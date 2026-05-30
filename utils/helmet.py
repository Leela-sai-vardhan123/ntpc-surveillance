"""
Helmet Detection Module
Model classes: {0: 'helmet', 1: 'two_wheeler', 2: 'without_helmet'}
Auto-detects class IDs from model names.
"""

from ultralytics import YOLO
import cv2


class HelmetDetector:
    def __init__(self, model_path, confidence=0.30, device="cpu"):
        self.model      = YOLO(model_path)
        self.confidence = confidence
        self.device     = device

        names = self.model.names
        print(f"[Helmet] Model loaded. Classes: {names}")

        self.HELMET_IDS    = []
        self.NO_HELMET_IDS = []
        self.SKIP_IDS      = []   # e.g. two_wheeler — not helmet/no-helmet

        for cid, cname in names.items():
            cn = cname.lower().replace("-", "_").replace(" ", "_")

            # No helmet class — any of these keywords
            if any(k in cn for k in ["without", "no_helmet", "nohelmet",
                                      "violation", "unsafe", "bare"]):
                self.NO_HELMET_IDS.append(cid)
                print(f"[Helmet] NO-HELMET class → ID {cid} ({cname})")

            # Skip class — vehicle body, not head/helmet
            elif any(k in cn for k in ["two_wheeler", "vehicle", "bike",
                                        "motorcycle", "person", "rider"]):
                self.SKIP_IDS.append(cid)
                print(f"[Helmet] SKIP class      → ID {cid} ({cname})")

            # Helmet present
            else:
                self.HELMET_IDS.append(cid)
                print(f"[Helmet] HELMET-OK class → ID {cid} ({cname})")

        # Safety fallback
        if not self.NO_HELMET_IDS:
            print("[Helmet] WARNING: no-helmet class not found — defaulting to class 2")
            self.NO_HELMET_IDS = [2]
        if not self.HELMET_IDS:
            print("[Helmet] WARNING: helmet class not found — defaulting to class 0")
            self.HELMET_IDS = [0]

        print(f"[Helmet] HELMET IDs    : {self.HELMET_IDS}")
        print(f"[Helmet] NO-HELMET IDs : {self.NO_HELMET_IDS}")
        print(f"[Helmet] SKIP IDs      : {self.SKIP_IDS}")

    def detect(self, frame, vehicle_box):
        """
        Detect helmet on motorcycle rider.
        Returns: (has_helmet, confidence, head_box)
        """
        x1, y1, x2, y2 = vehicle_box

        # Crop upper 60% of vehicle (head region)
        head_y2 = y1 + int((y2 - y1) * 0.60)
        roi = frame[y1:head_y2, x1:x2]

        if roi.size == 0 or roi.shape[0] < 10 or roi.shape[1] < 10:
            return True, 0.0, None

        results = self.model(
            roi, verbose=False,
            conf=self.confidence,
            device=self.device
        )

        best_no_helmet  = (None, 0.0)
        best_has_helmet = (None, 0.0)

        for box in results[0].boxes:
            cls  = int(box.cls.item())
            conf = float(box.conf.item())

            if cls in self.SKIP_IDS:
                continue  # ignore vehicle body detections

            bx1, by1, bx2, by2 = map(int, box.xyxy[0])
            abs_box = (x1 + bx1, y1 + by1, x1 + bx2, y1 + by2)

            if cls in self.NO_HELMET_IDS and conf > best_no_helmet[1]:
                best_no_helmet = (abs_box, conf)
            elif cls in self.HELMET_IDS and conf > best_has_helmet[1]:
                best_has_helmet = (abs_box, conf)

        # No-helmet takes priority
        if best_no_helmet[0] is not None:
            return False, best_no_helmet[1], best_no_helmet[0]
        if best_has_helmet[0] is not None:
            return True, best_has_helmet[1], best_has_helmet[0]

        return True, 0.0, None

    def draw(self, frame, has_helmet, head_box):
        if head_box is None:
            return frame
        x1, y1, x2, y2 = head_box
        color = (0, 200, 0) if has_helmet else (0, 0, 255)
        label = "HELMET OK" if has_helmet else "NO HELMET!"
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(frame, label, (x1 + 2, y1 - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
        return frame
