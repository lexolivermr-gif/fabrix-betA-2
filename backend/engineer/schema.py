"""
The build spec: the ONE source of truth shared by the prose and the drawings.

Everything the reader sees is derived from this object:
  - the materials list
  - the step-by-step prose
  - every blueprint (geometry, labels, dimensions)

Because prose and drawing are two projections of the same object, they cannot
disagree. `validate_spec` is the mechanical check that keeps it that way.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

PART_KEYS = {"ref", "name", "material", "length_mm", "width_mm", "thickness_mm",
             "qty", "shape", "source", "notes"}

SHAPE_KINDS = {"part", "rect", "bar", "rod", "plate", "disc", "band", "block",
               "circle", "ring", "spring", "wedge", "screw", "tube", "clip", "hook"}

DEFAULTS_PART = {
    "qty": 1, "shape": "bar", "name": "", "material": "", "source": "", "notes": "",
    "length_mm": None, "width_mm": None, "thickness_mm": None,
}


# ---------------------------------------------------------------------------
def normalize_spec(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Fill defaults, coerce types, index parts. Idempotent."""
    s = dict(raw or {})
    s.setdefault("title", "Untitled build")
    s.setdefault("subtitle", "")
    s.setdefault("mode", "create")
    s.setdefault("lang", "en")
    s.setdefault("summary", "")
    s.setdefault("difficulty", "intermediate")
    s.setdefault("safety", [])
    s.setdefault("principles", [])
    s.setdefault("tools", [])
    s.setdefault("checks", [])
    s.setdefault("steps", [])

    mats: List[dict] = []
    for i, m in enumerate(s.get("materials") or []):
        p = dict(DEFAULTS_PART)
        p.update({k: v for k, v in m.items() if k in PART_KEYS})
        if not p["ref"]:
            p["ref"] = f"P{i+1}"
        for k in ("length_mm", "width_mm", "thickness_mm"):
            try:
                p[k] = float(p[k]) if p[k] is not None else None
            except (TypeError, ValueError):
                p[k] = None
        try:
            p["qty"] = int(p["qty"] or 1)
        except (TypeError, ValueError):
            p["qty"] = 1
        mats.append(p)
    s["materials"] = mats

    tools = []
    for t in s["tools"]:
        if isinstance(t, str):
            tools.append({"name": t, "optional": False, "substitute": ""})
        else:
            tools.append({"name": t.get("name", ""), "optional": bool(t.get("optional")),
                          "substitute": t.get("substitute", "")})
    s["tools"] = tools

    steps = []
    for i, st in enumerate(s["steps"]):
        st = dict(st)
        st["n"] = int(st.get("n") or (i + 1))
        st.setdefault("title", f"Step {i+1}")
        st.setdefault("intent", "")
        st.setdefault("why", "")
        st.setdefault("check", "")
        st.setdefault("tip", "")
        st.setdefault("hazard", "")
        st.setdefault("actions", [])
        if isinstance(st["actions"], str):
            st["actions"] = [st["actions"]]
        st["duration_min"] = int(st.get("duration_min") or 5)
        st["parts_used"] = list(st.get("parts_used") or [])
        st["context_parts"] = list(st.get("context_parts") or [])
        d = dict(st.get("drawing") or {})
        d.setdefault("view", "detail")
        d.setdefault("caption", "")
        d["shapes"] = [dict(x) for x in (d.get("shapes") or [])]
        st["drawing"] = d
        steps.append(st)
    s["steps"] = sorted(steps, key=lambda x: x["n"])

    s["total_duration_min"] = int(s.get("total_duration_min") or
                                  sum(x["duration_min"] for x in steps))
    return s


def parts_index(spec: Dict[str, Any]) -> Dict[str, dict]:
    return {p["ref"]: p for p in spec["materials"]}


# ---------------------------------------------------------------------------
def validate_spec(spec: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings). Errors mean 'do not ship this'."""
    errs: List[str] = []
    warns: List[str] = []
    idx = parts_index(spec)

    if not spec.get("materials"):
        errs.append("spec.materials is empty")
    if not spec.get("steps"):
        errs.append("spec.steps is empty")
    if len(spec.get("steps", [])) > 14:
        warns.append(f"{len(spec['steps'])} steps — long for a printed guide")

    dupes = [r for r in idx if list(p["ref"] for p in spec["materials"]).count(r) > 1]
    if dupes:
        errs.append(f"duplicate part refs: {sorted(set(dupes))}")

    # every part must be usable by at least one step, and named
    used_anywhere = set()
    for st in spec["steps"]:
        used_anywhere |= set(st["parts_used"]) | set(st["context_parts"])
    for ref, p in idx.items():
        if not p["name"]:
            errs.append(f"part {ref} has no name")
        if ref not in used_anywhere:
            warns.append(f"part {ref} ({p['name']}) is never used in any step")

    for i, st in enumerate(spec["steps"], start=1):
        tag = f"step {i}"

        # --- prose quality -------------------------------------------------
        if not st["actions"]:
            errs.append(f"{tag}: no actions")
        if not st["check"]:
            warns.append(f"{tag}: no verification check")
        if not st["why"]:
            warns.append(f"{tag}: no mechanical rationale")

        # --- refs exist ----------------------------------------------------
        for r in st["parts_used"] + st["context_parts"]:
            if r not in idx:
                errs.append(f"{tag}: references unknown part '{r}'")

        shapes = st["drawing"]["shapes"]
        drawn = {sh.get("ref") for sh in shapes if (sh.get("k") or "").lower() in SHAPE_KINDS
                 and sh.get("ref")}

        # --- THE COHERENCE CONTRACT ---------------------------------------
        # 1. nothing may be drawn that is not in this step's parts
        for r in sorted(drawn - set(st["parts_used"]) - set(st["context_parts"])):
            warns.append(f"{tag}: draws {r} but it is not listed in parts_used/context_parts")
            st["context_parts"].append(r)

        # 2. every part the text says you touch must appear in the drawing
        missing = [r for r in st["parts_used"] if r not in drawn]
        if missing:
            errs.append(f"{tag}: parts {missing} are used by the text but never drawn")

        # 3. dimensions must come from the parts table
        for sh in shapes:
            k = (sh.get("k") or "").lower()
            if k in ("dim", "dimen", "dimension") and sh.get("ref"):
                ref = sh["ref"]
                if ref not in idx:
                    errs.append(f"{tag}: dimension references unknown part '{ref}'")
                else:
                    axis = (sh.get("axis") or "length").lower()
                    val = idx[ref].get("length_mm" if axis == "length" else "width_mm")
                    if not val:
                        errs.append(f"{tag}: dimension of {ref}.{axis} but the parts "
                                    f"table has no {'length_mm' if axis=='length' else 'width_mm'}")
            if k in SHAPE_KINDS and sh.get("ref") and sh["ref"] not in idx:
                errs.append(f"{tag}: draws unknown part '{sh['ref']}'")

        # 4. the drawing must say something
        if not shapes:
            errs.append(f"{tag}: empty drawing")

    return errs, warns
