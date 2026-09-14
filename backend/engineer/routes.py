"""
HTTP surface for the Engineer.

    POST /api/engineer/ask      -> next clarifying question
    POST /api/engineer/design   -> validated build spec
    POST /api/engineer/sheets   -> blueprint SVGs for that spec
    POST /api/engineer/pdf      -> the finished manual

These endpoints are stateless and need no database: the client keeps the spec
and passes it back when it wants drawings or a PDF.
"""
from __future__ import annotations

import io
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from .llm import LLMError, detect_provider
from .schema import normalize_spec, validate_spec

log = logging.getLogger("engineer.routes")

router = APIRouter(prefix="/api/engineer", tags=["engineer"])


class AskIn(BaseModel):
    project: str = Field("", description="What the user wants to build")
    history: List[dict] = Field(default_factory=list)
    lang: str = "en"


class DesignIn(AskIn):
    provider: Optional[str] = None
    model: Optional[str] = None


class SpecIn(BaseModel):
    spec: dict
    lang: Optional[str] = None


# ---------------------------------------------------------------------------
@router.get("/health")
def health():
    prov = detect_provider()
    return {"ok": True, "provider": prov, "configured": bool(prov),
            "offline_examples": True}


def _engineer(provider=None, model=None):
    from .agent import Engineer
    try:
        return Engineer(provider=provider, model=model)
    except LLMError as e:
        raise HTTPException(503, {"error": str(e),
                                  "hint": "set OPENROUTER_API_KEY, "
                                          "ANTHROPIC_API_KEY, OPENAI_API_KEY, "
                                          "GEMINI_API_KEY, or LLM_BASE_URL"})


@router.post("/ask")
def ask(body: AskIn):
    if not body.project.strip():
        raise HTTPException(400, "project is empty")
    try:
        return _engineer().ask(body.project, body.history, body.lang)
    except LLMError as e:
        raise HTTPException(502, str(e))


@router.post("/design")
def design(body: DesignIn):
    if not body.project.strip():
        raise HTTPException(400, "project is empty")
    try:
        spec = _engineer(body.provider, body.model).design(
            body.project, body.history, body.lang)
    except LLMError as e:
        raise HTTPException(502, str(e))
    return spec


# ---------------------------------------------------------------------------
@router.get("/example")
def example():
    """The bundled acceptance spec — lets you exercise the whole pipeline
    (validate -> sheets -> pdf) with no model configured."""
    import os
    from .agent import load_spec
    path = os.path.join(os.path.dirname(__file__), "examples",
                        "toothpick_crossbow.json")
    return load_spec(path)


@router.post("/validate")
def validate(body: SpecIn):
    spec = normalize_spec(body.spec)
    errs, warns = validate_spec(spec)
    return {"errors": errs, "warnings": warns, "ok": not errs,
            "steps": len(spec.get("steps", [])),
            "parts": len(spec.get("materials", []))}


def _render(spec: dict):
    from .render import all_svgs, overview_svg
    spec = normalize_spec(spec)
    errs, warns = validate_spec(spec)
    if errs:
        raise HTTPException(422, {"errors": errs, "warnings": warns})
    return spec, overview_svg(spec), all_svgs(spec), warns


@router.post("/sheets")
def sheets(body: SpecIn):
    spec, overview, steps, warns = _render(body.spec)
    out = []
    for i, svg in enumerate(steps):
        st = spec["steps"][i]
        dw = st.get("drawing") or {}
        out.append({
            "n": st.get("n", i + 1),
            "title": st.get("title", ""),
            "caption": dw.get("caption", ""),
            "view": dw.get("view", ""),
            "svg": svg,
        })
    return {"title": spec.get("title", ""), "nomenclature": overview,
            "sheets": out, "warnings": warns}


@router.post("/pdf")
def pdf(body: SpecIn):
    from .manual_pdf import build_pdf
    spec, _, _, _ = _render(body.spec)
    try:
        data = build_pdf(spec)
    except Exception as e:  # surface the real cause, don't mask it
        log.exception("pdf build failed")
        raise HTTPException(500, f"{type(e).__name__}: {e}")
    slug = (spec.get("title") or "manual").lower()
    slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-") or "manual"
    return Response(
        content=data, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{slug}.pdf"'},
    )
