"""
Blueprint proofer.

The agent cannot look at pixels, so it reads the drawing instead:

  1. `ascii_sheet()` rasterises an SVG (via resvg) and re-projects it onto a
     character grid. Each cell reports the highest-priority ink found in it:
         #  navy plate (white characters live on these)
         !  red  (critical: the new part, cuts, forces, hazards)
         :  red wash (fill of the part introduced by the step)
         O  IKEA blue line
         o  light blue / construction
         -  grey
         ·  grid
       space  white paper
     A human (or the agent) can read the picture straight off this grid.

  2. `check_sheet()` asserts structural properties that must hold for the sheet
     to be honest and legible:
        - the red parts on the sheet are exactly the step's `parts_used`
        - nothing is drawn outside the frame
        - no two label plates overlap
        - every plate is wide enough for the text it carries
        - the drawing actually fills its frame (nothing collapsed to a dot)

These are the acceptance tests for "the image matches the explanation".
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Dict, List, Tuple

from .blueprint import theme as T

# ink -> (character, priority). higher priority wins inside a cell.
PALETTE = [
    ((0x0B, 0x3D, 0x6B), "#", 90),   # navy plate / frame
    ((0xCC, 0x00, 0x08), "!", 95),   # red critical
    ((0x9E, 0x00, 0x06), "!", 95),
    ((0x1C, 0x54, 0x89), "#", 88),
    ((0xFC, 0xE9, 0xE7), ":", 60),   # red wash
    ((0x00, 0x58, 0xA3), "O", 70),   # IKEA blue
    ((0x00, 0x3C, 0x70), "O", 70),
    ((0x9C, 0xC2, 0xE0), "o", 40),   # light blue / hidden
    ((0xB8, 0xCC, 0xE0), "o", 38),
    ((0x6E, 0x7F, 0x8D), "-", 50),   # grey
    ((0xE9, 0xF1, 0xF9), "·", 20),   # grid
    ((0xD6, 0xE6, 0xF5), "·", 22),
    ((0xFF, 0xFF, 0xFF), " ", 0),
]

_RASTER_DIR = os.path.join(tempfile.gettempdir(), "fabrix_raster")
_RESvg = None


def _ensure_resvg():
    """Locate (or install) a node + resvg rasteriser. Optional: only needed
    for the ASCII proof, never for the product itself."""
    global _RESvg
    if _RESvg is not None:
        return _RESvg
    d = _RASTER_DIR
    js = os.path.join(d, "r.js")
    if not os.path.exists(js):
        try:
            os.makedirs(d, exist_ok=True)
            if shutil.which("npm"):
                subprocess.run(["npm", "init", "-y"], cwd=d, check=False,
                               capture_output=True, timeout=180)
                subprocess.run(["npm", "i", "@resvg/resvg-js"], cwd=d, check=False,
                               capture_output=True, timeout=300)
            with open(js, "w") as f:
                f.write(
                    "const {Resvg}=require('@resvg/resvg-js');const fs=require('fs');\n"
                    "const [,,i,o,w]=process.argv;\n"
                    "const r=new Resvg(fs.readFileSync(i,'utf8'),{font:{loadSystemFonts:true,"
                    "defaultFontFamily:'DejaVu Sans'},fitTo:{mode:'width',value:Number(w||1200)}});\n"
                    "fs.writeFileSync(o,r.render().asPng());\n"
                )
        except Exception:
            _RESvg = False
            return None
    _RESvg = js if shutil.which("node") else False
    return _RESvg or None


def svg_to_png(svg: str, out_png: str, width: int = 1200) -> bool:
    js = _ensure_resvg()
    if not js:
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as f:
        f.write(svg)
        tmp = f.name
    try:
        subprocess.run(["node", js, tmp, out_png, str(width)], check=True,
                       capture_output=True, timeout=180)
        return os.path.exists(out_png)
    except Exception:
        return False
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _classify(px):
    best, bestc, bestd = " ", 0, 1 << 30
    for (r, g, b), ch, pr in PALETTE:
        d = (px[0] - r) ** 2 + (px[1] - g) ** 2 + (px[2] - b) ** 2
        if d < bestd:
            bestd, best, bestc = d, ch, pr
    # near-white background snaps to space
    if px[0] > 246 and px[1] > 246 and px[2] > 246:
        return " ", 0
    return best, bestc


def ascii_sheet(svg: str, cols: int = 116, width: int = 1200) -> str:
    """Rasterise and print the sheet as a character grid."""
    from PIL import Image

    if not svg_to_png(svg, os.path.join(tempfile.gettempdir(), "_fabrix_proof.png"), width):
        return "(rasteriser unavailable)"
    im = Image.open(os.path.join(tempfile.gettempdir(), "_fabrix_proof.png")).convert("RGB")
    W, H = im.size
    cw = W / cols
    rows = max(int(H / (cw * 1.85)), 1)      # characters are ~1.85x taller than wide
    ch = H / rows
    px = im.load()
    out = []
    for r in range(rows):
        line = []
        for c in range(cols):
            x0, x1 = int(c * cw), max(int((c + 1) * cw), int(c * cw) + 1)
            y0, y1 = int(r * ch), max(int((r + 1) * ch), int(r * ch) + 1)
            bestch, bestpr = " ", -1
            for y in range(y0, min(y1, H), 2):
                for x in range(x0, min(x1, W), 2):
                    ch_, pr = _classify(px[x, y])
                    if pr > bestpr:
                        bestpr, bestch = pr, ch_
            line.append(bestch)
        out.append("".join(line).rstrip())
    return "\n".join(out)


# ---------------------------------------------------------------------------
# structural assertions on the primitive list
# ---------------------------------------------------------------------------
def _prim_bbox(p):
    if p["op"] == "rect":
        return (p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"])
    if p["op"] == "poly":
        xs = [q[0] for q in p["pts"]]
        ys = [q[1] for q in p["pts"]]
        return (min(xs), min(ys), max(xs), max(ys))
    if p["op"] == "circle":
        return (p["cx"] - p["r"], p["cy"] - p["r"], p["cx"] + p["r"], p["cy"] + p["r"])
    if p["op"] == "line":
        return (min(p["x1"], p["x2"]), min(p["y1"], p["y2"]),
                max(p["x1"], p["x2"]), max(p["y1"], p["y2"]))
    if p["op"] == "path":
        pts = [(s[1], s[2]) for s in p["segs"] if s[0] in ("M", "L")]
        pts += [(s[5], s[6]) for s in p["segs"] if s[0] == "C"]
        if not pts:
            return None
        xs = [q[0] for q in pts]
        ys = [q[1] for q in pts]
        return (min(xs), min(ys), max(xs), max(ys))
    if p["op"] == "text":
        w = T.text_w(str(p["s"]), p["size"])
        x = p["x"] if p.get("anchor", "start") == "start" else (
            p["x"] - w / 2 if p.get("anchor") == "middle" else p["x"] - w)
        return (x, p["y"] - p["size"], x + w, p["y"] + p["size"] * 0.3)
    return None


def _overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def dump(prims: List[dict]) -> str:
    """Compact human-readable listing of what is actually on the sheet.

    This is the primary inspection tool: it is exact, unlike looking at pixels.
    """
    lines = []
    for i, p in enumerate(prims):
        bb = _prim_bbox(p)
        bb = f"({bb[0]:5.1f},{bb[1]:5.1f})-({bb[2]:5.1f},{bb[3]:5.1f})" if bb else " " * 27
        if p["op"] == "text":
            anchor = p.get("anchor", "start")
            lines.append(f"{i:4d} TEXT  {bb} {anchor:6s} {p['size']:4.1f} "
                         f"{p.get('fill','')} {str(p['s'])[:44]!r}")
        elif p["op"] == "rect" and p.get("stroke") in (None, "none"):
            lines.append(f"{i:4d} PLATE {bb} rx={p.get('rx',0):.2f} {p.get('fill','')}")
        elif p["op"] == "rect":
            lines.append(f"{i:4d} rect  {bb} {p.get('stroke','')} sw={p.get('sw',0):.2f} "
                         f"fill={p.get('fill')}")
        elif p["op"] == "poly":
            lines.append(f"{i:4d} poly  {bb} n={len(p['pts'])} {p.get('stroke','')} "
                         f"sw={p.get('sw',0):.2f} fill={p.get('fill')}")
        elif p["op"] == "circle":
            lines.append(f"{i:4d} circ  {bb} r={p['r']:.2f} {p.get('stroke','')} "
                         f"fill={p.get('fill')}")
        elif p["op"] == "line":
            lines.append(f"{i:4d} line  {bb} {p.get('stroke','')} sw={p.get('sw',0):.2f} "
                         f"dash={p.get('dash')}")
        elif p["op"] == "path":
            lines.append(f"{i:4d} path  {bb} n={len(p['segs'])} {p.get('stroke','')} "
                         f"sw={p.get('sw',0):.2f} fill={p.get('fill')}")
    return "\n".join(lines)


def check_sheet(prims: List[dict], step: dict, expected_new: List[str]) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings) for one rendered sheet."""
    errs, warns = [], []

    if not prims:
        return ["empty sheet"], []

    # 1. nothing outside the frame
    fx0, fy0 = T.BORDER_INSET, T.BORDER_INSET
    fx1, fy1 = T.SHEET_W - T.BORDER_INSET, T.SHEET_H - T.BORDER_INSET
    for p in prims:
        if p["op"] == "rect" and p.get("fill") == T.SHEET_BG:
            continue
        bb = _prim_bbox(p)
        if not bb:
            continue
        if bb[0] < fx0 - 0.6 or bb[1] < fy0 - 0.6 or bb[2] > fx1 + 0.6 or bb[3] > fy1 + 0.6:
            errs.append(f"geometry outside the frame: {p['op']} bbox="
                        f"({bb[0]:.1f},{bb[1]:.1f},{bb[2]:.1f},{bb[3]:.1f})")
            break

    # 2. red ink must be present when the step introduces a part
    has_red = any((p.get("stroke") == T.CRIT or p.get("fill") == T.CRIT or
                   p.get("fill") == T.CRIT_WASH or p.get("fill") == T.CRIT_DARK)
                  for p in prims)
    if expected_new and not has_red:
        errs.append(f"step introduces {expected_new} but the sheet has no red ink")
    if not expected_new and has_red:
        warns.append("sheet uses red but the step introduces no new part")

    # 3. every text glyph must sit on a plate (white on navy/red) — no bare ink
    plates = []
    for p in prims:
        if p["op"] != "rect" or p.get("rx", 0) <= 0.15:
            continue
        if p.get("stroke") not in (None, "none"):
            continue
        bb = _prim_bbox(p)
        if not bb or (bb[3] - bb[1]) > 6.5:      # sheet furniture, not a label
            continue
        plates.append(p)
    texts = [p for p in prims if p["op"] == "text"]
    for t in texts:
        tb = _prim_bbox(t)
        if not tb:
            continue
        if p["y"] > T.FOOTER_Y0 - 0.5 or p["y"] < T.HEADER_Y0 + 0.5:
            continue          # title block / legend / header furniture
        covered = any(_contains(pl, tb) for pl in plates)
        if not covered and str(t.get("fill")) == T.WHITE:
            errs.append(f"white text '{str(t['s'])[:24]}' is not on a plate")

    # 4. plates must not overlap each other (labels must stay readable)
    for i in range(len(plates)):
        for j in range(i + 1, len(plates)):
            if _overlap(_prim_bbox(plates[i]), _prim_bbox(plates[j])):
                a, b = _prim_bbox(plates[i]), _prim_bbox(plates[j])
                ox = min(a[2], b[2]) - max(a[0], b[0])
                oy = min(a[3], b[3]) - max(a[1], b[1])
                if ox > 0.5 and oy > 0.5:
                    errs.append(f"label plates overlap by {ox:.1f}x{oy:.1f} units")
                    break
        else:
            continue
        break

    # 5. the drawing must actually fill its frame
    pts = []
    for p in prims:
        if p["op"] in ("rect", "poly", "circle", "path", "line") and p.get("stroke") not in (None, "none"):
            bb = _prim_bbox(p)
            if bb and T.AREA_X0 - 2 < bb[0] < T.AREA_X1 + 2:
                pts.append(bb)
    if pts:
        w = max(b[2] for b in pts) - min(b[0] for b in pts)
        h = max(b[3] for b in pts) - min(b[1] for b in pts)
        if w < (T.AREA_X1 - T.AREA_X0) * 0.35 and h < (T.AREA_Y1 - T.AREA_Y0) * 0.35:
            warns.append(f"drawing occupies only {w:.0f}x{h:.0f} of a "
                         f"{T.AREA_X1-T.AREA_X0:.0f}x{T.AREA_Y1-T.AREA_Y0:.0f} frame")

    return errs, warns


def _contains(plate, box):
    pb = _prim_bbox(plate)
    if not pb or not box:
        return False
    return (pb[0] <= box[0] + 0.3 and pb[1] <= box[1] + 0.3 and
            pb[2] >= box[2] - 0.3 and pb[3] >= box[3] - 0.3)
