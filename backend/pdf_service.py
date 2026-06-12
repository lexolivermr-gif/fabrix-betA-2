"""PDF export for manuals (ReportLab)."""
from __future__ import annotations

import io
import base64
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage,
)


def _img_from_b64(b64: Optional[str], max_w_mm: float = 150) -> Optional[RLImage]:
    if not b64:
        return None
    try:
        raw = base64.b64decode(b64)
        bio = io.BytesIO(raw)
        img = RLImage(bio, width=max_w_mm * mm, height=max_w_mm * mm)
        return img
    except Exception:
        return None


def render_manual_pdf(manual: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title=manual.get("title", "Manuel"),
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=24, leading=28, textColor=HexColor("#1a1a6e"), spaceAfter=8,
    )
    subtitle_style = ParagraphStyle(
        "subtitle", parent=styles["Normal"], fontName="Helvetica",
        fontSize=11, textColor=HexColor("#555555"), spaceAfter=16,
    )
    step_title_style = ParagraphStyle(
        "stepTitle", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=14, textColor=HexColor("#1a1a6e"), spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "body", parent=styles["Normal"], fontName="Helvetica",
        fontSize=10.5, leading=14, spaceAfter=8,
    )
    tip_style = ParagraphStyle(
        "tip", parent=styles["Normal"], fontName="Helvetica-Oblique",
        fontSize=10, leading=13, textColor=HexColor("#cc0000"), spaceAfter=10,
    )
    small_style = ParagraphStyle(
        "small", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.5, textColor=HexColor("#777777"),
    )

    story = []
    title = manual.get("title", "Manuel")
    story.append(Paragraph(title, title_style))
    meta = f"{manual.get('difficulty', '')} • {manual.get('total_duration_min', 0)} min • {len(manual.get('steps', []))} étapes"
    story.append(Paragraph(meta, subtitle_style))

    cover = _img_from_b64(manual.get("cover_image_base64"))
    if cover:
        cover._restrictSize(150 * mm, 150 * mm)
        story.append(cover)
        story.append(Spacer(1, 12))

    story.append(PageBreak())

    for i, step in enumerate(manual.get("steps", []), start=1):
        story.append(Paragraph(f"Étape {i} — {step.get('title','')}", step_title_style))
        sub = f"{step.get('duration_min', 0)} min"
        story.append(Paragraph(sub, small_style))
        story.append(Spacer(1, 6))

        img = _img_from_b64(step.get("image_base64"))
        if img:
            img._restrictSize(150 * mm, 150 * mm)
            story.append(img)
            story.append(Spacer(1, 8))

        if step.get("description"):
            story.append(Paragraph(step["description"].replace("\n", "<br/>"), body_style))
        if step.get("tip"):
            story.append(Paragraph("💡 " + step["tip"], tip_style))

        if i < len(manual["steps"]):
            story.append(PageBreak())

    story.append(Spacer(1, 18))
    story.append(Paragraph(
        f"Généré par ManuelIA — GPT-4o + DALL·E (gpt-image-1) — {datetime.utcnow().strftime('%Y-%m-%d')}",
        small_style,
    ))

    doc.build(story)
    return buf.getvalue()
