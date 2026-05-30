"""
Stolen Vehicle Database
Checks detected plates against a stolen/wanted vehicles list.
Stored in SQLite — easy to add/remove plates.
"""

import os
import sqlite3
from datetime import datetime

_HERE   = os.path.dirname(os.path.abspath(__file__))
_ROOT   = os.path.abspath(os.path.join(_HERE, ".."))
_DB     = os.path.join(_ROOT, "logs", "stolen_vehicles.db")
_CSV    = os.path.join(_ROOT, "logs", "stolen_vehicles.csv")


class StolenVehicleDB:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or _DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self._load_sample_data()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stolen_vehicles (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate       TEXT UNIQUE NOT NULL,
                    owner_name  TEXT,
                    vehicle_type TEXT,
                    reason      TEXT,
                    reported_date TEXT,
                    added_by    TEXT,
                    active      INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stolen_alerts (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    plate       TEXT,
                    camera_id   TEXT,
                    timestamp   TEXT,
                    evidence_path TEXT
                )
            """)
            conn.commit()

    def _load_sample_data(self):
        """Add sample stolen plates for demo purposes."""
        samples = [
            ("AP09AB1234", "Demo Owner 1", "car",        "Stolen",  "2025-01-01", "Police"),
            ("TS08CD5678", "Demo Owner 2", "motorcycle", "Wanted",  "2025-01-15", "Police"),
            ("MH12EF9012", "Demo Owner 3", "truck",      "Stolen",  "2025-02-01", "Police"),
        ]
        with sqlite3.connect(self.db_path) as conn:
            for plate, owner, vtype, reason, date, added in samples:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO stolen_vehicles "
                        "(plate, owner_name, vehicle_type, reason, reported_date, added_by) "
                        "VALUES (?,?,?,?,?,?)",
                        (plate, owner, vtype, reason, date, added)
                    )
                except Exception:
                    pass
            conn.commit()

    def check(self, plate: str) -> dict | None:
        """
        Check if plate is in stolen database.
        Returns vehicle info dict if found, None if clean.
        """
        if not plate or plate in ("UNKNOWN", ""):
            return None
        plate = plate.upper().strip().replace(" ", "")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM stolen_vehicles WHERE plate=? AND active=1",
                (plate,)
            ).fetchone()
        return dict(row) if row else None

    def log_alert(self, plate: str, camera_id: str, evidence_path: str = ""):
        """Log a stolen vehicle detection."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO stolen_alerts (plate,camera_id,timestamp,evidence_path) VALUES (?,?,?,?)",
                (plate, camera_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), evidence_path)
            )
            conn.commit()
        print(f"[StolenDB] ALERT LOGGED: {plate} at {camera_id}")

    def add_plate(self, plate: str, owner: str = "", vehicle_type: str = "",
                  reason: str = "Stolen", added_by: str = "User") -> bool:
        """Add a plate to the stolen database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO stolen_vehicles "
                    "(plate,owner_name,vehicle_type,reason,reported_date,added_by) "
                    "VALUES (?,?,?,?,?,?)",
                    (plate.upper(), owner, vehicle_type, reason,
                     datetime.now().strftime("%Y-%m-%d"), added_by)
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"[StolenDB] Add failed: {e}")
            return False

    def remove_plate(self, plate: str) -> bool:
        """Deactivate a plate (soft delete)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE stolen_vehicles SET active=0 WHERE plate=?",
                (plate.upper(),)
            )
            conn.commit()
        return True

    def get_all(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT * FROM stolen_vehicles WHERE active=1 ORDER BY id DESC"
            ).fetchall()]

    def get_alerts(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT * FROM stolen_alerts ORDER BY id DESC LIMIT 50"
            ).fetchall()]
