"""Command line front-end for the Fabrix engineer.

    python -m engineer.cli render  specs/crossbow.json  --out build/
    python -m engineer.cli proof   specs/crossbow.json
    python -m engineer.cli validate specs/crossbow.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .render import (all_svgs, overview_svg, step_drawing, step_prims, step_svg)
from .blueprint import theme as T
from .proof import ascii_sheet, check_sheet
from .manual_pdf import build_pdf
from .schema import normalize_spec, validate_spec


def load(path):
    with open(path) as f:
        return normalize_spec(json.load(f))


def cmd_validate(spec, args):
    errs, warns = validate_spec(spec)
    for e in errs:
        print("  ERROR  ", e)
    for w in warns:
        print("  warn   ", w)
    print(f"\n{len(errs)} error(s), {len(warns)} warning(s), "
          f"{len(spec['steps'])} steps, {len(spec['materials'])} parts")
    return 1 if errs else 0


def cmd_render(spec, args):
    out = args.out or "build"
    os.makedirs(out, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.spec))[0]
    with open(os.path.join(out, f"{base}-00-nomenclature.svg"), "w") as f:
        f.write(overview_svg(spec))
    for i, svg in enumerate(all_svgs(spec), start=1):
        with open(os.path.join(out, f"{base}-{i:02d}.svg"), "w") as f:
            f.write(svg)
    pdf = build_pdf(spec)
    with open(os.path.join(out, f"{base}.pdf"), "wb") as f:
        f.write(pdf)
    print(f"wrote {len(spec['steps'])+1} SVG sheets + {base}.pdf ({len(pdf)} bytes) to {out}/")
    return 0


def cmd_proof(spec, args):
    rc = 0
    from .render import overview_prims
    print("#" * 100)
    print("SHEET 0 — NOMENCLATURE")
    print(ascii_sheet(overview_svg(spec), cols=args.cols))
    for i, step in enumerate(spec["steps"], start=1):
        prims = step_prims(spec, i - 1)
        errs, warns = check_sheet(prims, step, step["parts_used"])
        print("#" * 100)
        print(f"SHEET {i} — {step['title']}   (parts used: {', '.join(step['parts_used']) or '-'})")
        print(ascii_sheet(step_svg(spec, i - 1), cols=args.cols))
        for e in errs:
            print("  ERROR  ", e)
            rc = 1
        for w in warns:
            print("  warn   ", w)
    errs, warns = validate_spec(spec)
    print("#" * 100)
    for e in errs:
        print("  SPEC ERROR", e)
        rc = 1
    for w in warns:
        print("  spec warn ", w)
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(prog="engineer")
    ap.add_argument("cmd", choices=["validate", "render", "proof"])
    ap.add_argument("spec")
    ap.add_argument("--out", default=None)
    ap.add_argument("--cols", type=int, default=112)
    args = ap.parse_args(argv)
    spec = load(args.spec)
    return {"validate": cmd_validate, "render": cmd_render, "proof": cmd_proof}[args.cmd](spec, args)


if __name__ == "__main__":
    sys.exit(main())
