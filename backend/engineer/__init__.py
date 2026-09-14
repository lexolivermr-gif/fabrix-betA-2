"""Fabrix Engineer — one AI reasons, a deterministic engine draws.

The pipeline is deliberately split in two:

    engineer.agent     the AI: interrogation, then a complete build spec
    engineer.blueprint the renderer: spec -> SVG / PDF, no model involved

The drawing is *computed* from the spec, never generated. That is what makes
the picture and the prose the same object instead of two separate guesses that
have to be checked against each other.
"""
from __future__ import annotations

import os
import sys

# Allow self-contained dependency folders. In production the packages live in
# site-packages; these paths are only a fallback so the service can boot in a
# bare sandbox or offline. They are never required.
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_HOME = os.path.expanduser("~")
for _candidate in (
    os.path.join(_HERE, ".vendor"),
    os.path.join(_HERE, "vendor"),
    os.path.join(_HOME, ".pydeps"),
):
    if os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.append(_candidate)
