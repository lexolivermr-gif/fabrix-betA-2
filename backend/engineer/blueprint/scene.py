"""
Scene builder:  (parts table + step drawing intent)  ->  primitive list.

Coherence rules enforced here, structurally:

  1. A part's SIZE comes from the parts table (length_mm / width_mm) through one
     global mm->unit scale. Every step draws the same part at the same size, and
     parts are in true relative proportion to each other. The prose cannot claim
     "150 mm" while the drawing shows a different length.
  2. A part's LABEL comes from the parts table. The bubble on the drawing says
     exactly the ref and name listed in the materials list.
  3. A DIMENSION's text is generated from the parts table, never hand-typed.
  4. The fit is computed, so a sloppy coordinate still lands on the sheet.

Everything is deterministic. No model, no sampling, no randomness: the same
spec always produces the same drawing.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from . import theme as T
from .prims import to_svg, to_reportlab  # noqa: F401  (re-exported)

SCENE = 100.0            # scene space is 0..SCENE x 0..SCENE (square, uniform)
PRINT_W_MM = 172.0       # printed width of a sheet in the PDF (sets the scale label)
_FITS = {}               # spec["fits"] — single source for design constants
MAX_PART_UNITS = 46.0    # the largest part dimension maps to this many scene units


# ---------------------------------------------------------------------------
# small geometry helpers
# ---------------------------------------------------------------------------
def _rot(x: float, y: float, deg: float) -> Tuple[float, float]:
    a = math.radians(deg or 0.0)
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


def _place(pts, x, y, rot):
    return [(px + x, py + y) for px, py in (_rot(a, b, rot) for a, b in pts)]


def _bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _arrow_head(x1, y1, x2, y2, size=1.9):
    dx, dy = x2 - x1, y2 - y1
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    px, py = -dy, dx
    bx, by = x2 - dx * size * 0.92, y2 - dy * size * 0.92
    return [(x2, y2),
            (bx + px * size * 0.42, by + py * size * 0.42),
            (bx - px * size * 0.42, by - py * size * 0.42)]


def _dash_for(role: str):
    return (1.4, 1.0) if role == "ghost" else None


def _poly_hatch(pts, spacing=1.5, angle=45.0):
    """Scanline hatch clipped to an arbitrary simple polygon."""
    x0, y0, x1, y1 = _bbox(pts)
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        return []
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    # rotate polygon into hatch space
    rp = [(px * dx + py * dy, -px * dy + py * dx) for px, py in pts]
    rx0 = min(p[0] for p in rp)
    rx1 = max(p[0] for p in rp)
    ry0 = min(p[1] for p in rp)
    ry1 = max(p[1] for p in rp)
    n = len(rp)
    segs = []
    k = math.ceil(rx0 / spacing)
    while k * spacing <= rx1:
        X = k * spacing
        xs = []
        for i in range(n):
            ax, ay = rp[i]
            bx, by = rp[(i + 1) % n]
            if (ax - X) * (bx - X) < 0:
                t = (X - ax) / (bx - ax)
                xs.append(ay + t * (by - ay))
            elif ax == X:
                xs.append(ay)
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            segs.append((X, xs[j], xs[j + 1]))
        k += 1
    out = []
    for X, ya, yb in segs:
        out.append((X * dx - ya * dy, X * dy + ya * dx))
        out.append((X * dx - yb * dy, X * dy + yb * dx))
    return out


# ---------------------------------------------------------------------------
# plate / label helpers  (white characters on a navy or red plate)
# ---------------------------------------------------------------------------
PLATE_BG = {"navy": T.NAVY, "red": T.CRIT, "blue": T.INK, "grey": T.GREY,
            "dark": T.NAVY_SOFT}


def _plate(out, cx, cy, s, size, kind="navy", pad_h=0.55, pad_v=0.44,
           weight="bold", anchor="middle"):
    w = T.text_w(s, size) + 2.0 * pad_h * size
    h = size * (1.0 + 2.0 * pad_v)
    if anchor == "middle":
        x = cx - w / 2.0
    elif anchor == "end":
        x = cx - w
    else:
        x = cx
    out.append({"op": "rect", "x": x, "y": cy - h / 2.0, "w": w, "h": h,
                "rx": h * 0.24, "fill": PLATE_BG.get(kind, T.NAVY),
                "stroke": "none", "sw": 0})
    tx = x + w / 2.0
    out.append({"op": "text", "x": tx, "y": cy + size * 0.35, "s": s, "size": size,
                "fill": T.WHITE, "anchor": "middle", "weight": weight})
    return w, h


def _leader(out, x1, y1, x2, y2, color=T.INK, sw=T.SW_THIN, dash=None):
    out.append({"op": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "stroke": color, "sw": sw, "dash": dash, "cap": "round"})


# ---------------------------------------------------------------------------
# label placement: never collide, never leave the sheet
# ---------------------------------------------------------------------------
SAFE = (2.6, 8.6, 97.4, 51.9)   # x0,y0,x1,y1 a plate rect must stay inside


class Placer:
    """Greedy collision-avoiding label placer.

    A blueprint is only readable if every label is readable. Labels are placed
    by the model only as a *hint*; this class has the final say and will slide
    a label to the nearest free slot, keeping a hairline leader back to the
    thing it names.
    """

    def __init__(self):
        self.hard = []     # other plates + sheet furniture (never overlap)
        self.soft = []     # part geometry (prefer not to cover)

    def add_hard(self, r):
        self.hard.append(r)

    def add_soft(self, r):
        self.soft.append(r)

    @staticmethod
    def _ov(a, b):
        ox = min(a[2], b[2]) - max(a[0], b[0])
        oy = min(a[3], b[3]) - max(a[1], b[1])
        return (ox, oy) if (ox > 0 and oy > 0) else (0.0, 0.0)

    def _cost(self, r, want):
        ox, oy = 0.0, 0.0
        for h in self.hard:
            a, b = self._ov(r, h)
            ox, oy = max(ox, a), max(oy, b)
        if ox > 0.25 and oy > 0.25:
            return (1e6 + ox * oy, 0.0)
        s = 0.0
        for h in self.soft:
            a, b = self._ov(r, h)
            if a > 0.4 and b > 0.4:
                s += a * b
        # stay inside the safe box
        pen = 0.0
        if r[0] < SAFE[0]:
            pen += (SAFE[0] - r[0]) * 60
        if r[1] < SAFE[1]:
            pen += (SAFE[1] - r[1]) * 60
        if r[2] > SAFE[2]:
            pen += (r[2] - SAFE[2]) * 60
        if r[3] > SAFE[3]:
            pen += (r[3] - SAFE[3]) * 60
        d = math.hypot((r[0] + r[2]) / 2 - want[0], (r[1] + r[3]) / 2 - want[1])
        return (pen + s * 3.0, d)

    def place(self, w, h, want, anchor="middle"):
        """Return the centre for a w x h label that wants to be at `want`."""
        def rect(cx, cy):
            x0 = cx - w / 2 if anchor == "middle" else (cx if anchor == "start" else cx - w)
            return (x0, cy - h / 2, x0 + w, cy + h / 2)

        best = None
        rings = 26
        for i in range(rings):
            step = 0.0 if i == 0 else (1 + (i - 1) // 8) * (h * 1.15)
            angs = [(0, 0)] if i == 0 else None
            if i > 0:
                k = i - 1
                base = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]
                angs = [base[k % 8]]
            for (dx, dy) in angs:
                cx = want[0] + dx * (step if dx else 0)
                cy = want[1] + dy * (step if dy else 0)
                r = rect(cx, cy)
                c = self._cost(r, want)
                if best is None or c < best[0]:
                    best = (c, (cx, cy), r)
            if best and best[0][0] < 0.01 and i >= 2:
                break
        _, (cx, cy), r = best
        self.hard.append(r)
        return cx, cy, r

    def plate(self, out, cx, cy, s, size, kind="navy", pad_h=0.55, pad_v=0.44,
              weight="bold", anchor="middle", anchor_to=None, lead=True,
              color=None):
        w = T.text_w(s, size) + 2.0 * pad_h * size
        h = size * (1.0 + 2.0 * pad_v)
        fx, fy, r = self.place(w, h, (cx, cy), anchor)
        bg = PLATE_BG.get(kind, T.NAVY)
        x0 = fx - w / 2 if anchor == "middle" else (fx if anchor == "start" else fx - w)
        out.append({"op": "rect", "x": x0, "y": fy - h / 2, "w": w, "h": h,
                    "rx": h * 0.24, "fill": bg, "stroke": "none", "sw": 0})
        out.append({"op": "text", "x": x0 + w / 2, "y": fy + size * 0.35, "s": s,
                    "size": size, "fill": T.WHITE, "anchor": "middle", "weight": weight})
        if lead and anchor_to:
            ax, ay = anchor_to
            ex, ey = _clamp_to_rect(r, ax, ay)
            col = color or (T.CRIT if kind == "red" else T.INK)
            out.append({"op": "line", "x1": ex, "y1": ey, "x2": ax, "y2": ay,
                        "stroke": col, "sw": T.SW_HAIR, "dash": (0.8, 0.8), "cap": "round"})
            out.append({"op": "circle", "cx": ax, "cy": ay, "r": 0.42,
                        "fill": col, "stroke": "none", "sw": 0})
        return w, h


def _clamp_to_rect(r, ax, ay):
    cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
    dx, dy = ax - cx, ay - cy
    if dx == 0 and dy == 0:
        return cx, cy
    hw, hh = (r[2] - r[0]) / 2 + 0.25, (r[3] - r[1]) / 2 + 0.25
    t = 1.0
    if dx:
        t = min(t, hw / abs(dx))
    if dy:
        t = min(t, hh / abs(dy))
    return cx + dx * t, cy + dy * t


# ---------------------------------------------------------------------------
# part geometry  (local coords, centred on origin, long axis along X)
# ---------------------------------------------------------------------------
def part_local_ops(part, L, W, sh=None):
    """Return list of (op, params) in local coords for one part.

    `sh` is the placement entry from the step drawing; it lets a part be drawn
    as a curved / flexed body (a strung prod is NOT straight) whose coordinates
    are given in scene space instead of as a plain rectangle.
    """
    sh = sh or {}
    shape = (part.get("shape") or "bar").lower()
    thick = max(min(W * 0.34, L * 0.16), 0.7)

    if shape in ("curve", "flex", "flexed") and sh.get("pts"):
        pts = [(float(a), float(b)) for a, b in sh["pts"]]
        w = float(sh.get("wid", W) or W)
        return [("poly", {"pts": _thick_polyline(pts, w), "_abs": True})]

    if shape in ("cord", "string", "thread", "line_part") and sh.get("pts"):
        pts = [(float(a), float(b)) for a, b in sh["pts"]]
        return [("poly", {"pts": pts, "_abs": True, "_open": True})]

    if shape in ("bar", "plate", "block", "strip", "board"):
        return [("rect", {"x": -L / 2, "y": -W / 2, "w": L, "h": W, "rx": min(W, L) * 0.06})]

    if shape in ("rod", "dowel", "bolt"):
        r = W / 2.0
        return [("path", {"segs": _capsule_segs(-L / 2 + r, 0, L / 2 - r, 0, r)})]

    if shape in ("tube", "sleeve", "barrel"):
        return [("rect", {"x": -L / 2, "y": -W / 2, "w": L, "h": W, "rx": 0.2}),
                ("rect", {"x": -L / 2 + thick * 0.5, "y": -W / 2 + thick * 0.62,
                          "w": L - thick, "h": max(W - thick * 1.24, 0.3), "rx": 0.1,
                          "_inner": True})]

    if shape in ("disc", "wheel", "washer", "coin"):
        return [("circle", {"cx": 0, "cy": 0, "r": max(L / 2.0, 0.5)})]

    if shape in ("ring", "o_ring"):
        r = max(L / 2.0, 0.6)
        return [("circle", {"cx": 0, "cy": 0, "r": r}),
                ("circle", {"cx": 0, "cy": 0, "r": max(r * 0.55, 0.25), "_inner": True})]

    if shape in ("band", "elastic", "loop", "rubber_band"):
        r = W / 2.0
        return [("path", {"segs": _capsule_segs(-L / 2 + r, 0, L / 2 - r, 0, r),
                          "_outline": True})]

    if shape in ("spring", "coil"):
        return [("path", {"segs": _spring_segs(L, W)})]

    if shape in ("wedge", "triangle"):
        return [("poly", {"pts": [(-L / 2, -W / 2), (L / 2, 0), (-L / 2, W / 2)]})]

    if shape in ("screw", "pin", "nail", "rivet"):
        r = max(min(L, W) / 2.0, 0.5)
        return [("circle", {"cx": 0, "cy": 0, "r": r}),
                ("line", {"x1": -r * 0.6, "y1": 0, "x2": r * 0.6, "y2": 0, "_inner": True}),
                ("line", {"x1": 0, "y1": -r * 0.6, "x2": 0, "y2": r * 0.6, "_inner": True})]

    if shape in ("clip", "binder", "clamp", "u"):
        return [("path", {"segs": _u_segs(L, W, thick)})]

    if shape in ("hook", "l"):
        return [("path", {"segs": _l_segs(L, W, thick)})]

    if shape == "poly":
        pts = part.get("outline") or [[-L / 2, -W / 2], [L / 2, -W / 2], [L / 2, W / 2], [-L / 2, W / 2]]
        return [("poly", {"pts": [(p[0] * L / 100.0, p[1] * W / 100.0) for p in pts]})]

    return [("rect", {"x": -L / 2, "y": -W / 2, "w": L, "h": W, "rx": 0.2})]


def _thick_polyline(pts, w):
    """Offset a polyline into a closed polygon of constant width."""
    if len(pts) < 2:
        return list(pts)
    n = len(pts)
    left, right = [], []
    for i, (px, py) in enumerate(pts):
        if i == 0:
            dx, dy = pts[1][0] - px, pts[1][1] - py
        elif i == n - 1:
            dx, dy = px - pts[i - 1][0], py - pts[i - 1][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        left.append((px + nx * w / 2.0, py + ny * w / 2.0))
        right.append((px - nx * w / 2.0, py - ny * w / 2.0))
    return left + right[::-1]


def _capsule_segs(x1, y1, x2, y2, r):
    dx, dy = x2 - x1, y2 - y1
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    px, py = -uy * r, ux * r
    return [("M", x1 + px, y1 + py),
            ("L", x2 + px, y2 + py),
            ("C", x2 + px + ux * r, y2 + py + uy * r, x2 + px + ux * r, y2 - py + uy * r,
             x2 - px, y2 - py),
            ("L", x1 - px, y1 - py),
            ("C", x1 - px - ux * r, y1 - py - uy * r, x1 - px - ux * r, y1 + py - uy * r,
             x1 + px, y1 + py),
            ("Z",)]


def _spring_segs(L, W):
    n = max(int(L / max(W * 0.9, 1.2)), 3)
    segs = [("M", -L / 2, 0)]
    step = L / n
    for i in range(n):
        x0 = -L / 2 + i * step
        segs.append(("L", x0 + step * 0.25, -W / 2))
        segs.append(("L", x0 + step * 0.75, W / 2))
        segs.append(("L", x0 + step, 0))
    return segs


def _u_segs(L, W, t):
    r = min(W, L) / 2.0
    return [("M", -L / 2, -W / 2), ("L", L / 2 - r, -W / 2),
            ("C", L / 2, -W / 2, L / 2, -W / 2 + r * 0.2, L / 2, 0),
            ("C", L / 2, W / 2 - r * 0.2, L / 2, W / 2, L / 2 - r, W / 2),
            ("L", -L / 2, W / 2)]


def _l_segs(L, W, t):
    return [("M", -L / 2, -W / 2), ("L", -L / 2 + t, -W / 2),
            ("L", -L / 2 + t, W / 2 - t), ("L", L / 2, W / 2 - t),
            ("L", L / 2, W / 2), ("L", -L / 2, W / 2), ("Z",)]


# ---------------------------------------------------------------------------
# the sheet
# ---------------------------------------------------------------------------
def spec_fits(step: dict) -> Dict[str, float]:
    """Design constants for this build (gap, brace height, draw length...).

    Dimensions in a drawing may only come from the parts table or from here,
    so a number on the sheet always traces back to a declared value.
    """
    f = {}
    raw = (step.get("_fits") or {})
    for k, v in raw.items():
        if isinstance(v, dict):
            f[k] = v.get("value")
        else:
            f[k] = v
    return {k: v for k, v in f.items() if isinstance(v, (int, float))}


def build_sheet(step: dict, parts_by_ref: Dict[str, dict], meta: dict) -> List[dict]:
    """step = one step dict from the spec (needs 'drawing'); meta = project info."""
    d = step.get("drawing") or {}
    view = (d.get("view") or "detail").upper()
    caption = d.get("caption") or ""

    global _FITS
    _FITS = spec_fits(step)

    out: List[dict] = []

    # ---- label placer: sheet furniture is never overwriteable --------------
    placer = Placer()
    placer.add_hard((1.6, 2.2, 98.4, 8.2))        # header band
    placer.add_hard((56.0, 51.6, 98.4, 61.9))     # title block
    placer.add_hard((1.6, 51.6, 56.0, 61.9))      # legend band

    # ---- mm -> scene units -------------------------------------------------
    # Every sheet is authored in MILLIMETRES. One scene unit == 1 mm.
    # The auto-fit then scales the sheet to the frame, and the resulting ratio
    # is printed in the title block as the sheet scale, exactly like a real
    # drawing. Authoring in mm removes a whole class of unit mistakes.
    mm2u = 1.0

    shapes = d.get("shapes") or []
    placed: Dict[str, dict] = {}

    # ---- split into geometry (scaled) and annotations (constant-size) ------
    geo: List[dict] = []          # basic prims in scene coords
    zmap = {"ghost": 0, "base": 1, "new": 2, "cut": 3}
    raw_geo = []

    for sh in shapes:
        k = (sh.get("k") or "").lower()
        if k in ("part", "rect", "bar", "rod", "plate", "disc", "band", "block",
                 "circle", "ring", "spring", "wedge", "screw", "tube", "clip", "hook"):
            ref = sh.get("ref")
            part = parts_by_ref.get(ref) or {}
            L = float(sh.get("len") or (part.get("length_mm") or 40) * mm2u)
            W = float(sh.get("wid") or (part.get("width_mm") or max((part.get("length_mm") or 40) * 0.2, 4)) * mm2u)
            if sh.get("wid_mm"):
                W = float(sh["wid_mm"]) * mm2u
            if sh.get("len_mm"):
                L = float(sh["len_mm"]) * mm2u
            role = (sh.get("role") or ("new" if ref in (step.get("parts_used") or []) else "base")).lower()
            pshape = sh.get("shape") or part.get("shape") or "bar"
            x, y = float(sh.get("x", 50)), float(sh.get("y", 50))
            rot = float(sh.get("rot", 0))
            ax, ay = x, y
            if pshape in ("curve", "flex", "flexed", "cord", "string", "thread", "line_part") \
                    and sh.get("pts"):
                x = y = 0.0
                rot = 0.0
                _pts = [(float(a), float(b)) for a, b in sh["pts"]]
                ax = sum(a for a, _ in _pts) / len(_pts)
                ay = sum(b for _, b in _pts) / len(_pts)
            placed[ref or f"_{len(placed)}"] = {"x": x, "y": y, "rot": rot, "L": L, "W": W,
                                                "ref": ref, "role": role, "ax": ax, "ay": ay}
            ops = part_local_ops({**part, "shape": pshape}, L, W, sh)
            raw_geo.append((zmap.get(role, 1), ref, x, y, rot, ops, role, sh))

    # ---- collect annotation anchor points for the bbox ---------------------
    anchors: List[Tuple[float, float]] = []

    def _anch(sh, keys):
        for kk in keys:
            if sh.get(kk) is not None:
                v = sh[kk]
                if isinstance(v, (int, float)):
                    pass
        if isinstance(sh.get("x"), (int, float)) and isinstance(sh.get("y"), (int, float)):
            anchors.append((float(sh["x"]), float(sh["y"])))
        if isinstance(sh.get("x1"), (int, float)) and isinstance(sh.get("y1"), (int, float)):
            anchors.append((float(sh["x1"]), float(sh["y1"])))
        if isinstance(sh.get("x2"), (int, float)) and isinstance(sh.get("y2"), (int, float)):
            anchors.append((float(sh["x2"]), float(sh["y2"])))
        if isinstance(sh.get("to"), (list, tuple)) and len(sh["to"]) == 2:
            anchors.append((float(sh["to"][0]), float(sh["to"][1])))

    def _dim_endpoints_local(sh):
        """Resolve a dimension that is anchored to a part, in scene units."""
        ref = sh.get("ref")
        if not ref or ref not in placed:
            return None
        pl = placed[ref]
        axis = (sh.get("axis") or "length").lower()
        half = (pl["L"] if axis == "length" else pl["W"]) / 2.0
        off = float(sh.get("off", 6))
        if axis == "length":
            a = _place([(-half, -off), (half, -off)], pl["x"], pl["y"], pl["rot"])
        else:
            a = _place([(-off, -half), (-off, half)], pl["x"], pl["y"], pl["rot"])
        return a

    for sh in shapes:
        _anch(sh, ())
        if (sh.get("k") or "").lower().startswith("dim"):
            e = _dim_endpoints_local(sh)
            if e:
                anchors.extend(e)

    # ---- geometry bbox -----------------------------------------------------
    allpts: List[Tuple[float, float]] = list(anchors)
    for z, ref, x, y, rot, ops, role, sh in raw_geo:
        for op, prm in ops:
            if op == "rect":
                allpts += _place([(prm["x"], prm["y"]), (prm["x"] + prm["w"], prm["y"] + prm["h"])],
                                 x, y, rot)
            elif op == "poly":
                allpts += _place(prm["pts"], x, y, rot)
            elif op == "circle":
                r = prm["r"]
                allpts += _place([(-r, -r), (r, r)], x, y, rot)
            elif op == "path":
                pts = []
                for s in prm["segs"]:
                    if s[0] in ("M", "L"):
                        pts.append((s[1], s[2]))
                    elif s[0] == "C":
                        pts.append((s[5], s[6]))
                if pts:
                    allpts += _place(pts, x, y, rot)
            elif op == "line":
                allpts += _place([(prm["x1"], prm["y1"]), (prm["x2"], prm["y2"])], x, y, rot)
    for sh in shapes:
        if (sh.get("k") or "").lower() == "hatch":
            allpts += [(float(sh["x"]), float(sh["y"])),
                       (float(sh["x"]) + float(sh["w"]), float(sh["y"]) + float(sh["h"]))]

    # ---- fit ---------------------------------------------------------------
    AW = T.AREA_X1 - T.AREA_X0
    AH = T.AREA_Y1 - T.AREA_Y0
    if allpts:
        x0, y0, x1, y1 = _bbox(allpts)
        bw, bh = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
        s = min(AW / bw, AH / bh)
        s = min(s, 2.4)
        tx = T.AREA_X0 + (AW - bw * s) / 2.0 - x0 * s
        ty = T.AREA_Y0 + (AH - bh * s) / 2.0 - y0 * s
    else:
        s, tx, ty = 1.0, T.AREA_X0, T.AREA_Y0

    def X(v):
        return float(v) * s + tx

    def Y(v):
        return float(v) * s + ty

    def P(x, y):
        return (X(x), Y(y))

    # ---- draw geometry -----------------------------------------------------
    grid_step = 5.0 * s
    if 0.6 < grid_step < 40:
        _area_grid(out, grid_step)

    for z, ref, x, y, rot, ops, role, sh in sorted(raw_geo, key=lambda t: t[0]):
        stroke = T.INK if role != "new" else T.CRIT
        if role == "ghost":
            stroke = T.GHOST
        if role == "cut":
            stroke = T.CRIT
        fill = T.WHITE
        if role == "new":
            fill = T.CRIT_WASH
        if role == "ghost":
            fill = T.WHITE
        sw = T.SW_BOLD if role == "new" else (T.SW_THIN if role == "ghost" else T.SW_MED)
        dash = _dash_for(role)

        for op, prm in ops:
            inner = prm.get("_inner") or prm.get("_outline")
            pstroke = T.INK_LIGHT if (inner and role != "new") else stroke
            pstroke = T.CRIT if (inner and role == "new") else pstroke
            psw = T.SW_THIN if inner else sw
            pfill = (T.WHITE if prm.get("_outline") else fill) if not inner else T.WHITE
            if role == "ghost":
                pfill = T.WHITE
            if op == "rect":
                cx, cy = _rot(prm["x"] + prm["w"] / 2, prm["y"] + prm["h"] / 2, rot)
                w2, h2 = prm["w"] * s, prm["h"] * s
                gx, gy = X(x) + cx * s, Y(y) + cy * s
                out.append({"op": "rect", "x": gx - w2 / 2, "y": gy - h2 / 2, "w": w2, "h": h2,
                            "rx": min(prm.get("rx", 0) * s, w2 / 2, h2 / 2),
                            "fill": pfill, "stroke": pstroke, "sw": psw, "dash": dash})
            elif op == "poly":
                if prm.get("_open"):
                    pfill = "none"
                out.append({"op": "poly", "pts": [P(*_rot(a, b, rot)) for a, b in
                                                  [(px + x, py + y) for px, py in prm["pts"]]],
                            "fill": pfill, "stroke": pstroke, "sw": psw, "dash": dash,
                            "close": not prm.get("_open")})
            elif op == "circle":
                cx, cy = P(*_rot(0, 0, rot))
                out.append({"op": "circle", "cx": X(x), "cy": Y(y), "r": prm["r"] * s,
                            "fill": pfill, "stroke": pstroke, "sw": psw, "dash": dash})
            elif op == "path":
                segs = []
                for sg in prm["segs"]:
                    if sg[0] in ("M", "L"):
                        px, py = _rot(sg[1], sg[2], rot)
                        segs.append((sg[0], X(px + x), Y(py + y)))
                    elif sg[0] == "C":
                        a1 = _rot(sg[1], sg[2], rot)
                        a2 = _rot(sg[3], sg[4], rot)
                        a3 = _rot(sg[5], sg[6], rot)
                        segs.append(("C", X(a1[0] + x), Y(a1[1] + y),
                                     X(a2[0] + x), Y(a2[1] + y),
                                     X(a3[0] + x), Y(a3[1] + y)))
                    else:
                        segs.append((sg[0],))
                out.append({"op": "path", "segs": segs, "fill": pfill, "stroke": pstroke,
                            "sw": psw, "dash": dash})
            elif op == "line":
                a1 = _rot(prm["x1"], prm["y1"], rot)
                a2 = _rot(prm["x2"], prm["y2"], rot)
                out.append({"op": "line", "x1": X(a1[0] + x), "y1": Y(a1[1] + y),
                            "x2": X(a2[0] + x), "y2": Y(a2[1] + y),
                            "stroke": pstroke, "sw": psw, "dash": dash})

    # ---- part geometry becomes a soft obstacle for labels ------------------
    for z, ref, x, y, rot, ops, role, sh in raw_geo:
        pad = 0.8
        half = max(pl_["L"] for pl_ in [placed[ref]] if ref in placed) if ref in placed else 0
        if ref in placed:
            p = placed[ref]
            corners = _place([(-p["L"] / 2, -p["W"] / 2), (p["L"] / 2, p["W"] / 2)],
                             p["x"], p["y"], p["rot"])
            xs = [X(c[0]) for c in corners]
            ys = [Y(c[1]) for c in corners]
            placer.add_soft((min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad))

    # ---- annotations (constant stroke + text size) -------------------------
    for sh in shapes:
        _annot(out, sh, parts_by_ref, placed, X, Y, s, placer)

    # ---- part labels -------------------------------------------------------
    for sh in shapes:
        k = (sh.get("k") or "").lower()
        if k not in ("part", "rect", "bar", "rod", "plate", "disc", "band", "block",
                     "circle", "ring", "spring", "wedge", "screw", "tube", "clip", "hook"):
            continue
        if sh.get("label") is False:
            continue
        ref = sh.get("ref")
        part = parts_by_ref.get(ref) or {}
        pl = placed.get(ref)
        if not pl:
            continue
        role = pl["role"]
        rot = pl["rot"]
        off = float(sh.get("label_off", 0) or 0)
        # preferred label position: pushed out along the part's own normal
        nx, ny = _rot(0, -(pl["W"] * s / 2.0 + 3.4 + off), rot)
        lx, ly = X(pl.get("ax", pl["x"])) + nx, Y(pl.get("ay", pl["y"])) + ny
        if sh.get("lx") is not None:
            lx, ly = X(float(sh["lx"])), Y(float(sh["ly"]))
        txt = sh.get("text") or f'{ref}'
        sub = sh.get("sub") or part.get("name", "")
        kind = "red" if role == "new" else "navy"
        anchor = sh.get("anchor", "middle")
        show_name = bool(sub) and sh.get("show_name", True)
        # place the name plate first (below), then the ref plate above it, so
        # the ref — the token the reader matches against the parts list — wins
        # the better slot.
        if show_name:
            placer.plate(out, lx, ly + T.FS_SMALL * 1.45, sub[:26], T.FS_TINY,
                         kind="grey" if role != "new" else "dark", anchor=anchor,
                         anchor_to=None, lead=False)
        placer.plate(out, lx, ly, txt, T.FS_SMALL, kind=kind, anchor=anchor,
                     anchor_to=(X(pl.get("ax", pl["x"])), Y(pl.get("ay", pl["y"]))),
                     lead=bool(sh.get("lead", True)))

    _legend(out, step)

    # Sheet furniture goes on last, with the true scale of this sheet.
    meta = dict(meta)
    meta["scale"] = _scale_label(s)
    return _frame(meta, view, caption) + out


# ---------------------------------------------------------------------------
# annotations
# ---------------------------------------------------------------------------
def _annot(out, sh, parts_by_ref, placed, X, Y, s, placer=None):
    k = (sh.get("k") or "").lower()
    crit = bool(sh.get("critical"))
    col = T.CRIT if crit else T.INK

    if k in ("part", "rect", "bar", "rod", "plate", "disc", "band", "block",
             "circle", "ring", "spring", "wedge", "screw", "tube", "clip", "hook"):
        return

    if k == "arrow":
        x1, y1 = X(sh["x1"]), Y(sh["y1"])
        x2, y2 = X(sh["x2"]), Y(sh["y2"])
        sw = T.SW_BOLD if crit else T.SW_MED
        out.append({"op": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "stroke": col, "sw": sw, "cap": "round"})
        out.append({"op": "poly", "pts": _arrow_head(x1, y1, x2, y2,
                                                     size=float(sh.get("head", 2.2))),
                    "fill": col, "stroke": col, "sw": sw * 0.6})
        if sh.get("label") and placer:
            placer.plate(out, (x1 + x2) / 2.0, (y1 + y2) / 2.0 - T.FS_SMALL * 1.2,
                         _fmt(str(sh["label"])), T.FS_TINY, kind=("red" if crit else "navy"),
                         anchor_to=((x1 + x2) / 2.0, (y1 + y2) / 2.0),
                         color=col)
        return

    if k in ("dim", "dimen", "dimension"):
        ref = sh.get("ref")
        if ref and ref in placed and sh.get("x1") is None:
            pl = placed[ref]
            axis = (sh.get("axis") or "length").lower()
            half = (pl["L"] if axis == "length" else pl["W"]) / 2.0
            off = float(sh.get("off", 6))
            if axis == "length":
                a = _place([(-half, -off), (half, -off)], pl["x"], pl["y"], pl["rot"])
            else:
                a = _place([(-off, -half), (-off, half)], pl["x"], pl["y"], pl["rot"])
            x1, y1 = X(a[0][0]), Y(a[0][1])
            x2, y2 = X(a[1][0]), Y(a[1][1])
            part = parts_by_ref.get(ref) or {}
            val = part.get("length_mm") if axis == "length" else part.get("width_mm")
            text = f"{_num(val)} mm" if val else (sh.get("text") or "")
        else:
            x1, y1 = X(sh["x1"]), Y(sh["y1"])
            x2, y2 = X(sh["x2"]), Y(sh["y2"])
            text = ""
            if sh.get("fit") and _FITS:
                v = _FITS.get(sh["fit"])
                if v is not None:
                    text = f"{_num(v)} mm"
            if not text and ref and ref in parts_by_ref:
                vp = parts_by_ref[ref]
                axis = (sh.get("axis") or "length").lower()
                val = vp.get("length_mm") if axis == "length" else vp.get("width_mm")
                if val:
                    text = f"{_num(val)} mm"
            if not text:
                text = _fmt(sh.get("text") or "")
        _dimension(out, x1, y1, x2, y2, text, crit=crit, placer=placer)
        return

    if k in ("note", "label", "callout"):
        x, y = X(sh["x"]), Y(sh["y"])
        to = sh.get("to")
        tgt = None
        if to:
            tx, ty = X(to[0]), Y(to[1])
            tgt = (tx, ty)
            out.append({"op": "circle", "cx": tx, "cy": ty, "r": 0.52,
                        "fill": col, "stroke": "none", "sw": 0})
        if placer:
            placer.plate(out, x, y, _fmt(str(sh["text"])), T.FS_TINY,
                         kind=("red" if crit else "navy"),
                         anchor=sh.get("anchor", "middle"),
                         anchor_to=tgt, color=col)
        else:
            _plate(out, x, y, _fmt(str(sh["text"])), T.FS_TINY,
                   kind=("red" if crit else "navy"), anchor=sh.get("anchor", "middle"))
        return

    if k in ("cut", "cutline", "cut_line"):
        x1, y1 = X(sh["x1"]), Y(sh["y1"])
        x2, y2 = X(sh["x2"]), Y(sh["y2"])
        out.append({"op": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "stroke": T.CRIT, "sw": T.SW_BOLD, "dash": (3.0, 1.6)})
        if sh.get("label") and placer:
            placer.plate(out, (x1 + x2) / 2.0, (y1 + y2) / 2.0 - T.FS_SMALL * 1.2,
                         _fmt(str(sh["label"])), T.FS_TINY, kind="red",
                         anchor_to=((x1 + x2) / 2.0, (y1 + y2) / 2.0), color=T.CRIT)
        return

    if k in ("hatch", "cutarea", "cut_area"):
        x, y = X(sh["x"]), Y(sh["y"])
        w, h = float(sh["w"]) * s, float(sh["h"]) * s
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        colr = T.CRIT if (sh.get("kind", "cut") in ("cut", "remove")) else T.INK
        seg = _poly_hatch(pts, spacing=float(sh.get("step", 1.5)), angle=float(sh.get("angle", 45)))
        for i in range(0, len(seg) - 1, 2):
            out.append({"op": "line", "x1": seg[i][0], "y1": seg[i][1],
                        "x2": seg[i + 1][0], "y2": seg[i + 1][1],
                        "stroke": colr, "sw": T.SW_HAIR})
        out.append({"op": "poly", "pts": pts, "fill": "none", "stroke": colr,
                    "sw": T.SW_THIN, "dash": (1.6, 1.0)})
        if sh.get("label") and placer:
            placer.plate(out, x + w / 2, y - T.FS_TINY * 1.2, _fmt(str(sh["label"])), T.FS_TINY,
                         kind=("red" if colr == T.CRIT else "navy"),
                         anchor_to=(x + w / 2, y), color=colr)
        return

    if k in ("glue", "weld", "bond", "tape"):
        x, y = X(sh["x"]), Y(sh["y"])
        r = float(sh.get("r", 2.2))
        for i in range(9):
            a = i * math.pi * 2 / 9
            out.append({"op": "circle", "cx": x + math.cos(a) * r * 0.8,
                        "cy": y + math.sin(a) * r * 0.8, "r": 0.32,
                        "fill": T.CRIT, "stroke": "none", "sw": 0})
        if sh.get("label") and placer:
            placer.plate(out, x, y - r - T.FS_TINY * 0.9, _fmt(str(sh["label"])), T.FS_TINY,
                         kind="red", anchor_to=(x, y), color=T.CRIT)
        return

    if k in ("axis", "centerline"):
        x1, y1 = X(sh["x1"]), Y(sh["y1"])
        x2, y2 = X(sh["x2"]), Y(sh["y2"])
        out.append({"op": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "stroke": T.INK_LIGHT, "sw": T.SW_HAIR, "dash": (4.0, 1.2, 0.8, 1.2)})
        return

    if k in ("zoom", "detail"):
        cx, cy = X(sh["x"]), Y(sh["y"])
        r = float(sh.get("r", 8)) * s
        out.append({"op": "circle", "cx": cx, "cy": cy, "r": r, "fill": "none",
                    "stroke": T.INK, "sw": T.SW_THIN, "dash": (2.0, 1.0)})
        to = sh.get("to")
        if to:
            _leader(out, cx + r * 0.7, cy - r * 0.7, X(to[0]), Y(to[1]),
                    color=T.INK, sw=T.SW_HAIR, dash=(1.2, 0.8))
        if sh.get("label") and placer:
            placer.plate(out, cx, cy - r - T.FS_TINY, _fmt(str(sh["label"])), T.FS_TINY,
                         kind="navy", anchor_to=(cx, cy - r))
        return

    if k in ("no", "forbid"):
        x, y = X(sh["x"]), Y(sh["y"])
        r = float(sh.get("r", 2.6))
        out.append({"op": "circle", "cx": x, "cy": y, "r": r, "fill": "none",
                    "stroke": T.CRIT, "sw": T.SW_BOLD})
        d = r * 0.7
        out.append({"op": "line", "x1": x - d, "y1": y - d, "x2": x + d, "y2": y + d,
                    "stroke": T.CRIT, "sw": T.SW_BOLD})
        if sh.get("label") and placer:
            placer.plate(out, x, y + r + T.FS_TINY, _fmt(str(sh["label"])), T.FS_TINY,
                         kind="red", anchor_to=(x, y + r), color=T.CRIT)
        return

    if k == "angle":
        cx, cy = X(sh["x"]), Y(sh["y"])
        r = float(sh.get("r", 8)) * s
        a0 = math.radians(float(sh.get("a0", 0)))
        a1 = math.radians(float(sh.get("a1", 90)))
        segs = [("M", cx + r * math.cos(a0), cy + r * math.sin(a0))]
        steps = 12
        for i in range(1, steps + 1):
            a = a0 + (a1 - a0) * i / steps
            segs.append(("L", cx + r * math.cos(a), cy + r * math.sin(a)))
        out.append({"op": "path", "segs": segs, "fill": "none",
                    "stroke": (T.CRIT if crit else T.INK), "sw": T.SW_THIN})
        if sh.get("text") and placer:
            am = (a0 + a1) / 2
            placer.plate(out, cx + (r + 3.0) * math.cos(am), cy + (r + 3.0) * math.sin(am),
                         _fmt(str(sh["text"])), T.FS_TINY, kind=("red" if crit else "navy"),
                         anchor_to=(cx + r * math.cos(am), cy + r * math.sin(am)))
        return

    if k in ("text", "free"):
        x, y = X(sh["x"]), Y(sh["y"])
        out.append({"op": "text", "x": x, "y": y, "s": _fmt(str(sh["text"])),
                    "size": T.FS_BODY, "fill": (T.CRIT if crit else T.INK_DARK),
                    "anchor": sh.get("anchor", "start"),
                    "weight": "bold" if crit else "normal"})
        return

    if k in ("line", "poly", "path"):
        pts = sh.get("pts") or []
        if len(pts) >= 2:
            tp = [P_xy(X, Y, p) for p in pts]
            out.append({"op": "poly" if sh.get("close") else "poly", "pts": tp,
                        "fill": sh.get("fill", "none"), "stroke": col,
                        "sw": T.SW_MED, "close": bool(sh.get("close"))})
        return


def P_xy(X, Y, p):
    return (X(p[0]), Y(p[1]))


def _fmt(s):
    """Expand {fit_name} placeholders from the spec's declared constants.

    A number printed on a drawing is therefore always a number that exists in
    the spec — it cannot be invented at render time.
    """
    if not isinstance(s, str) or "{" not in s:
        return s
    out = s
    for k, v in (_FITS or {}).items():
        out = out.replace("{" + k + "}", _num(v))
    return out


def _num(v):
    try:
        f = float(v)
        return str(int(f)) if abs(f - int(f)) < 1e-6 else f"{f:.1f}"
    except Exception:
        return str(v)


def _dimension(out, x1, y1, x2, y2, text, crit=False, placer=None):
    col = T.CRIT if crit else T.INK_DARK
    out.append({"op": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "stroke": col, "sw": T.SW_THIN})
    dx, dy = x2 - x1, y2 - y1
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    t = 1.1
    for (ax, ay) in ((x1, y1), (x2, y2)):
        out.append({"op": "line", "x1": ax + px * t, "y1": ay + py * t,
                    "x2": ax - px * t, "y2": ay - py * t,
                    "stroke": col, "sw": T.SW_THIN})
    if text:
        if placer:
            placer.plate(out, (x1 + x2) / 2.0, (y1 + y2) / 2.0, text, T.FS_TINY,
                         kind=("red" if crit else "navy"), pad_h=0.4,
                         anchor_to=None, lead=False)
        else:
            _plate(out, (x1 + x2) / 2.0, (y1 + y2) / 2.0, text, T.FS_TINY,
                   kind=("red" if crit else "navy"), pad_h=0.4)


# ---------------------------------------------------------------------------
# sheet furniture
# ---------------------------------------------------------------------------
def _frame(meta, view, caption) -> List[dict]:
    """Sheet furniture. Built LAST so the title block can state the true scale."""
    out: List[dict] = []
    # sheet border
    out.append({"op": "rect", "x": T.BORDER_INSET, "y": T.BORDER_INSET,
                "w": T.SHEET_W - 2 * T.BORDER_INSET, "h": T.SHEET_H - 2 * T.BORDER_INSET,
                "fill": "none", "stroke": T.NAVY, "sw": T.SW_FRAME, "rx": 0.6})
    out.append({"op": "rect", "x": T.BORDER_INSET + 0.55, "y": T.BORDER_INSET + 0.55,
                "w": T.SHEET_W - 2 * T.BORDER_INSET - 1.1,
                "h": T.SHEET_H - 2 * T.BORDER_INSET - 1.1,
                "fill": "none", "stroke": T.NAVY_SOFT, "sw": T.SW_HAIR, "rx": 0.3})

    # header: view caption (left) + step badge (right)
    title = str(meta.get("title", ""))[:44]
    _plate(out, T.MARGIN + 1.0, (T.HEADER_Y0 + T.HEADER_Y1) / 2.0,
           f"{view}" + (f"  ·  {caption}" if caption else ""),
           T.FS_BODY, kind="navy", anchor="start")
    badge = meta.get("badge") or f"STEP {meta.get('step_n', 1)}/{meta.get('total_steps', 1)}"
    _plate(out, T.SHEET_W - T.MARGIN - 1.0, (T.HEADER_Y0 + T.HEADER_Y1) / 2.0,
           badge, T.FS_SMALL, kind="navy", anchor="end")

    # title block (bottom right)
    tb_w = 40.0
    tb_x = T.SHEET_W - T.MARGIN - 1.0 - tb_w
    tb_y = T.FOOTER_Y0
    tb_h = T.FOOTER_Y1 - T.FOOTER_Y0
    out.append({"op": "rect", "x": tb_x, "y": tb_y, "w": tb_w, "h": tb_h,
                "fill": T.NAVY, "stroke": "none", "sw": 0, "rx": 0.6})
    row = tb_h / 3.0
    out.append({"op": "line", "x1": tb_x, "y1": tb_y + row, "x2": tb_x + tb_w,
                "y2": tb_y + row, "stroke": T.WHITE, "sw": T.SW_HAIR})
    out.append({"op": "line", "x1": tb_x, "y1": tb_y + 2 * row, "x2": tb_x + tb_w,
                "y2": tb_y + 2 * row, "stroke": T.WHITE, "sw": T.SW_HAIR})
    out.append({"op": "text", "x": tb_x + 1.2, "y": tb_y + row * 0.66, "s": title[:34],
                "size": T.FS_TINY, "fill": T.WHITE, "anchor": "start", "weight": "bold"})
    sheet_no = "PL" if int(meta.get("step_n", 1)) == 0 else f"{int(meta.get('step_n',1)):02d}"
    out.append({"op": "text", "x": tb_x + 1.2, "y": tb_y + row * 1.66,
                "s": f"SHEET {sheet_no}  SCALE {meta.get('scale','1:1')}",
                "size": T.FS_MICRO, "fill": T.WHITE, "anchor": "start"})
    out.append({"op": "text", "x": tb_x + 1.2, "y": tb_y + row * 2.66,
                "s": "DIM mm  ·  FABRIX ENGINEER",
                "size": T.FS_MICRO, "fill": T.WHITE, "anchor": "start"})
    return out


def _area_grid(out, step):
    if step <= 0:
        return
    x = T.AREA_X0
    while x <= T.AREA_X1 + 1e-6:
        out.append({"op": "line", "x1": x, "y1": T.AREA_Y0, "x2": x, "y2": T.AREA_Y1,
                    "stroke": T.GRID_MINOR, "sw": T.SW_HAIR * 0.8, "cap": "butt"})
        x += step
    y = T.AREA_Y0
    while y <= T.AREA_Y1 + 1e-6:
        out.append({"op": "line", "x1": T.AREA_X0, "y1": y, "x2": T.AREA_X1, "y2": y,
                    "stroke": T.GRID_MINOR, "sw": T.SW_HAIR * 0.8, "cap": "butt"})
        y += step


def _legend(out, step):
    """Bottom-left legend. Explains the colour code used on the sheet."""
    x = T.MARGIN + 1.2
    y = T.FOOTER_Y0 + 1.5
    items = [("navy", "ASSEMBLED"), ("red", "NEW THIS STEP"), ("grey", "ALREADY BUILT")]
    for kind, txt in items:
        _plate(out, x, y, txt, T.FS_MICRO, kind=kind, anchor="start", pad_h=0.35)
        x += T.plate_w(txt, T.FS_MICRO, pad=0.35) + 1.2
    warn = step.get("hazard")
    if warn:
        _plate(out, T.MARGIN + 1.2, y + T.FS_MICRO * 2.2,
               "! " + str(warn)[:52], T.FS_MICRO, kind="red", anchor="start", pad_h=0.35)
    return out


# ---------------------------------------------------------------------------
# parts list / nomenclature sheet
# ---------------------------------------------------------------------------
CORDY = ("cord", "string", "thread", "line_part")


def _icon(out, part, bx0, by0, bw, bh):
    """Draw one part scaled to fit a box, preserving its true aspect ratio."""
    L = float(part.get("length_mm") or 40)
    W = float(part.get("width_mm") or max(L * 0.16, 3))
    shape = (part.get("shape") or "bar").lower()
    if shape in CORDY:
        pts = []
        n = 14
        for i in range(n + 1):
            t = i / n
            pts.append((bx0 + t * bw, by0 + bh / 2 + (bh * 0.28) * math.sin(t * math.pi * 5)))
        out.append({"op": "poly", "pts": pts, "fill": "none", "stroke": T.INK,
                    "sw": T.SW_THIN, "close": False})
        return
    k = min(bw / max(L, 1e-6), bh / max(W, 1e-6))
    ops = part_local_ops(part, L * k, W * k, {})
    cx, cy = bx0 + bw / 2.0, by0 + bh / 2.0
    for op, prm in ops:
        if op == "rect":
            out.append({"op": "rect", "x": cx + prm["x"], "y": cy + prm["y"],
                        "w": prm["w"], "h": prm["h"], "rx": prm.get("rx", 0),
                        "fill": T.WHITE, "stroke": T.INK, "sw": T.SW_MED})
        elif op == "poly":
            out.append({"op": "poly", "pts": [(cx + a, cy + b) for a, b in prm["pts"]],
                        "fill": T.WHITE, "stroke": T.INK, "sw": T.SW_MED,
                        "close": not prm.get("_open")})
        elif op == "circle":
            out.append({"op": "circle", "cx": cx, "cy": cy, "r": prm["r"],
                        "fill": T.WHITE, "stroke": T.INK, "sw": T.SW_MED})
        elif op == "path":
            segs = []
            for sg in prm["segs"]:
                if sg[0] in ("M", "L"):
                    segs.append((sg[0], cx + sg[1], cy + sg[2]))
                elif sg[0] == "C":
                    segs.append(("C", cx + sg[1], cy + sg[2], cx + sg[3], cy + sg[4],
                                 cx + sg[5], cy + sg[6]))
                else:
                    segs.append((sg[0],))
            out.append({"op": "path", "segs": segs, "fill": T.WHITE, "stroke": T.INK,
                        "sw": T.SW_MED})
        elif op == "line":
            out.append({"op": "line", "x1": cx + prm["x1"], "y1": cy + prm["y1"],
                        "x2": cx + prm["x2"], "y2": cy + prm["y2"],
                        "stroke": T.INK, "sw": T.SW_THIN})


def _dims_str(p) -> str:
    bits = []
    for v in (p.get("length_mm"), p.get("width_mm"), p.get("thickness_mm")):
        if v:
            f = float(v)
            bits.append(str(int(f)) if abs(f - int(f)) < 1e-6 else f"{f:.1f}")
    return (" x ".join(bits) + " mm") if bits else ""


def build_parts_sheet(parts: List[dict], meta: dict) -> List[dict]:
    """Nomenclature: every part drawn once at a readable size, with its ref.

    Icons are normalised to fit their cell (a 360 mm string and a 2.2 mm
    toothpick both have to be recognisable), so this sheet does not use the
    global part scale — it is a list, not a view.
    """
    out: List[dict] = []
    placer = Placer()
    placer.add_hard((1.6, 2.2, 98.4, 8.2))
    placer.add_hard((56.0, 51.6, 98.4, 61.9))
    placer.add_hard((1.6, 51.6, 56.0, 61.9))

    n = max(len(parts), 1)
    cols = 2 if n > 4 else 1
    rows = (n + cols - 1) // cols
    x0, y0 = 6.0, 10.0
    cw, ch = (88.0 / cols), (41.0 / rows)

    for i, p in enumerate(parts):
        c, r = i % cols, i // cols
        bx = x0 + c * cw
        by = y0 + r * ch
        icon_w = 13.0
        _icon(out, p, bx + 0.5, by + ch * 0.14, icon_w, ch * 0.72)
        tx = bx + icon_w + 1.6
        avail = cw - icon_w - 3.0

        ref_w = T.plate_w(p["ref"], T.FS_SMALL)
        placer.plate(out, tx, by + ch * 0.24, p["ref"], T.FS_SMALL, kind="navy",
                     anchor="start", lead=False)
        name = _fit((p.get("name") or ""), avail - ref_w - 1.0, T.FS_MICRO)
        if name:
            placer.plate(out, tx + ref_w + 1.0, by + ch * 0.24, name, T.FS_MICRO,
                         kind="grey", anchor="start", lead=False)
        d = _fit(_dims_str(p), avail, T.FS_MICRO)
        if d:
            placer.plate(out, tx, by + ch * 0.52, d, T.FS_MICRO, kind="grey",
                         anchor="start", lead=False)
        q = int(p.get("qty") or 1)
        if q > 1:
            placer.plate(out, tx + T.plate_w(d, T.FS_MICRO) + 1.0, by + ch * 0.52,
                         f"QTY {q}", T.FS_MICRO, kind="blue", anchor="start", lead=False)
        mat = _fit((p.get("material") or ""), avail, T.FS_MICRO)
        if mat and ch > 8.5:
            placer.plate(out, tx, by + ch * 0.80, mat, T.FS_MICRO, kind="grey",
                         anchor="start", lead=False)
    meta = dict(meta)
    meta.setdefault("scale", "—")
    return _frame(meta, "PARTS LIST", "") + out


def _scale_label(s):
    """Human-readable sheet scale, based on how the sheet prints in the PDF."""
    mm_per_unit = PRINT_W_MM / T.SHEET_W
    r = s * mm_per_unit
    if r >= 1.0:
        return f"{r:.1f}:1" if r < 10 else f"{r:.0f}:1"
    return f"1:{1.0 / max(r, 1e-6):.1f}"


def _fit(s, max_w, size):
    """Truncate text so its plate fits the available width."""
    if not s:
        return ""
    s = str(s)
    while s and T.plate_w(s, size) > max_w:
        s = s[:-1]
    if len(str(s)) < len(str(s)):
        pass
    return s
