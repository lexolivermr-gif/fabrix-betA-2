"""PDF assembly: one A4 page per step, vector blueprint on top, prose below."""
from __future__ import annotations

import io
from datetime import datetime
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from . import render as R
from .blueprint import theme as T

NAVY = colors.HexColor("#0B3D6B")
BLUE = colors.HexColor("#0058A3")
RED = colors.HexColor("#CC0008")
GREY = colors.HexColor("#5A6B7A")
LINE = colors.HexColor("#D9E4EF")

DRAW_W_MM = 158.0
DRAW_H_MM = DRAW_W_MM * T.SHEET_H / T.SHEET_W


def _styles():
    ss = getSampleStyleSheet()
    s = {}
    s["cover_title"] = ParagraphStyle("ct", parent=ss["Title"], fontName="Helvetica-Bold",
                                      fontSize=25, leading=29, textColor=NAVY, alignment=TA_LEFT,
                                      spaceAfter=4)
    s["cover_sub"] = ParagraphStyle("cs", parent=ss["Normal"], fontName="Helvetica",
                                    fontSize=11.5, leading=15, textColor=GREY, spaceAfter=12)
    s["h2"] = ParagraphStyle("h2", parent=ss["Normal"], fontName="Helvetica-Bold",
                            fontSize=13.5, leading=17, textColor=NAVY, spaceBefore=7, spaceAfter=3)
    s["h3"] = ParagraphStyle("h3", parent=ss["Normal"], fontName="Helvetica-Bold",
                            fontSize=9.4, leading=12.2, textColor=BLUE, spaceBefore=6, spaceAfter=2)
    s["body"] = ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=9.6, leading=13.2, textColor=colors.HexColor("#1B2A38"),
                               spaceAfter=5)
    s["li"] = ParagraphStyle("li", parent=s["body"], leftIndent=11, bulletIndent=2,
                             spaceAfter=3.5)
    s["why"] = ParagraphStyle("w", parent=s["body"], fontSize=9.1, leading=12.4,
                              textColor=colors.HexColor("#33526E"), leftIndent=8)
    s["tip"] = ParagraphStyle("t", parent=s["body"], fontSize=9.1, leading=12.4,
                              textColor=RED, leftIndent=8)
    s["check"] = ParagraphStyle("c", parent=s["body"], fontSize=9.1, leading=12.4,
                                textColor=colors.HexColor("#12633C"), leftIndent=8)
    s["small"] = ParagraphStyle("s", parent=ss["Normal"], fontName="Helvetica",
                                fontSize=8, textColor=GREY)
    s["cell"] = ParagraphStyle("tc", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=8.5, leading=11)
    s["cellb"] = ParagraphStyle("tcb", parent=s["cell"], fontName="Helvetica-Bold",
                                textColor=NAVY)
    return s


def _esc(t) -> str:
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _dims(p) -> str:
    """Format declared dimensions.

    NB: an f-string format spec applies to the WHOLE replacement field, so
    f"{x if c else y:.1f}" silently formats the integer branch too. Format each
    value separately.
    """
    bits = []
    for k, u in (("length_mm", ""), ("width_mm", " × "), ("thickness_mm", " × ")):
        if p.get(k):
            f = float(p[k])
            v = str(int(f)) if abs(f - int(f)) < 1e-6 else f"{f:.1f}"
            bits.append(f"{u}{v}")
    return ("".join(bits) + " mm") if bits else "-"


def build_pdf(spec: dict) -> bytes:
    S = _styles()
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=19 * mm, rightMargin=19 * mm,
                          topMargin=16 * mm, bottomMargin=15 * mm,
                          title=str(spec.get("title", "Build guide")),
                          author="Fabrix Engineer")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")

    def deco(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(doc.leftMargin, A4[1] - 10 * mm,
                          str(spec.get("title", ""))[:78])
        canvas.drawRightString(A4[0] - doc.rightMargin, A4[1] - 10 * mm, "FABRIX ENGINEER")
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, A4[1] - 12 * mm, A4[0] - doc.rightMargin, A4[1] - 12 * mm)
        canvas.line(doc.leftMargin, 11 * mm, A4[0] - doc.rightMargin, 11 * mm)
        canvas.drawString(doc.leftMargin, 7.5 * mm,
                          f"Generated {datetime.utcnow():%Y-%m-%d}")
        canvas.drawRightString(A4[0] - doc.rightMargin, 7.5 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=deco)])

    st: List = []
    steps = spec["steps"]

    # ---------------- cover ------------------------------------------------
    st.append(Paragraph(_esc(spec.get("title", "")), S["cover_title"]))
    meta_bits = [spec.get("difficulty", ""), f'{spec.get("total_duration_min", 0)} min',
                 f"{len(steps)} steps", (spec.get("mode") or "create").upper()]
    st.append(Paragraph(" · ".join(b for b in meta_bits if b), S["cover_sub"]))
    if spec.get("summary"):
        st.append(Paragraph(_esc(spec["summary"]), S["body"]))
        st.append(Spacer(1, 5))

    st.append(Paragraph("HOW IT WORKS", S["h2"]))
    for p in spec.get("principles") or []:
        st.append(Paragraph(f"• {_esc(p)}", S["li"]))

    # nomenclature sheet
    st.append(Paragraph("PARTS &amp; NOMENCLATURE", S["h2"]))
    ov = R.overview_drawing(spec)
    ov.width = DRAW_W_MM * mm
    ov.height = DRAW_H_MM * mm
    ov.scale(DRAW_W_MM * mm / T.SHEET_W, DRAW_H_MM * mm / T.SHEET_H)
    st.append(ov)

    st.append(Spacer(1, 4))
    rows = [[Paragraph("REF", S["cellb"]), Paragraph("PART", S["cellb"]),
             Paragraph("MATERIAL", S["cellb"]), Paragraph("DIMENSIONS", S["cellb"]),
             Paragraph("QTY", S["cellb"]), Paragraph("WHERE TO GET IT", S["cellb"])]]
    for p in spec["materials"]:
        rows.append([Paragraph(_esc(p["ref"]), S["cell"]),
                     Paragraph(_esc(p["name"]), S["cell"]),
                     Paragraph(_esc(p["material"] or "—"), S["cell"]),
                     Paragraph(_dims(p), S["cell"]),
                     Paragraph(str(p["qty"]), S["cell"]),
                     Paragraph(_esc(p.get("source") or "—"), S["cell"])])
    t = Table(rows, colWidths=[16 * mm, 38 * mm, 33 * mm, 30 * mm, 11 * mm, 44 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3D6B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F8FC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    st.append(t)

    if spec.get("tools"):
        st.append(Paragraph("TOOLS", S["h2"]))
        for tl in spec["tools"]:
            extra = ""
            if tl.get("substitute"):
                extra = f' <font color="#5A6B7A">— substitute: {_esc(tl["substitute"])}</font>'
            opt = ' <font color="#5A6B7A">(optional)</font>' if tl.get("optional") else ""
            st.append(Paragraph(f"• {_esc(tl['name'])}{opt}{extra}", S["li"]))

    if spec.get("safety"):
        st.append(Paragraph("SAFETY", S["h2"]))
        for x in spec["safety"]:
            st.append(Paragraph(f'<font color="#CC0008">⚠</font> {_esc(x)}', S["li"]))

    # ---------------- steps ------------------------------------------------
    for i, step in enumerate(steps, start=1):
        st.append(PageBreak())
        head = Table([[Paragraph(f'<font color="#FFFFFF"><b>STEP {i}</b> / {len(steps)}</font>',
                                 _styles()["small"]),
                       Paragraph(f'<font color="#FFFFFF"><b>{_esc(step["title"])}</b></font>',
                                 ParagraphStyle("hh", parent=S["body"], fontName="Helvetica-Bold",
                                                fontSize=12.5, textColor=colors.white))]],
                     colWidths=[28 * mm, 144 * mm])
        head.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        st.append(head)
        st.append(Spacer(1, 3))
        st.append(Paragraph(
            f'{step["duration_min"]} min · parts: '
            f'{", ".join(step["parts_used"]) or "—"}', S["small"]))
        st.append(Spacer(1, 6))

        drw = R.step_drawing(spec, i - 1)
        drw.width = DRAW_W_MM * mm
        drw.height = DRAW_H_MM * mm
        drw.scale(DRAW_W_MM * mm / T.SHEET_W, DRAW_H_MM * mm / T.SHEET_H)
        st.append(drw)
        st.append(Spacer(1, 6))

        if step.get("intent"):
            st.append(Paragraph(_esc(step["intent"]), S["body"]))

        st.append(Paragraph("DO THIS", S["h3"]))
        for j, a in enumerate(step["actions"], start=1):
            st.append(Paragraph(f"<b>{j}.</b> {_esc(a)}", S["li"]))

        if step.get("why"):
            st.append(Paragraph("WHY IT WORKS", S["h3"]))
            st.append(Paragraph(_esc(step["why"]), S["why"]))
        if step.get("check"):
            st.append(Paragraph("CHECK", S["h3"]))
            st.append(Paragraph(_esc(step["check"]), S["check"]))
        if step.get("tip"):
            st.append(Paragraph("TIP", S["h3"]))
            st.append(Paragraph(_esc(step["tip"]), S["tip"]))

    # ---------------- final validation ------------------------------------
    if spec.get("checks"):
        st.append(PageBreak())
        st.append(Paragraph("FINAL FUNCTION TEST", S["h2"]))
        for j, c in enumerate(spec["checks"], start=1):
            st.append(Paragraph(f"<b>{j}.</b> {_esc(c)}", S["li"]))

    doc.build(st)
    return buf.getvalue()
