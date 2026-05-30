"""
PDF Report Generator
Generates daily/weekly violation reports with charts and evidence images.
Install: pip install fpdf2
"""

import os
import sqlite3
from datetime import datetime, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))


def generate_report(db_path: str = None, output_path: str = None,
                    title: str = "NTPC Smart Surveillance System",
                    period_days: int = 1) -> str:
    """
    Generate a PDF violation report.
    Returns: path to generated PDF file.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError("fpdf2 not installed. Run: pip install fpdf2")

    db_path     = db_path     or os.path.join(_ROOT, "logs", "violations.db")
    output_path = output_path or os.path.join(
        _ROOT, "results",
        f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # -- Fetch data ------------------------------------------------------------
    violations = []
    stats = {"total": 0, "overspeed": 0, "no_helmet": 0, "avg_speed": 0}

    if os.path.exists(db_path):
        cutoff = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            violations = [dict(r) for r in conn.execute(
                "SELECT * FROM violations WHERE date >= ? ORDER BY id DESC",
                (cutoff,)
            ).fetchall()]

        if violations:
            speeds = [v["speed"] for v in violations if v.get("speed")]
            stats = {
                "total":      len(violations),
                "overspeed":  sum(1 for v in violations if v.get("violation_type") == "OVERSPEED"),
                "no_helmet":  sum(1 for v in violations if v.get("violation_type") == "NO_HELMET"),
                "avg_speed":  round(sum(speeds) / len(speeds), 1) if speeds else 0,
            }

    # -- Build PDF -------------------------------------------------------------
    def _safe(text):
        """Remove characters not supported by Helvetica font."""
        return ''.join(c if ord(c) < 128 else '?' for c in str(text))

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_fill_color(5, 9, 17)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(77, 184, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_y(8)
    pdf.cell(0, 10, _safe(title), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 136, 170)
    pdf.cell(0, 8, _safe("NTPC - Summer Internship 2025 | Violation Report"), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    # Report info
    pdf.set_y(48)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 30, 30)
    period_label = "Daily" if period_days == 1 else f"Last {period_days} Days"
    pdf.cell(0, 8, _safe(f"{period_label} Report - Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, f"Period: {(datetime.now()-timedelta(days=period_days)).strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}",
             new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)

    # -- Stats summary boxes ---------------------------------------------------
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "SUMMARY STATISTICS", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    box_data = [
        ("Total Violations", str(stats["total"]),    (220, 50, 50)),
        ("Overspeed",         str(stats["overspeed"]),(255, 140, 0)),
        ("No Helmet",         str(stats["no_helmet"]),(255, 180, 0)),
        ("Avg Speed",         f"{stats['avg_speed']} km/h", (50, 150, 220)),
    ]
    x_start = 15
    box_w, box_h = 43, 24
    for i, (label, value, color) in enumerate(box_data):
        x = x_start + i * (box_w + 4)
        pdf.set_fill_color(*color)
        pdf.rect(x, pdf.get_y(), box_w, box_h, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_xy(x, pdf.get_y() + 3)
        pdf.cell(box_w, 8, value, align="C", new_x="RIGHT", new_y="TMARGIN")
        pdf.set_font("Helvetica", "", 7)
        pdf.set_xy(x, pdf.get_y() + 14)
        pdf.cell(box_w, 5, label.upper(), align="C", new_x="RIGHT", new_y="TMARGIN")

    pdf.set_y(pdf.get_y() + box_h + 8)
    pdf.set_text_color(0, 0, 0)

    # -- Violation table -------------------------------------------------------
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "VIOLATION LOG", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Table header
    headers = ["ID", "Type", "Plate", "Speed", "Violation", "Date", "Time"]
    widths  = [12, 22, 32, 22, 32, 28, 22]
    pdf.set_fill_color(5, 9, 17)
    pdf.set_text_color(77, 184, 255)
    pdf.set_font("Helvetica", "B", 8)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=0, fill=True, align="C")
    pdf.ln()

    # Table rows
    pdf.set_font("Helvetica", "", 8)
    for i, v in enumerate(violations[:50]):  # max 50 rows
        fill = i % 2 == 0
        pdf.set_fill_color(240, 245, 255) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(30, 30, 30)
        vtype = v.get("violation_type", "")
        color = (200, 50, 50) if "SPEED" in vtype else (200, 120, 0)
        row = [
            _safe(str(v.get("vehicle_id", ""))),
            _safe(v.get("vehicle_type", "").upper()[:10]),
            _safe(v.get("plate_text", "UNKNOWN")[:12]),
            _safe(f"{v['speed']:.0f} km/h" if v.get("speed") else "N/A"),
            _safe(vtype[:14]),
            _safe(v.get("date", "")[:10]),
            _safe(v.get("time", "")[:8]),
        ]
        for j, (cell, w) in enumerate(zip(row, widths)):
            if j == 4:  # violation type - colored
                pdf.set_text_color(*color)
            else:
                pdf.set_text_color(30, 30, 30)
            pdf.cell(w, 6, cell, border=0, fill=fill, align="C")
        pdf.ln()

    if len(violations) > 50:
        pdf.set_text_color(100, 100, 100)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 6, f"... and {len(violations)-50} more violations. See violations.csv for full data.",
                 new_x="LMARGIN", new_y="NEXT")

    # -- Evidence images -------------------------------------------------------
    evidence_imgs = [v.get("evidence_path", "") for v in violations[:6]
                     if v.get("evidence_path") and os.path.exists(v.get("evidence_path", ""))]

    if evidence_imgs:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 8, "EVIDENCE IMAGES (Latest 6 Violations)", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        x_positions = [10, 110]
        y_start = pdf.get_y()
        for i, img_path in enumerate(evidence_imgs):
            try:
                x = x_positions[i % 2]
                y = y_start + (i // 2) * 72
                pdf.image(img_path, x=x, y=y, w=90, h=65)
                # Caption
                v = violations[i]
                pdf.set_xy(x, y + 66)
                pdf.set_font("Helvetica", "", 7)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(90, 4,
                    f"{v.get('violation_type','')} | {v.get('plate_text','')} | {v.get('time','')}",
                    align="C")
            except Exception:
                pass

    # -- Footer ----------------------------------------------------------------
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5,
        f"NTPC Smart Surveillance 2025 | Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Page {pdf.page_no()}",
        align="C")

    pdf.output(output_path)
    print(f"[PDF] Report saved: {output_path}")
    return output_path
