"""
Core Detection Pipeline — GPU Optimized + DeepSORT
Every vehicle: plate read + drawn on frame + logged to all_vehicles.csv
Violations:    overspeed + no-helmet → violations.csv + buzzer + evidence JPG
"""

import cv2
import logging
import numpy as np
from ultralytics import YOLO

from core.gpu_config import get_device, optimize_model, warmup
from core.deepsort_tracker import DeepSORTTracker
from utils.speed import SpeedEstimator
from utils.plate_ocr import PlateReader
from utils.helmet import HelmetDetector
from utils.logger import ViolationLogger
from utils.alert import AlertSystem
from utils.night_vision import NightVisionEnhancer
from utils.stolen_vehicle_db import StolenVehicleDB

# Telegram is optional — only used if configured
try:
    from utils.telegram_alert import TelegramAlerter
    _TELEGRAM_AVAILABLE = True
except Exception:
    _TELEGRAM_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Vehicle class IDs (COCO) ──────────────────────────────────────────────────
VEHICLE_CLASSES  = [2, 3, 5, 7]   # car, motorcycle, bus, truck
MOTORCYCLE_CLASS = 3
CLASS_NAMES      = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# ── Speed limits (km/h) ───────────────────────────────────────────────────────
SPEED_LIMITS = {"car": 15, "truck": 12, "bus": 12, "motorcycle": 12, "auto": 12}

# ── Draw colours ──────────────────────────────────────────────────────────────
COLOR_OK        = (0,  210,  60)   # green  — normal vehicle
COLOR_VIOLATION = (0,   30, 230)   # red    — violated vehicle
COLOR_PLATE     = (0,  220, 255)   # yellow — plate box
COLOR_HELMET_OK = (0,  200,   0)   # green  — helmet present
COLOR_NO_HELMET = (0,   0,  255)   # red    — no helmet

# ── How often to read plates for non-violating vehicles (every N frames) ──────
PLATE_READ_INTERVAL = 15   # read plate every 15 frames for better detection   # read plate once every 30 frames per vehicle


class TrafficPipeline:
    def __init__(self, config: dict):
        self.config    = config
        self.camera_id = config.get("camera_id", "CAM_01")
        self.device    = get_device()
        self.half      = config.get("half_precision", False) and self.device == "cuda"

        self._load_models()
        self._init_subsystems()

        self.vehicles  = {}   # track_id → state dict
        self.frame_idx = 0
        self.speed_est = None

        logger.info(f"[Pipeline] Ready — device={self.device} | cam={self.camera_id}")

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load_models(self):
        print("[Pipeline] Loading vehicle detector...")
        self.vehicle_model = YOLO(self.config["vehicle_model"])
        optimize_model(self.vehicle_model, self.device, self.half)
        warmup(self.vehicle_model, self.device)

        print("[Pipeline] Loading plate detector...")
        self.plate_reader = PlateReader(
            self.config["plate_model"],
            confidence=self.config.get("plate_conf", 0.20),
            device=self.device,
        )

        self.helmet_detector = None
        if self.config.get("helmet_model"):
            try:
                print("[Pipeline] Loading helmet detector...")
                self.helmet_detector = HelmetDetector(
                    self.config["helmet_model"], device=self.device
                )
            except Exception as e:
                print(f"[Pipeline] Helmet model skipped: {e}")

    def _init_subsystems(self):
        self.tracker = DeepSORTTracker(
            max_age=30, n_init=3,
            max_cosine_distance=0.4,
            device=self.device,
        )
        self.logger     = ViolationLogger()
        self.alert      = AlertSystem(cooldown_sec=4)
        self.night_vision = NightVisionEnhancer(
            mode=self.config.get("night_vision", "auto")
        )
        self.stolen_db  = StolenVehicleDB()
        # Telegram
        self.telegram   = None
        if _TELEGRAM_AVAILABLE and self.config.get("telegram_token"):
            self.telegram = TelegramAlerter(
                token   = self.config["telegram_token"],
                chat_id = self.config["telegram_chat_id"],
            )
            self.telegram.send_startup(self.camera_id)

    # ── Public API ────────────────────────────────────────────────────────────

    def init_speed_estimator(self, fps: float):
        self.speed_est = SpeedEstimator(
            entry_line_y         = self.config["entry_line_y"],
            exit_line_y          = self.config["exit_line_y"],
            real_distance_meters = self.config["real_distance_m"],
            fps                  = fps,
            perspective_factor   = self.config.get("perspective", 1.2),
        )

    def process_frame(self, frame: np.ndarray):
        self.frame_idx += 1
        new_violations = []

        # ── Night vision enhancement ──────────────────────────────────────────
        frame, enhanced = self.night_vision.enhance(frame)
        if enhanced:
            frame = self.night_vision.draw_indicator(frame, True)

        # ── Detect ────────────────────────────────────────────────────────────
        det = self.vehicle_model(
            frame, classes=VEHICLE_CLASSES,
            verbose=False, conf=0.40, device=self.device,
        )
        boxes = det[0].boxes

        # ── Track ─────────────────────────────────────────────────────────────
        if self.tracker.available and len(boxes):
            raw   = DeepSORTTracker.yolo_to_deepsort(boxes)
            tracks = self.tracker.update(raw, frame)
            tracked = self._tracks_to_list(tracks, boxes)
        else:
            fb = self.vehicle_model.track(
                frame, persist=True,
                classes=VEHICLE_CLASSES, verbose=False, conf=0.40,
            )
            tracked = self._yolo_fallback(fb)

        # ── Per vehicle ────────────────────────────────────────────────────────
        for (vid, cls, x1, y1, x2, y2) in tracked:
            label  = CLASS_NAMES.get(cls, "vehicle")
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            # Init state
            if vid not in self.vehicles:
                state = self.speed_est.new_vehicle_state() if self.speed_est else {}
                state.update({
                    "type":           label,
                    "cls":            cls,
                    "box":            (x1, y1, x2, y2),
                    "plate":          "UNKNOWN",
                    "plate_box":      None,
                    "plate_conf":     0.0,
                    "plate_img":      None,
                    "plate_logged":   False,
                    "plate_ready":    False,
                    "logged_speed":   False,
                    "logged_helmet":  False,
                    "speed":          None,
                    "last_plate_frame": -999,
                })
                self.vehicles[vid] = state

            state        = self.vehicles[vid]
            state["box"] = (x1, y1, x2, y2)

            if self.speed_est:
                self.speed_est.update(state, cy, self.frame_idx)

            # ── Read plate for every vehicle ──────────────────────────────────
            # Read once every PLATE_READ_INTERVAL frames (not every frame — slow)
            frames_since = self.frame_idx - state["last_plate_frame"]
            if (frames_since >= PLATE_READ_INTERVAL and
                    (x2 - x1) > 40 and (y2 - y1) > 30):
                now_ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                p_text, p_box, p_conf, p_path = self.plate_reader.read(
                    frame, (x1, y1, x2, y2),
                    vehicle_id=vid, timestamp=now_ts
                )
                if p_text != "UNKNOWN" or p_box is not None:
                    state["plate"]      = p_text
                    state["plate_box"]  = p_box
                    state["plate_conf"] = p_conf
                    state["plate_img"]  = p_path
                state["last_plate_frame"] = self.frame_idx

                # Mark plate as ready — actual CSV log happens after speed computed
                if state["plate"] != "UNKNOWN":
                    state["plate_ready"] = True

            # ── Check violations ──────────────────────────────────────────────
            v = self._check_violations(frame, vid, state, label, x1, y1, x2, y2)
            if v:
                new_violations.append(v)

            # ── Draw vehicle ──────────────────────────────────────────────────
            frame = self._draw_vehicle(frame, vid, label, state, x1, y1, x2, y2)

        frame = self._draw_lines(frame)
        frame = self._draw_hud(frame)
        return frame, new_violations

    def reset(self):
        self.vehicles  = {}
        self.frame_idx = 0

    # ── Violation logic ───────────────────────────────────────────────────────

    def _check_violations(self, frame, vid, state, label, x1, y1, x2, y2):
        record = None

        # OVERSPEED
        if self.speed_est and state.get("exit_frame") and not state["logged_speed"]:
            speed = self.speed_est.compute_speed(state)
            limit = SPEED_LIMITS.get(label, 40)
            if speed and speed > limit:
                # Ensure plate is read
                if state["plate"] == "UNKNOWN":
                    now_ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    p_text, p_box, p_conf, p_path = self.plate_reader.read(
                        frame, (x1,y1,x2,y2), vehicle_id=vid, timestamp=now_ts
                    )
                    state.update({
                        "plate": p_text, "plate_box": p_box,
                        "plate_conf": p_conf, "plate_img": p_path,
                    })
                state["speed"] = speed
                # Check stolen vehicle DB
                stolen_info = self.stolen_db.check(state["plate"])
                if stolen_info:
                    print(f"[STOLEN] !! STOLEN VEHICLE DETECTED: {state['plate']} !!")
                    self.stolen_db.log_alert(state["plate"], self.camera_id)
                    if self.telegram:
                        self.telegram.send_violation(
                            "STOLEN VEHICLE", state["plate"],
                            vehicle_type=label, camera_id=self.camera_id,
                            vehicle_id=vid,
                        )
                # Log to all_vehicles with actual speed
                if not state["plate_logged"]:
                    self.logger.log_vehicle(
                        vehicle_id    = vid,
                        vehicle_type  = label,
                        plate_text    = state["plate"],
                        plate_conf    = state["plate_conf"],
                        speed         = speed,
                        camera_id     = self.camera_id,
                        plate_img_path= state["plate_img"] or "",
                    )
                    state["plate_logged"] = True
                record = self.logger.log(
                    frame=frame, vehicle_box=(x1,y1,x2,y2),
                    plate_box=state["plate_box"],
                    vehicle_id=vid, vehicle_type=label,
                    plate_text=state["plate"],
                    violation_type="OVERSPEED",
                    speed=speed, speed_limit=limit,
                    camera_id=self.camera_id,
                    plate_conf=state["plate_conf"],
                    plate_img_path=state["plate_img"] or "",
                )
                self.alert.trigger(vid, "OVERSPEED", state["plate"], speed)
                if self.telegram:
                    self.telegram.send_violation(
                        "OVERSPEED", state["plate"], speed=speed,
                        vehicle_type=label, camera_id=self.camera_id,
                        evidence_path=record.get("evidence_path","") if record else "",
                        vehicle_id=vid,
                    )
                state["logged_speed"] = True

        # Log non-violating vehicles to all_vehicles when they cross EXIT line
        if (self.speed_est
                and state.get("exit_frame")
                and not state["plate_logged"]
                and state.get("plate_ready")):
            speed = self.speed_est.compute_speed(state)
            self.logger.log_vehicle(
                vehicle_id    = vid,
                vehicle_type  = label,
                plate_text    = state["plate"],
                plate_conf    = state["plate_conf"],
                speed         = speed,
                camera_id     = self.camera_id,
                plate_img_path= state["plate_img"] or "",
            )
            state["plate_logged"] = True

        # NO HELMET (motorcycle only — no line crossing needed)
        if (self.helmet_detector
                and state["cls"] == MOTORCYCLE_CLASS
                and not state["logged_helmet"]
                and (x2 - x1) > 40 and (y2 - y1) > 40):

            has_helmet, conf, head_box = self.helmet_detector.detect(
                frame, (x1, y1, x2, y2)
            )

            # Debug every 30 frames
            if self.frame_idx % 30 == 0:
                print(f"[Helmet] ID:{vid} has_helmet={has_helmet} conf={conf:.2f}")

            # Draw helmet box always (green=ok, red=no helmet)
            frame = self.helmet_detector.draw(frame, has_helmet, head_box)

            if not has_helmet:
                if state["plate"] == "UNKNOWN":
                    now_ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    p_text, p_box, p_conf, p_path = self.plate_reader.read(
                        frame, (x1,y1,x2,y2), vehicle_id=vid, timestamp=now_ts
                    )
                    state.update({
                        "plate": p_text, "plate_box": p_box,
                        "plate_conf": p_conf, "plate_img": p_path,
                    })
                record = self.logger.log(
                    frame=frame, vehicle_box=(x1,y1,x2,y2),
                    plate_box=state["plate_box"],
                    vehicle_id=vid, vehicle_type=label,
                    plate_text=state["plate"],
                    violation_type="NO_HELMET",
                    camera_id=self.camera_id,
                    plate_conf=state["plate_conf"],
                    plate_img_path=state["plate_img"] or "",
                )
                self.alert.trigger(vid, "NO_HELMET", state["plate"])
                if self.telegram:
                    self.telegram.send_violation(
                        "NO_HELMET", state["plate"],
                        vehicle_type=label, camera_id=self.camera_id,
                        evidence_path=record.get("evidence_path","") if record else "",
                        vehicle_id=vid,
                    )
                state["logged_helmet"] = True
                print(f"[Helmet] VIOLATION logged ID:{vid} plate:{state['plate']}")

        return record

    # ── Draw helpers ──────────────────────────────────────────────────────────

    def _draw_vehicle(self, frame, vid, label, state, x1, y1, x2, y2):
        violated = state["logged_speed"] or state["logged_helmet"]
        color    = COLOR_VIOLATION if violated else COLOR_OK

        # Vehicle bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Label tag: ID + type + speed
        speed_str = f" {state['speed']:.0f}km/h" if state.get("speed") else ""
        tag       = f"#{vid} {label}{speed_str}"
        (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)
        cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
        cv2.putText(frame, tag, (x1 + 3, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2)

        # Always draw plate box + number if detected
        if state["plate_box"] is not None:
            frame = self.plate_reader.draw(
                frame, state["plate"],
                state["plate_box"], state["plate_conf"]
            )

        return frame

    def _draw_lines(self, frame):
        h, w = frame.shape[:2]
        ey   = min(self.config["entry_line_y"], h - 20)
        xy   = min(self.config["exit_line_y"],  h - 5)

        # Cyan entry line
        cv2.line(frame, (0, ey), (w, ey), (0, 220, 255), 2)
        cv2.putText(frame, "ENTRY", (8, max(ey - 6, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 2)
        # Red exit line
        cv2.line(frame, (0, xy), (w, xy), (0, 0, 255), 3)
        cv2.putText(frame, "EXIT", (8, max(xy - 6, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        return frame

    def _draw_hud(self, frame):
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (270, 56), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0, frame)
        cv2.putText(frame, f"Frame : {self.frame_idx:06d}",
                    (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 220, 255), 1)
        cv2.putText(frame, f"Tracks: {len(self.vehicles)}  Cam: {self.camera_id}",
                    (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 220, 255), 1)
        return frame

    # ── Tracker format converters ─────────────────────────────────────────────

    def _tracks_to_list(self, tracks, boxes):
        result  = []
        box_arr = np.array([list(map(float, b.xyxy[0])) for b in boxes])
        cls_arr = [int(b.cls.item()) for b in boxes]
        for t in tracks:
            tx1, ty1, tx2, ty2 = DeepSORTTracker.ltrb(t)
            cls = self._match_class(tx1, ty1, tx2, ty2, box_arr, cls_arr)
            result.append((t.track_id, cls, tx1, ty1, tx2, ty2))
        return result

    def _yolo_fallback(self, results):
        if results[0].boxes.id is None:
            return []
        out = []
        for box in results[0].boxes:
            vid = int(box.id.item())
            cls = int(box.cls.item())
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            out.append((vid, cls, x1, y1, x2, y2))
        return out

    @staticmethod
    def _match_class(tx1, ty1, tx2, ty2, box_arr, cls_arr):
        if not len(box_arr):
            return 2
        ious = []
        for (bx1, by1, bx2, by2) in box_arr:
            ix1, iy1 = max(tx1, bx1), max(ty1, by1)
            ix2, iy2 = min(tx2, bx2), min(ty2, by2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = (tx2-tx1)*(ty2-ty1) + (bx2-bx1)*(by2-by1) - inter
            ious.append(inter / union if union else 0)
        return cls_arr[int(np.argmax(ious))]
