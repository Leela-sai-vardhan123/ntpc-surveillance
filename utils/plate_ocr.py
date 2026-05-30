"""
License Plate Detection + OCR Module
- Always draws yellow box around plate
- Shows plate number on frame
- Saves plate crop as separate JPG
- Logs every vehicle's plate to CSV
"""

import re
import os
import cv2
import easyocr
from ultralytics import YOLO

_HERE     = os.path.dirname(os.path.abspath(__file__))
_ROOT     = os.path.abspath(os.path.join(_HERE, ".."))
PLATE_DIR = os.path.join(_ROOT, "results", "plates")


class PlateReader:
    def __init__(self, plate_model_path, confidence=0.35, device="cpu"):
        self.plate_model = YOLO(plate_model_path)
        self.confidence  = confidence
        self.device      = device
        use_gpu          = device == "cuda"
        self.ocr         = easyocr.Reader(['en'], gpu=use_gpu)
        os.makedirs(PLATE_DIR, exist_ok=True)

        # Indian plate patterns
        self.PATTERNS = [
            r'^[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}$',
            r'^[A-Z]{2}\d{2}[A-Z]{2}\d{4}$',
            r'^[A-Z]{2}\d{2}[A-Z]\d{4}$',
        ]

    # ── OCR helpers ───────────────────────────────────────────────────────────

    def _clean(self, raw):
        text = re.sub(r'[^A-Z0-9]', '', raw.upper().strip())
        for p in self.PATTERNS:
            if re.match(p, text):
                return text
        return text if 5 <= len(text) <= 12 else None

    def _preprocess(self, img):
        img   = cv2.resize(img, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
        gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enh   = clahe.apply(gray)
        den   = cv2.fastNlMeansDenoising(enh, h=10)
        return cv2.cvtColor(den, cv2.COLOR_GRAY2BGR)

    def _save_plate_crop(self, plate_img, vehicle_id, timestamp):
        """Save the cropped plate as a separate JPG."""
        ts   = timestamp.replace(":", "-").replace(" ", "_")
        fname = f"plate_{vehicle_id}_{ts}.jpg"
        path  = os.path.join(PLATE_DIR, fname)
        cv2.imwrite(path, plate_img)
        return path

    # ── Main read ─────────────────────────────────────────────────────────────

    def read(self, frame, vehicle_box, vehicle_id=None, timestamp=None):
        """
        Detect plate inside vehicle crop, run OCR, save plate JPG.
        Returns: (plate_text, plate_box, confidence, plate_img_path)
          plate_box is in full-frame coordinates.
        """
        x1, y1, x2, y2 = vehicle_box
        vehicle_crop    = frame[y1:y2, x1:x2]

        if vehicle_crop.size == 0:
            return "UNKNOWN", None, 0.0, None

        plate_results = self.plate_model(
            vehicle_crop, verbose=False, conf=self.confidence
        )

        best_text  = "UNKNOWN"
        best_conf  = 0.0
        best_box   = None
        best_path  = None

        for box in plate_results[0].boxes:
            px1, py1, px2, py2 = map(int, box.xyxy[0])
            # Clamp to crop bounds
            px1, py1 = max(0, px1), max(0, py1)
            px2 = min(vehicle_crop.shape[1], px2)
            py2 = min(vehicle_crop.shape[0], py2)

            plate_crop = vehicle_crop[py1:py2, px1:px2]
            if plate_crop.size == 0:
                continue

            # Save raw plate crop
            if vehicle_id is not None and timestamp is not None:
                path = self._save_plate_crop(plate_crop, vehicle_id, timestamp)
            else:
                path = None

            # OCR
            processed  = self._preprocess(plate_crop)
            ocr_result = self.ocr.readtext(processed)

            for (_, text, conf) in ocr_result:
                cleaned = self._clean(text)
                if cleaned and conf > best_conf:
                    best_text = cleaned
                    best_conf = conf
                    # Translate to full-frame coords
                    best_box  = (x1 + px1, y1 + py1, x1 + px2, y1 + py2)
                    best_path = path

            # If no OCR matched but plate was detected, still save box
            if best_box is None:
                best_box  = (x1 + px1, y1 + py1, x1 + px2, y1 + py2)
                best_path = path

        return best_text, best_box, round(best_conf, 2), best_path

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self, frame, plate_text, plate_box, confidence=None):
        """
        Draw yellow plate box + plate number text on frame.
        Always call this even if plate_text is UNKNOWN.
        """
        if plate_box is None:
            return frame

        x1, y1, x2, y2 = plate_box
        # Yellow box around plate
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 255), 2)

        # Label: plate number + confidence
        conf_str = f" {confidence:.0%}" if confidence and confidence > 0 else ""
        label    = f"{plate_text}{conf_str}"

        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)
        lx, ly = x1, y2 + th + 6

        # Background for readability
        cv2.rectangle(frame, (lx - 1, ly - th - 4), (lx + tw + 4, ly + 2),
                      (0, 0, 0), -1)
        cv2.putText(frame, label, (lx + 2, ly),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 220, 255), 2)
        return frame
