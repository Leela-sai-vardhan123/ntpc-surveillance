"""
Violation Logger
Logs ALL vehicles (plate read) + violations (overspeed/no-helmet) to:
  CSV  → logs/violations.csv      (violations only)
  CSV  → logs/all_vehicles.csv    (every vehicle with plate)
  DB   → logs/violations.db
  JPG  → results/violations/      (violation evidence)
  JPG  → results/plates/          (plate crops — handled by plate_ocr.py)
"""

import os
import csv
import sqlite3
import cv2
from datetime import datetime

_HERE    = os.path.dirname(os.path.abspath(__file__))
_ROOT    = os.path.abspath(os.path.join(_HERE, ".."))
_LOG_DIR = os.path.join(_ROOT, "logs")
_EVI_DIR = os.path.join(_ROOT, "results", "violations")


class ViolationLogger:
    def __init__(self, log_dir=None, evidence_dir=None):
        self.log_dir      = log_dir      or _LOG_DIR
        self.evidence_dir = evidence_dir or _EVI_DIR
        os.makedirs(self.log_dir,      exist_ok=True)
        os.makedirs(self.evidence_dir, exist_ok=True)

        self.violations_csv  = os.path.join(self.log_dir, "violations.csv")
        self.all_vehicles_csv = os.path.join(self.log_dir, "all_vehicles.csv")
        self.db_path         = os.path.join(self.log_dir, "violations.db")

        self._init_violations_csv()
        self._init_all_vehicles_csv()
        self._init_db()

        print(f"[Logger] violations CSV → {self.violations_csv}")
        print(f"[Logger] all_vehicles  → {self.all_vehicles_csv}")
        print(f"[Logger] DB            → {self.db_path}")
        print(f"[Logger] Evidence imgs → {self.evidence_dir}")

    # ── CSV init ──────────────────────────────────────────────────────────────

    VIOLATION_HEADERS = [
        "Vehicle ID", "Vehicle Type", "License Plate", "Plate Confidence",
        "Speed (km/h)", "Speed Limit (km/h)", "Violation Type",
        "Date", "Time", "Camera ID",
        "Evidence Image", "Plate Image"
    ]

    ALL_VEHICLE_HEADERS = [
        "Vehicle ID", "Vehicle Type", "License Plate", "Plate Confidence",
        "Speed (km/h)", "Date", "Time", "Camera ID", "Plate Image"
    ]

    def _init_violations_csv(self):
        if not os.path.exists(self.violations_csv):
            with open(self.violations_csv, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self.VIOLATION_HEADERS)

    def _init_all_vehicles_csv(self):
        if not os.path.exists(self.all_vehicles_csv):
            with open(self.all_vehicles_csv, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self.ALL_VEHICLE_HEADERS)

    # ── DB init ───────────────────────────────────────────────────────────────

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS violations (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id      INTEGER,
                    vehicle_type    TEXT,
                    plate_text      TEXT,
                    plate_conf      REAL,
                    speed           REAL,
                    speed_limit     REAL,
                    violation_type  TEXT,
                    timestamp       TEXT,
                    date            TEXT,
                    time            TEXT,
                    camera_id       TEXT,
                    evidence_path   TEXT,
                    plate_img_path  TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS all_vehicles (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id      INTEGER,
                    vehicle_type    TEXT,
                    plate_text      TEXT,
                    plate_conf      REAL,
                    speed           REAL,
                    timestamp       TEXT,
                    date            TEXT,
                    time            TEXT,
                    camera_id       TEXT,
                    plate_img_path  TEXT
                )
            """)
            conn.commit()

    # ── Evidence image ────────────────────────────────────────────────────────

    def _save_evidence(self, frame, vehicle_box, plate_box, r):
        img = frame.copy()
        x1, y1, x2, y2 = vehicle_box

        # Red vehicle box
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 3)

        # Cyan plate box
        if plate_box:
            cv2.rectangle(img,
                          (plate_box[0], plate_box[1]),
                          (plate_box[2], plate_box[3]),
                          (0, 220, 255), 2)

        # Dark top banner
        overlay = img.copy()
        cv2.rectangle(overlay, (0, 0), (img.shape[1], 170), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.65, img, 0.35, 0, img)

        vtype = r["violation_type"]
        color = (0, 80, 255) if "SPEED" in vtype else (0, 140, 255)
        lines = [
            f"VIOLATION : {vtype}",
            f"Vehicle   : #{r['vehicle_id']}  {r['vehicle_type'].upper()}",
            f"Plate     : {r['plate_text']}  (conf: {r.get('plate_conf',0):.0%})",
            f"Speed     : {r['speed']:.1f} km/h  (limit {r.get('speed_limit','N/A')} km/h)"
                if r.get("speed") else "Speed     : N/A",
            f"Camera    : {r.get('camera_id','CAM_01')}",
            f"Time      : {r['date']}  {r['time']}",
        ]
        for i, line in enumerate(lines):
            c = color if i == 0 else (255, 255, 255)
            cv2.putText(img, line, (10, 24 + i * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, c, 2)

        ts    = r["time"].replace(":", "-")
        fname = f"{r['vehicle_id']}_{vtype}_{r['date']}_{ts}.jpg"
        path  = os.path.join(self.evidence_dir, fname)
        cv2.imwrite(path, img)
        return path

    # ── Public: log every vehicle plate ──────────────────────────────────────

    def log_vehicle(self, vehicle_id, vehicle_type, plate_text, plate_conf=0.0,
                    speed=None, camera_id="CAM_01", plate_img_path=""):
        """
        Called for EVERY vehicle detected (even no violation).
        Writes to all_vehicles.csv and all_vehicles DB table.
        """
        now = datetime.now()
        row = {
            "vehicle_id":    int(vehicle_id),
            "vehicle_type":  vehicle_type,
            "plate_text":    plate_text or "UNKNOWN",
            "plate_conf":    round(float(plate_conf), 2),
            "speed":         round(float(speed), 1) if speed else None,
            "timestamp":     now.strftime("%Y-%m-%d %H:%M:%S"),
            "date":          now.strftime("%Y-%m-%d"),
            "time":          now.strftime("%H:%M:%S"),
            "camera_id":     camera_id,
            "plate_img_path": plate_img_path or "",
        }
        # CSV
        with open(self.all_vehicles_csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                row["vehicle_id"], row["vehicle_type"],
                row["plate_text"], row["plate_conf"],
                row["speed"] or "N/A",
                row["date"], row["time"],
                row["camera_id"], row["plate_img_path"],
            ])
        # DB
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO all_vehicles
                (vehicle_id, vehicle_type, plate_text, plate_conf, speed,
                 timestamp, date, time, camera_id, plate_img_path)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                row["vehicle_id"], row["vehicle_type"], row["plate_text"],
                row["plate_conf"], row["speed"],
                row["timestamp"], row["date"], row["time"],
                row["camera_id"], row["plate_img_path"],
            ))
            conn.commit()

    # ── Public: log violation ─────────────────────────────────────────────────

    def log(self, frame, vehicle_box, plate_box,
            vehicle_id, vehicle_type, plate_text,
            violation_type, speed=None, speed_limit=None,
            camera_id="CAM_01", plate_conf=0.0, plate_img_path=""):
        """
        Log a violation — OVERSPEED or NO_HELMET.
        Writes to violations.csv, DB, and saves evidence JPEG.
        """
        now = datetime.now()
        r = {
            "vehicle_id":    int(vehicle_id),
            "vehicle_type":  vehicle_type,
            "plate_text":    plate_text or "UNKNOWN",
            "plate_conf":    round(float(plate_conf), 2),
            "speed":         round(float(speed), 1) if speed else None,
            "speed_limit":   speed_limit,
            "violation_type": violation_type,
            "timestamp":     now.strftime("%Y-%m-%d %H:%M:%S"),
            "date":          now.strftime("%Y-%m-%d"),
            "time":          now.strftime("%H:%M:%S"),
            "camera_id":     camera_id,
            "plate_img_path": plate_img_path or "",
        }

        # Evidence image
        try:
            r["evidence_path"] = self._save_evidence(frame, vehicle_box, plate_box, r)
        except Exception as e:
            print(f"[Logger] Evidence save error: {e}")
            r["evidence_path"] = ""

        # Violations CSV
        with open(self.violations_csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                r["vehicle_id"], r["vehicle_type"],
                r["plate_text"], r["plate_conf"],
                f"{r['speed']:.1f}" if r.get("speed") else "N/A",
                r.get("speed_limit", "N/A"),
                r["violation_type"],
                r["date"], r["time"],
                r["camera_id"],
                r["evidence_path"],
                r["plate_img_path"],
            ])

        # DB
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO violations
                (vehicle_id, vehicle_type, plate_text, plate_conf,
                 speed, speed_limit, violation_type,
                 timestamp, date, time, camera_id,
                 evidence_path, plate_img_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                r["vehicle_id"], r["vehicle_type"], r["plate_text"], r["plate_conf"],
                r.get("speed"), r.get("speed_limit"), r["violation_type"],
                r["timestamp"], r["date"], r["time"], r["camera_id"],
                r["evidence_path"], r["plate_img_path"],
            ))
            conn.commit()

        spd = f"{speed:.1f} km/h" if speed else "N/A"
        print(f"[Logger] {violation_type:12s} | ID:{int(vehicle_id):3d} | "
              f"{vehicle_type:10s} | {plate_text:12s} | {spd}")
        return r

    # ── Read back ─────────────────────────────────────────────────────────────

    def get_all(self):
        if not os.path.exists(self.db_path):
            return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM violations ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_all_vehicles(self):
        if not os.path.exists(self.db_path):
            return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM all_vehicles ORDER BY id DESC LIMIT 200"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self):
        if not os.path.exists(self.db_path):
            return {"total": 0, "by_type": {}, "by_vehicle": {}, "avg_speed": 0}
        with sqlite3.connect(self.db_path) as conn:
            total      = conn.execute("SELECT COUNT(*) FROM violations").fetchone()[0]
            by_type    = dict(conn.execute(
                "SELECT violation_type, COUNT(*) FROM violations GROUP BY violation_type"
            ).fetchall())
            by_vehicle = dict(conn.execute(
                "SELECT vehicle_type, COUNT(*) FROM violations GROUP BY vehicle_type"
            ).fetchall())
            avg_speed  = conn.execute(
                "SELECT AVG(speed) FROM violations WHERE speed IS NOT NULL"
            ).fetchone()[0]
        return {
            "total":      total,
            "by_type":    by_type,
            "by_vehicle": by_vehicle,
            "avg_speed":  round(avg_speed, 1) if avg_speed else 0,
        }
