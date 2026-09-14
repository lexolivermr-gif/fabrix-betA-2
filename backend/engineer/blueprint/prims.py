"""
Primitives + two rendering backends.

A drawing is a flat list of primitive dicts in SHEET coordinates
(0..SHEET_W, 0..SHEET_H, y grows downward, like SVG). Two backends consume
the exact same list:

    to_svg(prims)        -> SVG string            (web, crisp at any size)
    to_reportlab(prims)  -> reportlab Drawing     (vector, embedded in the PDF)

Because both consume one list, the picture in the app and the picture in the PDF
are the same picture by construction — there is no second code path that could
drift out of sync with the explanation.

Primitives
----------
rect    x,y,w,h, fill,stroke,sw,dash,rx
poly    pts[(x,y)], fill,stroke,sw,dash,close
circle  cx,cy,r,   fill,stroke,sw,dash
line    x1,y1,x2,y2, stroke,sw,dash,cap
path    segs[("M"|"L"|"C"|"Z", ...)], fill,stroke,sw,dash
text    x,y,s,size,fill,anchor,weight,rot
"""
from __future__ import annotations

from typing import List

from . import theme as T


# ---------------------------------------------------------------------------
# SVG backend
# ---------------------------------------------------------------------------
def _svg_color(c):
    return c or "none"


def _svg_dash(d):
    if not d:
        return ""
    return f' stroke-dasharray="{",".join(str(round(v, 3)) for v in d)}"'


def to_svg(prims: List[dict], w: float = T.SHEET_W, h: float = T.SHEET_H,
           px_per_unit: float = 14.0) -> str:
    W = round(w * px_per_unit)
    H = round(h * px_per_unit)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {w} {h}" font-family="{T.MONO_FONT}">',
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="{T.SHEET_BG}"/>',
        '<g stroke-linecap="round" stroke-linejoin="round">',
    ]

    for p in prims:
        op = p["op"]
        if op == "rect":
            out.append(
                f'<rect x="{p["x"]:.3f}" y="{p["y"]:.3f}" width="{max(p["w"],0):.3f}" '
                f'height="{max(p["h"],0):.3f}" rx="{p.get("rx",0):.3f}" '
                f'fill="{_svg_color(p.get("fill"))}" stroke="{_svg_color(p.get("stroke"))}" '
                f'stroke-width="{p.get("sw",T.SW_MED):.3f}"{_svg_dash(p.get("dash"))}/>'
            )
        elif op == "poly":
            pts = " ".join(f"{x:.3f},{y:.3f}" for x, y in p["pts"])
            tag = "polygon" if p.get("close", True) else "polyline"
            out.append(
                f'<{tag} points="{pts}" fill="{_svg_color(p.get("fill"))}" '
                f'stroke="{_svg_color(p.get("stroke"))}" stroke-width="{p.get("sw",T.SW_MED):.3f}"'
                f'{_svg_dash(p.get("dash"))}/>'
            )
        elif op == "circle":
            out.append(
                f'<circle cx="{p["cx"]:.3f}" cy="{p["cy"]:.3f}" r="{max(p["r"],0):.3f}" '
                f'fill="{_svg_color(p.get("fill"))}" stroke="{_svg_color(p.get("stroke"))}" '
                f'stroke-width="{p.get("sw",T.SW_MED):.3f}"{_svg_dash(p.get("dash"))}/>'
            )
        elif op == "line":
            cap = p.get("cap", "round")
            out.append(
                f'<line x1="{p["x1"]:.3f}" y1="{p["y1"]:.3f}" x2="{p["x2"]:.3f}" '
                f'y2="{p["y2"]:.3f}" stroke="{_svg_color(p.get("stroke"))}" '
                f'stroke-width="{p.get("sw",T.SW_MED):.3f}" stroke-linecap="{cap}"'
                f'{_svg_dash(p.get("dash"))}/>'
            )
        elif op == "path":
            d = []
            for seg in p["segs"]:
                k = seg[0]
                if k == "M":
                    d.append(f"M {seg[1]:.3f} {seg[2]:.3f}")
                elif k == "L":
                    d.append(f"L {seg[1]:.3f} {seg[2]:.3f}")
                elif k == "C":
                    d.append(f"C {seg[1]:.3f} {seg[2]:.3f} {seg[3]:.3f} {seg[4]:.3f} "
                             f"{seg[5]:.3f} {seg[6]:.3f}")
                elif k == "Z":
                    d.append("Z")
            out.append(
                f'<path d="{" ".join(d)}" fill="{_svg_color(p.get("fill"))}" '
                f'stroke="{_svg_color(p.get("stroke"))}" stroke-width="{p.get("sw",T.SW_MED):.3f}"'
                f'{_svg_dash(p.get("dash"))}/>'
            )
        elif op == "text":
            anchor = {"start": "start", "middle": "middle", "end": "end"}.get(
                p.get("anchor", "start"), "start")
            weight = "font-weight=\"700\" " if p.get("weight") == "bold" else ""
            rot = ""
            if p.get("rot"):
                rot = f' transform="rotate({p["rot"]:.2f} {p["x"]:.3f} {p["y"]:.3f})"'
            esc = (str(p["s"]).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            out.append(
                f'<text x="{p["x"]:.3f}" y="{p["y"]:.3f}" font-size="{p["size"]:.3f}" '
                f'fill="{_svg_color(p.get("fill"))}" text-anchor="{anchor}" {weight}'
                f' dominant-baseline="alphabetic"{rot}>{esc}</text>'
            )

    out.append("</g></svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# reportlab backend (vector, for the PDF)
# ---------------------------------------------------------------------------
def to_reportlab(prims: List[dict], w: float = T.SHEET_W, h: float = T.SHEET_H):
    """Return a reportlab.graphics.shapes.Drawing.

    reportlab's origin is bottom-left, ours is top-left, so every y is flipped.
    Text baseline semantics match (both place the baseline at y).
    """
    from reportlab.graphics.shapes import Drawing, Rect, Polygon, Circle, Line, Path, String
    from reportlab.lib.colors import HexColor

    def C(c):
        if not c or c == "none":
            return None
        return HexColor(c)

    d = Drawing(w, h)
    added = []

    def push(item):
        # later prims paint on top: reportlab draws in insertion order, so we
        # collect and add in order at the end (keeps z-order identical to SVG)
        added.append(item)

    for p in prims:
        op = p["op"]
        fill = C(p.get("fill"))
        stroke = C(p.get("stroke"))
        sw = p.get("sw", T.SW_MED)
        dash = p.get("dash")

        def style(obj):
            # reportlab shape classes expose different subsets of attributes
            # (Line has no fillColor, String has no stroke...), so guard each.
            if hasattr(obj, "fillColor"):
                obj.fillColor = fill
            if hasattr(obj, "strokeColor"):
                if stroke is not None:
                    obj.strokeColor = stroke
                    obj.strokeWidth = sw
                else:
                    obj.strokeColor = None
                    obj.strokeWidth = 0
                if dash:
                    obj.strokeDashArray = list(dash)
            return obj

        if op == "rect":
            r = Rect(p["x"], h - p["y"] - p["h"], max(p["w"], 0), max(p["h"], 0))
            if p.get("rx"):
                r.rx = min(p["rx"], p["w"] / 2.0, p["h"] / 2.0)
            push(style(r))

        elif op == "poly":
            pts = []
            for x, y in p["pts"]:
                pts.extend([x, h - y])
            poly = Polygon(pts)
            poly.strokeLineJoin = 1
            push(style(poly))

        elif op == "circle":
            push(style(Circle(p["cx"], h - p["cy"], max(p["r"], 0))))

        elif op == "line":
            ln = Line(p["x1"], h - p["y1"], p["x2"], h - p["y2"])
            if p.get("cap") == "butt":
                ln.strokeLineCap = 0
            else:
                ln.strokeLineCap = 1
            push(style(ln))

        elif op == "path":
            pa = Path()
            for seg in p["segs"]:
                k = seg[0]
                if k == "M":
                    pa.moveTo(seg[1], h - seg[2])
                elif k == "L":
                    pa.lineTo(seg[1], h - seg[2])
                elif k == "C":
                    pa.curveTo(seg[1], h - seg[2], seg[3], h - seg[4], seg[5], h - seg[6])
                elif k == "Z":
                    pa.closePath()
            push(style(pa))

        elif op == "text":
            anchor = {"start": "start", "middle": "middle", "end": "end"}.get(
                p.get("anchor", "start"), "start")
            st = String(p["x"], h - p["y"], str(p["s"]))
            st.fontName = "Courier-Bold" if p.get("weight") == "bold" else "Courier"
            st.fontSize = p["size"]
            st.fillColor = C(p.get("fill")) or HexColor("#000000")
            st.textAnchor = anchor
            push(st)

    for a in added:
        d.add(a)
    return d
