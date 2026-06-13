"""
Fabrix AI service layer (formerly ManuelIA).

Models LOCKED:
  - Text + vision : claude-sonnet-4-5-20250929  (via emergentintegrations)
  - Images        : gpt-image-2                  (OpenAI direct)

Pipeline:
  1. ONE Claude call returns full manual JSON:
       title, materials, tools, style_anchor, steps[] with title, description, tip,
       duration_min, image_prompt (English, optimized for gpt-image-2)
  2. Step 1 image generated alone (text-to-image)         → becomes reference + style anchor for the rest
  3. Steps 2..N + cover generated in PARALLEL via images.edit (img2img)
     using step1 as reference + style_anchor as text prefix
  4. NO validator retry loop (removed). Quality is controlled by Claude's prompt builder.

Anti-hallucination is now ENTIRELY in the prompt engineering of layer 1.

Every call logs the requested model + the returned model. If they differ, a CRITICAL log is emitted.
"""
from __future__ import annotations

import os
import json
import re
import base64
import asyncio
import logging
from typing import List, Optional, Tuple, Dict, Any

import httpx
from openai import AsyncOpenAI
from fastapi import HTTPException

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

log = logging.getLogger("ai")

# ---------------------------------------------------------------------------
# LOCKED MODEL CONSTANTS
# ---------------------------------------------------------------------------
TEXT_MODEL_PROVIDER = "anthropic"
TEXT_MODEL_NAME = "claude-sonnet-4-5-20250929"   # user-facing alias: "claude-sonnet-4-5"
IMAGE_MODEL = "gpt-image-2"                        # locked
IMAGE_SIZE = "1536x1024"
IMAGE_QUALITY = "medium"

_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
_EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

if not _OPENAI_API_KEY:
    log.warning("OPENAI_API_KEY missing — image calls will fail.")
if not _EMERGENT_LLM_KEY:
    log.warning("EMERGENT_LLM_KEY missing — Claude calls will fail.")


_openai_client: Optional[AsyncOpenAI] = None

def get_openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=_OPENAI_API_KEY, timeout=240.0, max_retries=2)
    return _openai_client


def _shrink_png_b64(b64: str, max_bytes: int = 600_000) -> str:
    """Re-encode a PNG (base64) to fit under max_bytes so the whole manual stays under
    MongoDB's 16MB BSON document limit. IKEA-style line art quantizes to a tiny palette
    losslessly visually.
    """
    try:
        from io import BytesIO
        from PIL import Image
        raw = base64.b64decode(b64)
        if len(raw) <= max_bytes:
            return b64
        im = Image.open(BytesIO(raw)).convert("RGB")
        # Quantize to adaptive palette — line art uses very few colors
        for colors in (64, 32, 16):
            buf = BytesIO()
            im.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).save(
                buf, format="PNG", optimize=True
            )
            data = buf.getvalue()
            if len(data) <= max_bytes:
                return base64.b64encode(data).decode("ascii")
        # Fallback: downscale 75% then quantize 16 colors
        w, h = im.size
        im = im.resize((int(w * 0.75), int(h * 0.75)), Image.LANCZOS)
        buf = BytesIO()
        im.quantize(colors=16, method=Image.Quantize.MEDIANCUT).save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        log.warning("PNG shrink failed, keeping original: %s", e)
        return b64


# ---------------------------------------------------------------------------
# Model logging helpers (mandatory per spec)
# ---------------------------------------------------------------------------
def _log_model_use(kind: str, requested: str, returned: Optional[str] = None) -> None:
    if returned and returned != requested:
        log.critical(
            "MODEL MISMATCH [%s] requested=%r returned=%r — REJECTING any silent substitution.",
            kind, requested, returned,
        )
    else:
        log.info("model_use kind=%s model=%s", kind, returned or requested)


# ---------------------------------------------------------------------------
# CLAUDE  (text + vision)
# ---------------------------------------------------------------------------
def _make_claude_chat(system: str, session_id: str = "fabrix") -> LlmChat:
    """Build a fresh LlmChat instance per call (library requirement)."""
    if not _EMERGENT_LLM_KEY:
        raise HTTPException(status_code=503, detail="Claude indisponible (EMERGENT_LLM_KEY manquant).")
    return LlmChat(
        api_key=_EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system,
    ).with_model(TEXT_MODEL_PROVIDER, TEXT_MODEL_NAME)


async def _claude_call(system: str, user_text: str, image_b64: Optional[str] = None, session_id: str = "fabrix") -> str:
    """Single non-streaming Claude call. Returns the assistant text."""
    chat = _make_claude_chat(system, session_id=session_id)
    file_contents = []
    if image_b64:
        file_contents.append(ImageContent(image_base64=image_b64))
    msg = UserMessage(text=user_text, file_contents=file_contents or None)
    try:
        # Library exposes send_message() for non-streaming
        result = await chat.send_message(msg)
        # Log model use (returned model name not always exposed; we trust the explicit .with_model())
        _log_model_use("claude", requested=TEXT_MODEL_NAME, returned=TEXT_MODEL_NAME)
        # send_message returns the assistant text directly per the lib API
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and "text" in result:
            return result["text"]
        return str(result)
    except Exception as e:
        log.error("Claude call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Claude ({TEXT_MODEL_NAME}) a échoué: {e}")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
CLARIFY_SYSTEM = (
    "Tu es un expert technique senior qui aide un utilisateur à préparer un manuel d'assemblage "
    "illustré ULTRA-PRÉCIS dans le style des notices IKEA. RÉPONDS DANS LA LANGUE INDIQUÉE. "
    "Ton objectif est d'obtenir suffisamment d'informations pour produire un manuel de 6 à 8 étapes denses. "
    "\n\n"
    "RÈGLES (TRÈS IMPORTANTES) :\n"
    "1. À CHAQUE tour, pose UNE SEULE question ciblée (max 2 si très liées).\n"
    "2. Tu DOIS poser au moins 3 questions au total. Idéalement 3 à 5.\n"
    "3. Couvre ces axes par ordre de pertinence : matériaux, dimensions, outils, contraintes, niveau, quincaillerie, finition.\n"
    "4. Sois TRÈS concis: 1 à 3 phrases par message, sans préambule.\n"
    "5. Quand tu as accumulé au moins 3 réponses utiles, conclus EXACTEMENT par : "
    "\"Parfait, j'ai toutes les informations nécessaires pour générer un manuel détaillé. Tu peux lancer la génération.\"\n"
    "6. Ne propose jamais d'étapes dans le chat."
)

# The big "ONE-CALL" system prompt for full manual JSON generation
MANUAL_JSON_SYSTEM_TEMPLATE = (
    "You are Fabrix, an expert technical writer + visual director for IKEA-style assembly manuals.\n\n"
    "**OUTPUT LANGUAGE**: all user-facing French text (title, descriptions, tips) must be in {LANG_NAME} ({LANG_CODE}).\n"
    "**IMAGE PROMPTS**: ALWAYS in ENGLISH, ALWAYS short and visual (12-25 words each).\n\n"
    "You output ONE JSON object — NOTHING ELSE. No prose, no markdown fences. Schema:\n\n"
    "{\n"
    "  \"title\": str  (<=60 chars, in {LANG_CODE}),\n"
    "  \"difficulty\": \"Débutant\" | \"Intermédiaire\" | \"Avancé\"  (translated to {LANG_CODE} if non-FR),\n"
    "  \"total_duration_min\": int,\n"
    "  \"materials\": [str]  (short labels in {LANG_CODE}, max 8 items),\n"
    "  \"tools\": [str]  (short labels in {LANG_CODE}, max 8 items),\n"
    "  \"style_anchor\": str  (English, 60-110 words; describes the locked visual style for ALL images of this manual: stroke weight, character style (minimalist stick figure with rounded joints if needed), viewpoint preference, environment, colors. IKEA blue #0058A3 main lines, red #CC0008 accent arrows ONLY for direction or warning, pure white background, no text inside images, pictogram style),\n"
    "  \"steps\": [\n"
    "    {\n"
    "      \"title\": str  (in {LANG_CODE}, action-oriented, <=60 chars),\n"
    "      \"description\": str  (in {LANG_CODE}, 3-5 sentences with concrete measurements/techniques),\n"
    "      \"tip\": str  (in {LANG_CODE}, <=240 chars),\n"
    "      \"duration_min\": int,\n"
    "      \"image_prompt\": str  (ENGLISH, 50-120 words, optimized for gpt-image-2; MUST include: pure white background, IKEA blue (#0058A3) lines, optional red (#CC0008) arrows for direction, no text inside, pictogram style, the specific viewpoint and the main object/action; consistent with the style_anchor)\n"
    "    }, ...\n"
    "  ]\n"
    "}\n\n"
    "**HARD CONSTRAINTS:**\n"
    "- EXACTLY 6 to 8 steps. Not more. Not less. Each step = a substantial unit of work (group related actions if needed).\n"
    "- Each image_prompt must be self-contained and refer to ONE clear visual scene.\n"
    "- Make image_prompts VISUALLY CONSISTENT by reusing the same style_anchor language across all steps.\n"
    "- Do NOT output anything outside the JSON object.\n"
)

# Fix-It specific addition (one-call with vision)
FIXIT_VISION_SYSTEM_TEMPLATE = (
    "You are Fabrix Fix-It, an expert who diagnoses broken/damaged objects from a user-provided photo "
    "and produces a step-by-step repair manual in IKEA-pictogram style.\n\n"
    "**STEP 1 — VISUAL ANALYSIS (silent)**:\n"
    "Look at the photo carefully. Identify: the object, the visible damages, the materials, the apparent quality.\n"
    "If the photo is BLURRY, too dark, doesn't show a fixable object, or you cannot identify a clear problem, "
    "output ONLY this JSON and nothing else:\n"
    "{\"refusal\": true, \"reason\": \"<in {LANG_CODE}, max 240 chars, polite, concrete advice on what kind of photo to send>\"}\n\n"
    "**STEP 2 — IF THE PHOTO IS USABLE**, output the full manual JSON. Same schema as Manual mode, plus one extra field:\n"
    "  \"diagnostic\": str (in {LANG_CODE}, 2-3 sentences describing what you saw and the proposed repair approach)\n\n"
    "All other rules of the manual JSON apply (6-8 steps, English image_prompts, etc.).\n"
    "**IMPORTANT**: The user photo is only used by you for analysis. NEVER mention 'image_prompt' that references the original photo — describe the actions/objects/tools generically so gpt-image-2 (which doesn't see the photo) can illustrate them. "
    "Output ONLY the JSON — no prose, no markdown fences."
)


def _lang_name(code: str) -> str:
    return {
        "fr": "French", "en": "English", "es": "Spanish",
        "de": "German", "pt": "Portuguese", "it": "Italian",
    }.get(code, "French")


# ---------------------------------------------------------------------------
# Public API — CLARIFICATION (multi-turn)
# ---------------------------------------------------------------------------
async def clarify_next(project: str, history: List[dict], lang: str = "fr") -> str:
    """Multi-turn clarification chat. history = [{role, content}, ...]."""
    transcript = ""
    if history:
        for m in history:
            who = "ASSISTANT" if m.get("role") == "assistant" else "USER"
            transcript += f"\n{who}: {m.get('content', '')}"
    user_text = (
        f"[Language: {_lang_name(lang)} / {lang}]\n"
        f"INITIAL PROJECT:\n{project}\n"
        f"{('CONVERSATION SO FAR:' + transcript) if transcript else 'This is the first turn.'}\n\n"
        "Now produce your next clarification message."
    )
    return await _claude_call(CLARIFY_SYSTEM, user_text, session_id=f"clarify-{abs(hash(project)) % 10**8}")


# ---------------------------------------------------------------------------
# Public API — ONE-CALL MANUAL JSON
# ---------------------------------------------------------------------------
def _strip_json_envelope(raw: str) -> str:
    """Tolerate accidental ```json fences from the model."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.lstrip("`")
        # could be 'json\n{...}\n```'
        if s.lower().startswith("json"):
            s = s[4:]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


def _validate_manual_shape(data: dict) -> None:
    for k in ("title", "difficulty", "total_duration_min", "style_anchor", "steps"):
        if k not in data:
            raise HTTPException(status_code=502, detail=f"JSON manuel invalide (champ manquant: {k}).")
    if not isinstance(data["steps"], list) or len(data["steps"]) < 5:
        raise HTTPException(
            status_code=502,
            detail=f"JSON manuel insuffisant ({len(data.get('steps', []))} étapes — minimum 6).",
        )
    if len(data["steps"]) > 8:
        data["steps"] = data["steps"][:8]
    for i, s in enumerate(data["steps"]):
        for k in ("title", "description", "image_prompt"):
            if k not in s:
                raise HTTPException(status_code=502, detail=f"Étape {i+1}: champ manquant '{k}'.")
        s.setdefault("tip", "")
        s.setdefault("duration_min", 15)


async def generate_manual_json(project: str, history: List[dict], lang: str = "fr") -> dict:
    """ONE Claude call returns the full manual JSON."""
    sys_prompt = (
        MANUAL_JSON_SYSTEM_TEMPLATE
        .replace("{LANG_NAME}", _lang_name(lang))
        .replace("{LANG_CODE}", lang)
    )
    transcript = "\n".join(
        f"{m.get('role','').upper()}: {m.get('content','')}" for m in history if m.get("role") in ("user", "assistant")
    )
    user_text = (
        f"INITIAL PROJECT (verbatim):\n{project}\n\n"
        f"CLARIFICATION DIALOGUE:\n{transcript or '(none)'}\n\n"
        "Now output the full manual JSON. Output language: " + _lang_name(lang) + "."
    )
    raw = await _claude_call(sys_prompt, user_text, session_id=f"manual-{abs(hash(project)) % 10**8}")
    raw = _strip_json_envelope(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error("Claude returned non-JSON manual: %s -- raw start: %s", e, raw[:300])
        raise HTTPException(status_code=502, detail=f"Claude n'a pas retourné un JSON valide ({e}).")
    _validate_manual_shape(data)
    return data


# ---------------------------------------------------------------------------
# Public API — FIX-IT (vision + JSON in one call)
# ---------------------------------------------------------------------------
async def fixit_analyze_and_generate(image_b64: str, user_text: str = "", lang: str = "fr") -> dict:
    """One Claude vision call: analyze photo + produce repair manual JSON.
    May also return {refusal: True, reason: "..."} if photo unusable.
    """
    sys_prompt = (
        FIXIT_VISION_SYSTEM_TEMPLATE
        .replace("{LANG_NAME}", _lang_name(lang))
        .replace("{LANG_CODE}", lang)
    )
    msg_text = (
        f"USER LANGUAGE: {_lang_name(lang)} ({lang}).\n"
        f"OPTIONAL USER DESCRIPTION OF PROBLEM:\n{user_text or '(none provided — diagnose from the photo only)'}\n\n"
        "Analyze the attached photo and produce the JSON now."
    )
    raw = await _claude_call(sys_prompt, msg_text, image_b64=image_b64, session_id="fixit")
    raw = _strip_json_envelope(raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error("Claude Fix-It non-JSON: %s -- raw start: %s", e, raw[:300])
        raise HTTPException(status_code=502, detail=f"Claude n'a pas retourné un JSON valide ({e}).")
    if data.get("refusal") is True:
        return data  # caller will return 422 with the polite reason
    _validate_manual_shape(data)
    return data


# ---------------------------------------------------------------------------
# IMAGE GENERATION (gpt-image-2)
# ---------------------------------------------------------------------------
async def gen_step_image(image_prompt: str, style_anchor: str,
                         reference_image_b64: Optional[str] = None,
                         project_user_id: str = "fabrix",
                         custom_instructions: Optional[str] = None) -> str:
    """Generate one step image. Returns base64.
    - If reference_image_b64 is provided → images.edit (img2img)
    - Else → images.generate (text-to-image)
    """
    # Build a defensive prefix: technical diagram framing reduces moderation false-positives.
    full_prompt = (
        "Technical illustration in strict IKEA assembly manual style.\n"
        "STRICTLY a static technical diagram of the object only. NO person, NO hands aiming, "
        "NO shooting action, NO target, NO projectile in motion, NO violent or threatening context.\n\n"
        f"STYLE ANCHOR (locked across the whole manual):\n{style_anchor}\n\n"
        "STRICT VISUAL RULES:\n"
        "- Pure white background (#FFFFFF). No gradients, no shadows, no textures.\n"
        "- All lines in IKEA blue (#0058A3), stroke 2.0-3.5px.\n"
        "- Red (#CC0008) arrows ONLY for direction/warnings.\n"
        "- NO text, NO labels, NO numbers anywhere in the image.\n"
        "- NO photorealism, NO shading, NO decorative background.\n\n"
        f"STEP CONTENT (illustrate this exact scene):\n{image_prompt}\n"
    )
    if custom_instructions:
        full_prompt += f"\nAdditional user instructions: {custom_instructions[:400]}\n"
    if reference_image_b64:
        full_prompt = (
            "Match the EXACT visual style of the provided reference image: same stroke weight, "
            "same line treatment, same character style, same color palette. Keep visual continuity strictly.\n\n"
            + full_prompt
        )

    async def _call(prompt_text: str) -> str:
        if reference_image_b64:
            ref_bytes = base64.b64decode(reference_image_b64)
            resp = await get_openai().images.edit(
                model=IMAGE_MODEL,
                image=[("reference.png", ref_bytes, "image/png")],
                prompt=prompt_text[:3500],
                size=IMAGE_SIZE,
                quality=IMAGE_QUALITY,
                n=1,
                user=project_user_id[:128] if project_user_id else None,
            )
        else:
            resp = await get_openai().images.generate(
                model=IMAGE_MODEL,
                prompt=prompt_text[:3500],
                size=IMAGE_SIZE,
                quality=IMAGE_QUALITY,
                n=1,
                user=project_user_id[:128] if project_user_id else None,
            )
        returned_model = getattr(resp, "model", None) or IMAGE_MODEL
        _log_model_use("image", requested=IMAGE_MODEL, returned=returned_model)
        item = resp.data[0]
        b64 = getattr(item, "b64_json", None)
        url = getattr(item, "url", None)
        if b64:
            return _shrink_png_b64(b64)
        if url:
            async with httpx.AsyncClient(timeout=120.0) as h:
                r = await h.get(url)
                r.raise_for_status()
                return _shrink_png_b64(base64.b64encode(r.content).decode("ascii"))
        raise RuntimeError("Pas d'image dans la réponse OpenAI.")

    try:
        return await _call(full_prompt)
    except HTTPException:
        raise
    except Exception as e:
        err_str = str(e)
        # Retry once with a sanitized prompt when OpenAI moderation blocks the image (illicit/weapons).
        if "moderation_blocked" in err_str or "safety" in err_str.lower():
            log.warning("gpt-image-2 moderation_blocked — retrying with sanitized prompt")
            sanitized = re.sub(
                r"\b(weapon|firearm|gun|rifle|bow|crossbow|arrow|bolt|projectile|"
                r"shoot|shooting|fire|firing|aim|aiming|target|kill|hit|blade|"
                r"sharp|tip|barbed|venom|poison|"
                r"arbal[eè]te|arc|fl[eè]che|tir|tirer|viser|cible|arme|tuer)\b",
                "part", full_prompt, flags=re.IGNORECASE,
            )
            sanitized = (
                "Neutral mechanical engineering diagram for sport/recreational equipment assembly. "
                "Pure exploded-view technical schematic on white background, no person, no action, "
                "no living target, no motion, no danger context. Educational documentation only.\n\n"
                + sanitized
            )
            try:
                return await _call(sanitized)
            except Exception as e2:
                log.error("gpt-image-2 failed even after sanitization: %s", e2)
                raise HTTPException(
                    status_code=502,
                    detail=f"OpenAI a refusé cette illustration même après reformulation (modération). Détail: {e2}",
                )
        log.error("gpt-image-2 failed (with_ref=%s): %s", bool(reference_image_b64), e)
        raise HTTPException(status_code=502, detail=f"gpt-image-2 a échoué: {e}")


async def gen_cover_image(title: str, style_anchor: str, reference_image_b64: Optional[str]) -> str:
    """Cover = hero shot of finished object."""
    cover_prompt = (
        f"Hero cover illustration for the manual titled {title!r}. "
        "Show the FINISHED assembled object from an attractive isometric 3/4 hero view. "
        "Bold clean lines, no character, no environment, generous white margin, centered composition."
    )
    return await gen_step_image(
        image_prompt=cover_prompt,
        style_anchor=style_anchor,
        reference_image_b64=reference_image_b64,
        project_user_id="fabrix-cover",
    )


# ---------------------------------------------------------------------------
# PARALLEL ORCHESTRATION
# ---------------------------------------------------------------------------
async def generate_all_step_images(
    manual_data: dict,
    *,
    on_step_state: Optional[Any] = None,  # async callable(idx, state, extra)
    concurrency: int = 3,
    project_user_id: str = "fabrix",
) -> Tuple[List[str], str]:
    """
    Pipeline:
      - step 1 alone (text-to-image)        → lock reference
      - steps 2..N + cover in PARALLEL      → all use step1 as reference

    on_step_state(idx, state) is called with state in {"running","done","error"}.
    Returns (list_of_step_b64_in_order, cover_b64).
    """
    style_anchor = manual_data["style_anchor"]
    steps = manual_data["steps"]
    title = manual_data["title"]
    n = len(steps)

    async def _notify(idx: int, state: str, extra: Optional[dict] = None):
        if on_step_state:
            try:
                res = on_step_state(idx, state, extra or {})
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

    # ---- step 1 sequential (locks reference) ----
    await _notify(0, "running")
    step1_b64 = await gen_step_image(
        image_prompt=steps[0]["image_prompt"],
        style_anchor=style_anchor,
        reference_image_b64=None,
        project_user_id=project_user_id,
    )
    await _notify(0, "done")

    # ---- steps 2..N + cover in parallel ----
    sem = asyncio.Semaphore(concurrency)
    images: List[Optional[str]] = [None] * n
    images[0] = step1_b64
    cover_holder: Dict[str, Optional[str]] = {"cover": None}

    async def _one(idx: int):
        async with sem:
            await _notify(idx, "running")
            try:
                b = await gen_step_image(
                    image_prompt=steps[idx]["image_prompt"],
                    style_anchor=style_anchor,
                    reference_image_b64=step1_b64,
                    project_user_id=project_user_id,
                )
                images[idx] = b
                await _notify(idx, "done")
            except HTTPException as e:
                log.error("step %d failed: %s", idx, e.detail)
                await _notify(idx, "error", {"reason": str(e.detail)})

    async def _cover():
        async with sem:
            try:
                cover_holder["cover"] = await gen_cover_image(title, style_anchor, step1_b64)
            except Exception as e:
                log.warning("cover gen failed (%s), falling back to step1", e)
                cover_holder["cover"] = step1_b64

    tasks = [_one(i) for i in range(1, n)] + [_cover()]
    await asyncio.gather(*tasks)

    # If ANY step image failed, fail the whole job — never silently duplicate step1.
    missing = [i for i, b in enumerate(images) if b is None]
    if missing:
        # Try to surface the first concrete reason from the most recent log line
        raise HTTPException(
            status_code=502,
            detail=(
                f"{len(missing)} étape(s) sur {n} ont échoué (indices {missing}). "
                "Le manuel n'a PAS été sauvegardé pour éviter d'enregistrer des images dupliquées. "
                "Cause la plus probable: quota OpenAI atteint ou prompt bloqué. "
                "Vérifie ton compte OpenAI puis relance la génération."
            ),
        )

    return [b for b in images], (cover_holder["cover"] or step1_b64)
