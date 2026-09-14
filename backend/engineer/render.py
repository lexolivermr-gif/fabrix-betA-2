"""Facade: build spec -> SVG sheets / PDF bytes."""
from __future__ import annotations

import copy
from typing import Dict, List, Optional

from .blueprint import scene as S
from .blueprint import theme as T
from .blueprint.prims import to_svg, to_reportlab
from .schema import normalize_spec, parts_index

PX_PER_UNIT = 14.0


def _meta(spec: dict, n: int) -> dict:
    return {
        "title": spec.get("title", ""),
        "step_n": n,
        "total_steps": len(spec["steps"]),
        "scale": spec.get("scale", "1:1"),
    }


def step_prims(spec: dict, i: int) -> List[dict]:
    spec = normalize_spec(spec) if spec.get("__raw") else spec
    st = dict(spec["steps"][i])
    st["_fits"] = spec.get("fits") or {}
    return S.build_sheet(st, parts_index(spec), _meta(spec, i + 1))


def step_svg(spec: dict, i: int, px_per_unit: float = PX_PER_UNIT) -> str:
    return to_svg(step_prims(spec, i), T.SHEET_W, T.SHEET_H, px_per_unit)


def all_svgs(spec: dict, px_per_unit: float = PX_PER_UNIT) -> List[str]:
    return [step_svg(spec, i, px_per_unit) for i in range(len(spec["steps"]))]


def step_drawing(spec: dict, i: int):
    """reportlab Drawing for one step (vector, used in the PDF)."""
    return to_reportlab(step_prims(spec, i), T.SHEET_W, T.SHEET_H)


# ---------------------------------------------------------------------------
# overview / nomenclature sheet
# ---------------------------------------------------------------------------
def overview_prims(spec: dict) -> List[dict]:
    meta = {"title": spec.get("title", ""), "step_n": 0, "badge": "PARTS LIST",
            "total_steps": len(spec["steps"]), "scale": spec.get("scale", "1:1")}
    return S.build_parts_sheet(spec["materials"], meta)


def overview_svg(spec: dict, px_per_unit: float = PX_PER_UNIT) -> str:
    return to_svg(overview_prims(spec), T.SHEET_W, T.SHEET_H, px_per_unit)


def overview_drawing(spec: dict):
    return to_reportlab(overview_prims(spec), T.SHEET_W, T.SHEET_H)
