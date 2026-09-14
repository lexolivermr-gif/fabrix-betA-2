"""
The Engineer: one model, two phases.

    engineer.ask()     -> the next question (or READY)
    engineer.design()  -> a complete, validated build spec

`design()` never returns an unvalidated spec. If the coherence contract fails
the errors go straight back to the model as a repair request, so the model
fixes its own drawing instead of the app shipping a sheet that contradicts its
own prose.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

from .llm import LLM, LLMError, extract_json
from .prompts import (DESIGN_SYSTEM, DESIGN_USER, INTERROGATE_SYSTEM,
                      INTERROGATE_USER, READY, REPAIR_USER)
from .schema import normalize_spec, validate_spec

log = logging.getLogger("engineer.agent")

LANG_NAMES = {
    "en": "English", "fr": "French", "es": "Spanish", "de": "German",
    "pt": "Portuguese", "it": "Italian",
}


def _lang(lang: Optional[str]):
    code = (lang or "en").split("-")[0].lower()
    return code, LANG_NAMES.get(code, "English")


def _transcript(history) -> str:
    if not history:
        return "(no questions asked yet — this is your first turn)"
    lines = []
    for m in history:
        role = (m.get("role") if isinstance(m, dict) else getattr(m, "role", ""))
        content = (m.get("content") if isinstance(m, dict)
                   else getattr(m, "content", ""))
        if role in ("user", "assistant"):
            lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines) or "(none)"


class Engineer:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.llm = LLM(provider=provider, model=model)

    # ------------------------------------------------------------------
    def ask(self, project: str, history=None, lang: str = "en") -> dict:
        """Return the next question. `ready` is True once it has enough."""
        code, name = _lang(lang)
        user = INTERROGATE_USER.format(project=project, lang_name=name,
                                       lang_code=code,
                                       transcript=_transcript(history))
        reply = self.llm.complete(INTERROGATE_SYSTEM, user).strip()
        ready = READY in reply
        if ready:
            # keep only the closing sentence; drop the sentinel
            reply = "\n".join(l for l in reply.splitlines()
                              if l.strip() != READY).strip()
        return {"reply": reply, "ready": ready}

    # ------------------------------------------------------------------
    def design(self, project: str, history=None, lang: str = "en",
               max_repairs: int = 3) -> dict:
        """Produce a validated build spec, repairing against the checker."""
        code, name = _lang(lang)
        user = DESIGN_USER.format(project=project, lang_name=name,
                                  lang_code=code,
                                  transcript=_transcript(history))
        raw = self.llm.complete(DESIGN_SYSTEM, user, json_mode=True,
                                max_tokens=32000)
        data = extract_json(raw)
        data = normalize_spec(data)
        data["lang"] = code
        errs, warns = validate_spec(data)
        attempts = 0
        while errs and attempts < max_repairs:
            attempts += 1
            log.warning("spec rejected (attempt %d): %s", attempts, errs[:4])
            repair = REPAIR_USER.format(
                errors="\n".join(f"- {e}" for e in errs) or "(none)",
                warnings="\n".join(f"- {w}" for w in warns) or "(none)",
                spec=json.dumps(data, ensure_ascii=False)[:24000],
            )
            try:
                fixed = extract_json(self.llm.complete(
                    DESIGN_SYSTEM, repair, json_mode=True, max_tokens=32000))
                data = normalize_spec(fixed)
                data["lang"] = code
            except (LLMError, ValueError) as e:
                log.error("repair call failed: %s", e)
                break
            errs, warns = validate_spec(data)
        data["_validation"] = {"errors": errs, "warnings": warns,
                               "repairs": attempts}
        return data


# ---------------------------------------------------------------------------
def load_spec(path: str) -> dict:
    """Load and normalise a spec from disk (used by the CLI and by the
    bundled examples, and the way you run the whole pipeline with no model)."""
    with open(path) as f:
        return normalize_spec(json.load(f))
