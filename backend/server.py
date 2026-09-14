"""
ManuelIA v2 \u2014 main FastAPI server.

Routes are mounted under /api/.
Auth: JWT bearer.
AI: OpenAI GPT-4o for text, gpt-image-1 for images (DALL\u00b7E 3 unavailable on this OpenAI account).
"""
from __future__ import annotations

import os
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Header, BackgroundTasks, Response, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import models as M
import auth as A
import ai_service as AI
import stripe_service as STP
from pdf_service import render_manual_pdf
import jobs as J

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
log = logging.getLogger("server")

# -----------------------------------------------------------------------------
# Mongo
# -----------------------------------------------------------------------------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo[DB_NAME]

users_col = db["users"]
manuals_col = db["manuals"]
events_col = db["events"]
usage_col = db["usage"]
jobs_col = db["jobs"]

# initialize the Mongo-backed job tracker
job_tracker = J.init_tracker(jobs_col)

# Concurrency for parallel image gen — OpenAI tolerates ~5 parallel image calls comfortably
IMAGE_CONCURRENCY = int(os.environ.get("IMAGE_CONCURRENCY", "3"))

# -----------------------------------------------------------------------------
# FastAPI
# -----------------------------------------------------------------------------
app = FastAPI(title="Fabrix API")

api = APIRouter(prefix="/api")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _user_public(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u.get("name"),
        "plan": u.get("plan", "free"),
        "credits": u.get("credits", 3),
        "email_notifications": u.get("email_notifications", True),
        "public_by_default": u.get("public_by_default", False),
        "created_at": u.get("created_at"),
    }


async def _get_user(user_id: str) -> dict:
    u = await users_col.find_one({"id": user_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return u


async def _summary_from_doc(doc: dict) -> dict:
    """Return ManualSummary-shape (no full steps, includes cover thumbnail)."""
    return {
        "id": doc["id"],
        "title": doc.get("title", ""),
        "difficulty": doc.get("difficulty", ""),
        "total_duration_min": doc.get("total_duration_min", 0),
        "step_count": len(doc.get("steps", [])),
        "is_public": bool(doc.get("is_public", False)),
        "cover_image_base64": doc.get("cover_image_base64"),
        "created_at": doc.get("created_at"),
        "status": doc.get("status", "complete"),
    }


# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@api.get("/")
async def root():
    return {
        "service": "Fabrix",
        "status": "ok",
        "models": {"text": AI.TEXT_MODEL_NAME, "image": AI.IMAGE_MODEL},
    }


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
@api.post("/auth/signup", response_model=M.AuthResponse)
async def signup(payload: M.SignupRequest):
    email = payload.email.lower().strip()
    existing = await users_col.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="Un compte existe d\u00e9j\u00e0 avec cet email.")

    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": payload.name or email.split("@")[0],
        "password_hash": A.hash_password(payload.password),
        "plan": "free",
        "credits": 3,
        "email_notifications": True,
        "public_by_default": False,
        "stripe_customer_id": None,
        "created_at": _now_iso(),
    }
    await users_col.insert_one(user)
    token = A.create_access_token(user["id"], user["email"])
    return {"access_token": token, "user": _user_public(user)}


@api.post("/auth/login", response_model=M.AuthResponse)
async def login(payload: M.LoginRequest):
    email = payload.email.lower().strip()
    u = await users_col.find_one({"email": email})
    if not u or not A.verify_password(payload.password, u.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")
    token = A.create_access_token(u["id"], u["email"])
    return {"access_token": token, "user": _user_public(u)}


@api.get("/auth/me", response_model=M.UserPublic)
async def me(current=Depends(A.get_current_user)):
    u = await _get_user(current["id"])
    return _user_public(u)


@api.patch("/auth/me", response_model=M.UserPublic)
async def update_prefs(payload: M.UpdatePrefsRequest, current=Depends(A.get_current_user)):
    update = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if update:
        await users_col.update_one({"id": current["id"]}, {"$set": update})
    u = await _get_user(current["id"])
    return _user_public(u)


@api.delete("/auth/me")
async def delete_account(current=Depends(A.get_current_user)):
    await manuals_col.delete_many({"user_id": current["id"]})
    await users_col.delete_one({"id": current["id"]})
    return {"deleted": True}


# -----------------------------------------------------------------------------
# Clarification chat (Claude Sonnet 4.5)
# -----------------------------------------------------------------------------
@api.post("/ai/clarify", response_model=M.ClarifyResponse)
async def clarify(payload: M.ClarifyRequest, current=Depends(A.get_current_user)):
    history = [m.model_dump() for m in payload.history]
    lang = (payload.lang or "fr")[:2]
    reply = await AI.clarify_next(payload.project, history, lang=lang)
    return {"reply": reply}


# -----------------------------------------------------------------------------
# Manual generation \u2014 async with Mongo-backed progress
# -----------------------------------------------------------------------------
async def _generate_manual_job(
    job_id: str, user_id: str, project: str, history: List[dict], lang: str = "fr",
):
    try:
        await job_tracker.update(
            job_id, state="running", progress=4,
            label="Analyse", status_text="Claude Sonnet 4.5 r\u00e9dige le manuel\u2026",
        )

        manual = await AI.generate_manual_json(project, history, lang=lang)

        # initialise per-step grid now that we know the count
        step_titles = [s["title"] for s in manual["steps"]]
        await job_tracker.set_steps(job_id, step_titles)
        await job_tracker.update(
            job_id, progress=15,
            label="Plan g\u00e9n\u00e9r\u00e9", status_text=f"{len(manual['steps'])} \u00e9tapes r\u00e9dig\u00e9es. Image 1\u2026",
        )

        manual_uid = str(uuid.uuid4())

        # Per-step state notifier (async)
        async def _on_step_state(idx: int, state: str, extra: dict):
            await job_tracker.update_step(job_id, idx, state=state)
            n = len(manual["steps"])
            # progress = 15 + 80 * (done_count / n)
            cur = await job_tracker.get(job_id)
            done = sum(1 for s in (cur or {}).get("steps_status", []) if s.get("state") == "done")
            await job_tracker.update(
                job_id,
                progress=int(15 + (80 * done / max(n, 1))),
                label=f"Image {done}/{n}",
                status_text=f"\u00c9tape {idx+1} {state}\u2026",
            )

        step_images, cover_b64 = await AI.generate_all_step_images(
            manual,
            on_step_state=_on_step_state,
            concurrency=int(os.environ.get("IMAGE_CONCURRENCY", "3")),
            project_user_id=manual_uid,
        )

        await job_tracker.update(
            job_id, progress=96,
            label="Sauvegarde", status_text="Enregistrement du manuel\u2026",
        )

        user = await _get_user(user_id)
        # Build persisted steps
        steps_out = []
        for i, s in enumerate(manual["steps"]):
            steps_out.append({
                "id": str(uuid.uuid4()),
                "index": i,
                "title": s["title"],
                "description": s.get("description", ""),
                "tip": s.get("tip", ""),
                "duration_min": int(s.get("duration_min", 0) or 0),
                "image_prompt": s.get("image_prompt", ""),
                "image_base64": step_images[i],
                "image_mime": "image/png",
                "image_custom_instructions": None,
            })

        doc = {
            "id": manual_uid,
            "user_id": user_id,
            "kind": "manual",
            "title": manual["title"],
            "difficulty": manual.get("difficulty", "Interm\u00e9diaire"),
            "total_duration_min": int(manual.get("total_duration_min", 0) or 0),
            "materials": manual.get("materials", []),
            "tools": manual.get("tools", []),
            "lang": lang,
            "project": project,
            "history": history,
            "style_anchor": manual["style_anchor"],
            "reference_image_b64": step_images[0],
            "steps": steps_out,
            "cover_image_base64": cover_b64,
            "is_public": bool(user.get("public_by_default", False)),
            "pdf_unlocked": False,
            "status": "complete",
            "created_at": _now_iso(),
        }
        await manuals_col.insert_one(doc)

        await usage_col.update_one(
            {"user_id": user_id},
            {"$inc": {"manuals_created": 1, "images_generated": len(steps_out) + 1}},
            upsert=True,
        )

        await job_tracker.update(
            job_id, state="done", progress=100,
            label="Termin\u00e9", status_text="Manuel pr\u00eat \u2728",
            manual_id=doc["id"],
        )
    except HTTPException as e:
        log.error("manual gen failed: %s", e.detail)
        await job_tracker.update(job_id, state="error", error=str(e.detail))
    except Exception as e:
        log.exception("manual gen exception")
        await job_tracker.update(job_id, state="error", error=str(e))


@api.post("/manuals/generate")
async def start_generation(payload: M.CreateManualRequest, background: BackgroundTasks, current=Depends(A.get_current_user)):
    user = await _get_user(current["id"])
    if user.get("plan", "free") != "pro" and int(user.get("credits", 0)) <= 0:
        raise HTTPException(status_code=402, detail="Cr\u00e9dits insuffisants \u2014 passe au Pro ou ach\u00e8te un pack.")

    history = [m.model_dump() for m in payload.history]
    lang = (payload.lang or "fr")[:2]

    job_id = await job_tracker.create(user["id"], n_steps=0)
    if user.get("plan", "free") != "pro":
        await users_col.update_one({"id": user["id"]}, {"$inc": {"credits": -1}})

    background.add_task(_generate_manual_job, job_id, user["id"], payload.project, history, lang)
    return {"job_id": job_id}


# -----------------------------------------------------------------------------
# Fix-It (photo \u2192 Claude Vision \u2192 manual JSON \u2192 parallel images)
# -----------------------------------------------------------------------------
async def _generate_fixit_job(job_id: str, user_id: str, manual_data: dict, lang: str = "fr"):
    try:
        step_titles = [s["title"] for s in manual_data["steps"]]
        await job_tracker.set_steps(job_id, step_titles)
        await job_tracker.update(
            job_id, state="running", progress=15,
            label="Plan g\u00e9n\u00e9r\u00e9", status_text=f"{len(step_titles)} \u00e9tapes r\u00e9dig\u00e9es. Image 1\u2026",
        )
        manual_uid = str(uuid.uuid4())

        async def _on_step_state(idx: int, state: str, extra: dict):
            await job_tracker.update_step(job_id, idx, state=state)
            n = len(step_titles)
            cur = await job_tracker.get(job_id)
            done = sum(1 for s in (cur or {}).get("steps_status", []) if s.get("state") == "done")
            await job_tracker.update(
                job_id,
                progress=int(15 + (80 * done / max(n, 1))),
                label=f"Image {done}/{n}",
                status_text=f"\u00c9tape {idx+1} {state}\u2026",
            )

        step_images, cover_b64 = await AI.generate_all_step_images(
            manual_data,
            on_step_state=_on_step_state,
            concurrency=int(os.environ.get("IMAGE_CONCURRENCY", "3")),
            project_user_id=manual_uid,
        )

        user = await _get_user(user_id)
        steps_out = []
        for i, s in enumerate(manual_data["steps"]):
            steps_out.append({
                "id": str(uuid.uuid4()),
                "index": i,
                "title": s["title"],
                "description": s.get("description", ""),
                "tip": s.get("tip", ""),
                "duration_min": int(s.get("duration_min", 0) or 0),
                "image_prompt": s.get("image_prompt", ""),
                "image_base64": step_images[i],
                "image_mime": "image/png",
                "image_custom_instructions": None,
            })

        doc = {
            "id": manual_uid,
            "user_id": user_id,
            "kind": "fixit",
            "title": manual_data["title"],
            "diagnostic": manual_data.get("diagnostic", ""),
            "difficulty": manual_data.get("difficulty", "Interm\u00e9diaire"),
            "total_duration_min": int(manual_data.get("total_duration_min", 0) or 0),
            "materials": manual_data.get("materials", []),
            "tools": manual_data.get("tools", []),
            "lang": lang,
            "project": "(Fix-It from photo)",
            "history": [],
            "style_anchor": manual_data["style_anchor"],
            "reference_image_b64": step_images[0],
            "steps": steps_out,
            "cover_image_base64": cover_b64,
            "is_public": bool(user.get("public_by_default", False)),
            "pdf_unlocked": False,
            "status": "complete",
            "created_at": _now_iso(),
        }
        await manuals_col.insert_one(doc)
        await usage_col.update_one(
            {"user_id": user_id},
            {"$inc": {"manuals_created": 1, "images_generated": len(steps_out) + 1}},
            upsert=True,
        )
        await job_tracker.update(
            job_id, state="done", progress=100,
            label="Termin\u00e9", status_text="Fix-It pr\u00eat \u2728",
            manual_id=doc["id"],
        )
    except HTTPException as e:
        log.error("fixit gen failed: %s", e.detail)
        await job_tracker.update(job_id, state="error", error=str(e.detail))
    except Exception as e:
        log.exception("fixit gen exception")
        await job_tracker.update(job_id, state="error", error=str(e))


@api.post("/fixit/generate")
async def fixit_generate(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    lang: Optional[str] = Form("fr"),
    current=Depends(A.get_current_user),
):
    # Validate file
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Format non support\u00e9. JPG, PNG ou WEBP requis.")
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Photo trop volumineuse (max 10 Mo).")
    if len(contents) < 1024:
        raise HTTPException(status_code=400, detail="Photo trop petite ou invalide.")

    user = await _get_user(current["id"])
    if user.get("plan", "free") != "pro" and int(user.get("credits", 0)) <= 0:
        raise HTTPException(status_code=402, detail="Cr\u00e9dits insuffisants.")

    import base64 as _b64
    image_b64 = _b64.b64encode(contents).decode("ascii")
    lang_c = (lang or "fr")[:2]

    # Synchronous Claude vision call (analysis + JSON or refusal)
    data = await AI.fixit_analyze_and_generate(image_b64, description or "", lang=lang_c)
    if data.get("refusal") is True:
        # Don't charge a credit on refusal
        return {"refusal": True, "reason": data.get("reason", "Photo inexploitable.")}

    # Pre-decrement credits (only here, after analysis succeeded)
    if user.get("plan", "free") != "pro":
        await users_col.update_one({"id": user["id"]}, {"$inc": {"credits": -1}})

    job_id = await job_tracker.create(user["id"], n_steps=len(data["steps"]),
                                      step_titles=[s["title"] for s in data["steps"]])
    background.add_task(_generate_fixit_job, job_id, user["id"], data, lang_c)
    return {"job_id": job_id, "preview": {"title": data["title"], "diagnostic": data.get("diagnostic", "")}}


@api.get("/manuals/jobs/active")
async def get_active_job(current=Depends(A.get_current_user)):
    j = await job_tracker.get_active_for_user(current["id"])
    return j or {}


@api.get("/manuals/jobs/{job_id}")
async def get_job(job_id: str, current=Depends(A.get_current_user)):
    j = await job_tracker.get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job introuvable.")
    return j


# -----------------------------------------------------------------------------
# Step image regeneration (single + all)
# -----------------------------------------------------------------------------
@api.post("/manuals/{manual_id}/steps/{step_id}/regen")
async def regen_step_image(
    manual_id: str, step_id: str, payload: M.RegenStepRequest, current=Depends(A.get_current_user),
):
    doc = await manuals_col.find_one({"id": manual_id, "user_id": current["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Manuel introuvable.")

    steps = doc.get("steps", [])
    target_idx = next((i for i, s in enumerate(steps) if s["id"] == step_id), None)
    if target_idx is None:
        raise HTTPException(status_code=404, detail="\u00c9tape introuvable.")

    step = steps[target_idx]
    style_anchor = doc.get("style_anchor") or "Strict IKEA notice style. Pure white background. IKEA blue (#0058A3) lines. Red (#CC0008) arrows for direction. Pictogram, no shading, no text."
    stored_ref = doc.get("reference_image_b64")
    ref_for_this = None if target_idx == 0 else stored_ref

    image_prompt = step.get("image_prompt") or f"{step.get('title','')}. {step.get('description','')}"

    b64 = await AI.gen_step_image(
        image_prompt=image_prompt,
        style_anchor=style_anchor,
        reference_image_b64=ref_for_this,
        project_user_id=manual_id,
        custom_instructions=payload.custom_instructions,
    )

    steps[target_idx]["image_base64"] = b64
    steps[target_idx]["image_custom_instructions"] = payload.custom_instructions or None
    update_fields = {"steps": steps, "style_anchor": style_anchor}
    if target_idx == 0:
        update_fields["reference_image_b64"] = b64
    await manuals_col.update_one({"id": manual_id}, {"$set": update_fields})

    await usage_col.update_one(
        {"user_id": current["id"]},
        {"$inc": {"images_generated": 1}},
        upsert=True,
    )

    return {"ok": True, "step_id": step_id}


async def _regen_all_job(job_id: str, user_id: str, manual_id: str):
    try:
        doc = await manuals_col.find_one({"id": manual_id, "user_id": user_id}, {"_id": 0})
        if not doc:
            await job_tracker.update(job_id, state="error", error="Manuel introuvable")
            return
        steps = doc.get("steps", [])
        if not steps:
            await job_tracker.update(job_id, state="done", progress=100, label="Vide", status_text="Aucune \u00e9tape.")
            return

        await job_tracker.set_steps(job_id, [s["title"] for s in steps])

        # Build a manual_data-like dict so we can reuse generate_all_step_images
        style_anchor = doc.get("style_anchor") or "Strict IKEA notice style. Pure white background. IKEA blue (#0058A3) lines. Red (#CC0008) arrows for direction. Pictogram, no shading, no text."
        manual_data = {
            "title": doc.get("title", ""),
            "style_anchor": style_anchor,
            "steps": [
                {"title": s["title"], "image_prompt": s.get("image_prompt") or f"{s.get('title','')}. {s.get('description','')}"}
                for s in steps
            ],
        }

        async def _cb(idx: int, state: str, extra: dict):
            await job_tracker.update_step(job_id, idx, state=state)
            n = len(steps)
            cur = await job_tracker.get(job_id)
            done = sum(1 for s in (cur or {}).get("steps_status", []) if s.get("state") == "done")
            await job_tracker.update(
                job_id,
                state="running",
                progress=int((done / max(n, 1)) * 100),
                label=f"Image {done}/{n}",
                status_text=f"\u00c9tape {idx+1} {state}\u2026",
            )

        new_imgs, new_cover = await AI.generate_all_step_images(
            manual_data,
            on_step_state=_cb,
            concurrency=int(os.environ.get("IMAGE_CONCURRENCY", "3")),
            project_user_id=manual_id,
        )

        # write back
        for i, s in enumerate(steps):
            s["image_base64"] = new_imgs[i]
            s["image_custom_instructions"] = None
        await manuals_col.update_one(
            {"id": manual_id},
            {"$set": {
                "steps": steps,
                "style_anchor": style_anchor,
                "reference_image_b64": new_imgs[0],
                "cover_image_base64": new_cover,
            }},
        )

        await usage_col.update_one(
            {"user_id": user_id},
            {"$inc": {"images_generated": len(steps)}},
            upsert=True,
        )
        await job_tracker.update(job_id, state="done", progress=100, label="Termin\u00e9",
                                 status_text="Toutes les images ont \u00e9t\u00e9 r\u00e9g\u00e9n\u00e9r\u00e9es.")
    except Exception as e:
        log.exception("regen-all failed")
        await job_tracker.update(job_id, state="error", error=str(e))




# -----------------------------------------------------------------------------
# Manual CRUD
# -----------------------------------------------------------------------------
@api.get("/manuals")
async def list_manuals(current=Depends(A.get_current_user)):
    cursor = manuals_col.find({"user_id": current["id"]}, {"_id": 0}).sort("created_at", -1)
    out = []
    async for doc in cursor:
        out.append(await _summary_from_doc(doc))
    return out


@api.get("/manuals/{manual_id}")
async def get_manual(manual_id: str, current=Depends(A.get_current_user)):
    doc = await manuals_col.find_one({"id": manual_id, "user_id": current["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Manuel introuvable.")
    return doc


@api.get("/manuals/{manual_id}/public")
async def get_manual_public(manual_id: str):
    doc = await manuals_col.find_one({"id": manual_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Manuel introuvable.")
    if not doc.get("is_public", False):
        raise HTTPException(status_code=403, detail="Ce manuel n'est pas public.")
    doc.pop("user_id", None)
    return doc


@api.delete("/manuals/{manual_id}")
async def delete_manual(manual_id: str, current=Depends(A.get_current_user)):
    res = await manuals_col.delete_one({"id": manual_id, "user_id": current["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Manuel introuvable.")
    return {"deleted": True}


@api.delete("/manuals")
async def delete_all_manuals(current=Depends(A.get_current_user)):
    res = await manuals_col.delete_many({"user_id": current["id"]})
    return {"deleted": res.deleted_count}


@api.patch("/manuals/{manual_id}/public")
async def toggle_public(manual_id: str, payload: M.TogglePublicRequest, current=Depends(A.get_current_user)):
    res = await manuals_col.update_one(
        {"id": manual_id, "user_id": current["id"]},
        {"$set": {"is_public": payload.is_public}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Manuel introuvable.")
    return {"is_public": payload.is_public}


@api.patch("/manuals/{manual_id}/pdf-unlock")
async def admin_pdf_unlock(manual_id: str, current=Depends(A.get_current_user)):
    """For now an authenticated owner can self-unlock — pricing logic to come later."""
    res = await manuals_col.update_one(
        {"id": manual_id, "user_id": current["id"]},
        {"$set": {"pdf_unlocked": True}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Manuel introuvable.")
    return {"pdf_unlocked": True}


@api.post("/manuals/{manual_id}/regen-all")
async def regen_all(manual_id: str, background: BackgroundTasks, current=Depends(A.get_current_user)):
    doc = await manuals_col.find_one({"id": manual_id, "user_id": current["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Manuel introuvable.")
    job_id = await job_tracker.create(current["id"], n_steps=len(doc.get("steps", [])),
                                      step_titles=[s.get("title", "") for s in doc.get("steps", [])])
    background.add_task(_regen_all_job, job_id, current["id"], manual_id)
    return {"job_id": job_id}


# -----------------------------------------------------------------------------
# Usage stats
# -----------------------------------------------------------------------------
@api.get("/usage")
async def get_usage(current=Depends(A.get_current_user)):
    u = await usage_col.find_one({"user_id": current["id"]}, {"_id": 0}) or {}
    count_manuals = await manuals_col.count_documents({"user_id": current["id"]})
    return {
        "manuals_created": count_manuals,
        "images_generated": int(u.get("images_generated", 0)),
        "pdfs_exported": int(u.get("pdfs_exported", 0)),
    }


# -----------------------------------------------------------------------------
# PDF
# -----------------------------------------------------------------------------
@api.get("/manuals/{manual_id}/export/pdf")
async def export_pdf(manual_id: str, current=Depends(A.get_current_user)):
    doc = await manuals_col.find_one({"id": manual_id, "user_id": current["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Manuel introuvable.")
    if not doc.get("pdf_unlocked", False):
        raise HTTPException(status_code=402, detail="Export PDF verrouillé — déverrouille d'abord ce manuel.")
    pdf_bytes = render_manual_pdf(doc)
    await usage_col.update_one(
        {"user_id": current["id"]},
        {"$inc": {"pdfs_exported": 1}},
        upsert=True,
    )
    fname = f"manuelia-{doc.get('title','manuel').replace(' ', '_')[:40]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# -----------------------------------------------------------------------------
# Stripe checkout + webhook
# -----------------------------------------------------------------------------
@api.post("/stripe/checkout/subscription")
async def checkout_sub(current=Depends(A.get_current_user)):
    u = await _get_user(current["id"])
    url = STP.create_subscription_session(u["id"], u["email"])
    return {"url": url}


@api.post("/stripe/checkout/credits")
async def checkout_credits(payload: M.CheckoutCreditsRequest, current=Depends(A.get_current_user)):
    u = await _get_user(current["id"])
    url = STP.create_credits_session(u["id"], u["email"], payload.pack)
    return {"url": url}


@api.post("/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature")):
    payload = await request.body()
    event = STP.verify_webhook(payload, stripe_signature or "")

    obj = event["data"]["object"] if "data" in event else {}
    customer = obj.get("customer")
    amount = obj.get("amount_total") or obj.get("amount_paid") or obj.get("amount_received")
    print(f"[STRIPE WEBHOOK] event={event['type']} | customer={customer} | amount_paid={amount}")

    # Persist raw event
    try:
        await events_col.insert_one({
            "id": str(uuid.uuid4()),
            "type": event["type"],
            "received_at": _now_iso(),
            "payload": dict(obj) if isinstance(obj, dict) else {},
        })
    except Exception:
        log.exception("stripe event persist failed")

    metadata = (obj.get("metadata") or {}) if isinstance(obj, dict) else {}
    user_id = metadata.get("user_id") if isinstance(metadata, dict) else None

    if event["type"] == "checkout.session.completed" and user_id:
        kind = metadata.get("kind")
        if kind == "credits":
            credits_added = int(metadata.get("credits", "0") or "0")
            if credits_added > 0:
                res = await users_col.find_one_and_update(
                    {"id": user_id},
                    {"$inc": {"credits": credits_added}},
                    return_document=True,
                )
                new_total = (res or {}).get("credits") if res else None
                if new_total is None:
                    # Fetch separately if returned doc didn't include credits
                    u = await users_col.find_one({"id": user_id}, {"credits": 1, "_id": 0})
                    new_total = (u or {}).get("credits")
                print(f"[STRIPE WEBHOOK] Cr\u00e9dits ajout\u00e9s \u2192 user_id={user_id} | cr\u00e9dits={credits_added} | nouveau_total={new_total}")
        elif kind == "subscription":
            await users_col.update_one({"id": user_id}, {"$set": {"plan": "pro"}})
            print(f"[STRIPE WEBHOOK] Plan Pro activ\u00e9 \u2192 user_id={user_id}")

    if event["type"] in ("customer.subscription.deleted", "invoice.payment_failed"):
        # Best-effort downgrade if Stripe customer is mapped via email
        email = obj.get("customer_email") or obj.get("customer_details", {}).get("email") if isinstance(obj, dict) else None
        if email:
            await users_col.update_one({"email": str(email).lower()}, {"$set": {"plan": "free"}})

    return {"received": True}


# -----------------------------------------------------------------------------
# Mount + CORS
# -----------------------------------------------------------------------------
app.include_router(api)

# --- Fabrix Engineer: one model that asks, reasons, and draws -------------
try:
    from engineer.routes import router as _engineer_router
    app.include_router(_engineer_router)
    logging.getLogger(__name__).info("engineer router mounted at /api/engineer")
except Exception as _e:  # never let the new surface take the whole API down
    logging.getLogger(__name__).warning("engineer router disabled: %s", _e)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def _shutdown():
    mongo.close()
