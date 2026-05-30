"""
FastAPI Backend
Exposes violation data via REST API.
Run: uvicorn api.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import sqlite3
import os

DB_PATH = "logs/violations.db"

app = FastAPI(
    title="AI Smart Traffic Monitor API",
    description="Real-time traffic violation detection system — NTPC Internship Project",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DB helper ─────────────────────────────────────────────────────────────────

def get_db():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=503, detail="Database not found. Run detection first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Models ────────────────────────────────────────────────────────────────────

class ViolationOut(BaseModel):
    id:             int
    vehicle_id:     int
    vehicle_type:   str
    plate_text:     str
    speed:          Optional[float]
    speed_limit:    Optional[float]
    violation_type: str
    timestamp:      str
    camera_id:      str
    evidence_path:  Optional[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["System"])
def root():
    return {
        "system": "AI Smart Traffic Monitor",
        "version": "2.0.0",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health", tags=["System"])
def health():
    db_ok = os.path.exists(DB_PATH)
    return {"status": "healthy", "database": "connected" if db_ok else "not found"}


@app.get("/violations", response_model=list[ViolationOut], tags=["Violations"])
def get_violations(
    limit:          int            = Query(50,  ge=1, le=500),
    violation_type: Optional[str]  = Query(None, description="OVERSPEED | NO_HELMET"),
    vehicle_type:   Optional[str]  = Query(None, description="car | truck | motorcycle | bus"),
    camera_id:      Optional[str]  = Query(None),
):
    """Return recent violations with optional filters."""
    conn = get_db()
    query  = "SELECT * FROM violations WHERE 1=1"
    params = []

    if violation_type:
        query += " AND violation_type = ?"
        params.append(violation_type.upper())
    if vehicle_type:
        query += " AND vehicle_type = ?"
        params.append(vehicle_type.lower())
    if camera_id:
        query += " AND camera_id = ?"
        params.append(camera_id)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/violations/{violation_id}", response_model=ViolationOut, tags=["Violations"])
def get_violation(violation_id: int):
    """Get a single violation by ID."""
    conn = get_db()
    row  = conn.execute("SELECT * FROM violations WHERE id = ?", (violation_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Violation not found")
    return dict(row)


@app.get("/violations/{violation_id}/evidence", tags=["Violations"])
def get_evidence(violation_id: int):
    """Download the evidence image for a violation."""
    conn = get_db()
    row  = conn.execute(
        "SELECT evidence_path FROM violations WHERE id = ?", (violation_id,)
    ).fetchone()
    conn.close()

    if not row or not row["evidence_path"]:
        raise HTTPException(status_code=404, detail="No evidence image found")
    if not os.path.exists(row["evidence_path"]):
        raise HTTPException(status_code=404, detail="Evidence file missing on disk")

    return FileResponse(row["evidence_path"], media_type="image/jpeg")


@app.get("/stats", tags=["Analytics"])
def get_stats():
    """Return aggregated traffic statistics."""
    conn   = get_db()
    total  = conn.execute("SELECT COUNT(*) FROM violations").fetchone()[0]

    by_type = {
        r[0]: r[1] for r in conn.execute(
            "SELECT violation_type, COUNT(*) FROM violations GROUP BY violation_type"
        ).fetchall()
    }
    by_vehicle = {
        r[0]: r[1] for r in conn.execute(
            "SELECT vehicle_type, COUNT(*) FROM violations GROUP BY vehicle_type"
        ).fetchall()
    }
    by_camera = {
        r[0]: r[1] for r in conn.execute(
            "SELECT camera_id, COUNT(*) FROM violations GROUP BY camera_id"
        ).fetchall()
    }
    avg_speed = conn.execute(
        "SELECT AVG(speed) FROM violations WHERE speed IS NOT NULL"
    ).fetchone()[0]
    max_speed = conn.execute(
        "SELECT MAX(speed) FROM violations WHERE speed IS NOT NULL"
    ).fetchone()[0]

    hourly = conn.execute("""
        SELECT strftime('%H', timestamp) as hour, COUNT(*) as cnt
        FROM violations
        GROUP BY hour ORDER BY hour
    """).fetchall() 

    conn.close()
    return {
        "total_violations": total,
        "by_violation_type": by_type,
        "by_vehicle_type":   by_vehicle,
        "by_camera":         by_camera,
        "speed": {
            "average_kmh": round(avg_speed, 1) if avg_speed else 0,
            "max_kmh":     round(max_speed, 1) if max_speed else 0,
        },
        "hourly_distribution": {r[0]: r[1] for r in hourly},
    }


@app.delete("/violations", tags=["Admin"])
def clear_violations(confirm: str = Query(..., description="Pass 'yes' to confirm")):
    """Clear all violation records. Irreversible."""
    if confirm.lower() != "yes":
        raise HTTPException(status_code=400, detail="Pass confirm=yes to clear all records")
    conn = get_db()
    conn.execute("DELETE FROM violations")
    conn.commit()
    conn.close()
    return {"message": "All violations cleared"}
