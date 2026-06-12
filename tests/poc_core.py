"""
POC for ManuelIA v2 core:
  1. GPT-4o conversational clarification chat
  2. GPT-4o structured JSON output for manual steps
  3. DALL-E 3 image generation with IKEA-style prompt + custom_instructions
  4. Verify shared context (project + chat history) is passed to BOTH text + image calls
  5. Verify DALL-E URL is downloadable and saveable as base64

Run: cd /app && python tests/poc_core.py
"""
import os
import sys
import json
import base64
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load backend .env
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

import httpx
from openai import AsyncOpenAI

API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    print("[FATAL] OPENAI_API_KEY not set in /app/backend/.env"); sys.exit(1)

client = AsyncOpenAI(api_key=API_KEY)

IKEA_IMAGE_PROMPT_TEMPLATE = """Generate a technical illustration in IKEA assembly manual style.

Project context: {PROJECT_CONTEXT}
Step to illustrate: {STEP_CONTENT}

Visual rules (strict):
- White background (#FFFFFF), no gradients, no shadows, no textures
- All lines and shapes in IKEA blue (#1a1a6e), stroke weight 2.5-3.5px
- Important elements (arrows, highlights, warnings) in IKEA red (#cc0000)
- Pictogram style — clean, minimal, geometric
- NO text, NO labels, NO numbers inside the image
- NO photorealism, NO shading, NO perspective distortion
- Objects must match exactly what is described in the step text
- If "grocery basket" is mentioned, draw a wire mesh supermarket cart basket, NOT a bicycle basket
- Step number in red bottom-center, bold
- Consistent style with all other steps of this manual"""


# -----------------------------------------------------------------------------
# POC 1: GPT-4o clarification chat (multi-turn)
# -----------------------------------------------------------------------------
async def poc_clarification_chat(project: str) -> list[dict]:
    print("\n" + "=" * 80)
    print("POC 1: GPT-4o Clarification chat")
    print("=" * 80)

    system = (
        "Tu es un expert technique qui aide un utilisateur à préparer un manuel d'assemblage "
        "illustré dans le style des notices IKEA. Pose 1 à 2 questions PERTINENTES pour clarifier "
        "le projet (matériaux, dimensions, contraintes, niveau d'expérience). "
        "RÉPONDS EN FRANÇAIS. Reste très concis (max 3 phrases). Ne propose pas d'étapes ici."
    )

    history = [
        {"role": "system", "content": system},
        {"role": "user", "content": project},
    ]

    # Turn 1
    r1 = await client.chat.completions.create(
        model="gpt-4o",
        messages=history,
        temperature=0.7,
        max_tokens=200,
    )
    q1 = r1.choices[0].message.content
    print(f"\n[Assistant Q1] {q1}")
    history.append({"role": "assistant", "content": q1})

    # User answer
    user_answer = (
        "Le panier est en grillage métallique soudé, dimensions standards supermarché. "
        "Le vélo est un VTC avec fourche rigide en aluminium. Je vise une fixation solide "
        "mais réversible. J'ai un niveau intermédiaire, j'ai déjà fait du bricolage."
    )
    history.append({"role": "user", "content": user_answer})
    print(f"\n[User] {user_answer}")

    # Turn 2 — confirmer/clarifier
    r2 = await client.chat.completions.create(
        model="gpt-4o",
        messages=history,
        temperature=0.7,
        max_tokens=200,
    )
    q2 = r2.choices[0].message.content
    history.append({"role": "assistant", "content": q2})
    print(f"\n[Assistant Q2] {q2}")

    print("\n[OK] Clarification chat reached 2 assistant turns successfully.")
    return history


# -----------------------------------------------------------------------------
# POC 2: GPT-4o structured JSON output (manual steps)
# -----------------------------------------------------------------------------
async def poc_steps_json(project: str, chat_history: list[dict]) -> dict:
    print("\n" + "=" * 80)
    print("POC 2: GPT-4o Structured manual steps")
    print("=" * 80)

    # Build context string from full chat (shared context)
    chat_transcript = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in chat_history if m["role"] != "system"
    )

    system = (
        "Tu es un rédacteur expert de manuels d'assemblage style IKEA. "
        "Tu produis UN SEUL objet JSON conforme au schéma. RÉPONDS EN FRANÇAIS. "
        "Champs requis:\n"
        "  title (string): titre court du manuel\n"
        "  difficulty (string): 'Débutant' | 'Intermédiaire' | 'Avancé' (déduis automatiquement)\n"
        "  total_duration_min (int): durée totale estimée en minutes\n"
        "  steps (array, 3 à 8 éléments) avec pour chaque étape:\n"
        "    - title (string court)\n"
        "    - description (string, 2-4 phrases, instructions claires et actionnables)\n"
        "    - tip (string, conseil pratique court)\n"
        "    - duration_min (int)\n"
        "    - image_subject (string court 8-15 mots décrivant exactement les OBJETS et l'ACTION "
        "visible dans l'image, ex: \"hand using wrench to tighten a bolt on metal bracket\")\n"
        "Ne retourne RIEN d'autre que le JSON."
    )

    user = (
        f"PROJET INITIAL:\n{project}\n\n"
        f"TRANSCRIPT DE CLARIFICATION:\n{chat_transcript}\n\n"
        "Produis le JSON du manuel maintenant."
    )

    resp = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content
    print(f"\n[Raw JSON length] {len(raw)} chars")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[FAIL] JSON parse error: {e}")
        print(raw[:500])
        raise

    # Validate required fields
    required_top = ["title", "difficulty", "total_duration_min", "steps"]
    for k in required_top:
        assert k in data, f"missing top-level field: {k}"

    assert isinstance(data["steps"], list), "steps must be array"
    assert 3 <= len(data["steps"]) <= 8, f"steps count out of range: {len(data['steps'])}"

    required_step = ["title", "description", "tip", "duration_min", "image_subject"]
    for i, s in enumerate(data["steps"]):
        for k in required_step:
            assert k in s, f"step {i} missing {k}"

    print(f"[OK] Manual generated:")
    print(f"   title: {data['title']}")
    print(f"   difficulty: {data['difficulty']}")
    print(f"   total_duration: {data['total_duration_min']} min")
    print(f"   steps: {len(data['steps'])}")
    for i, s in enumerate(data["steps"], 1):
        print(f"   {i}. {s['title']} ({s['duration_min']}min)")
        print(f"      image_subject: {s['image_subject']}")

    return data


# -----------------------------------------------------------------------------
# POC 3: DALL-E 3 image generation with IKEA prompt + custom_instructions
# -----------------------------------------------------------------------------
async def poc_dalle3_image(
    project_context: str,
    step_content: str,
    custom_instructions: str | None = None,
) -> dict:
    print("\n" + "-" * 80)
    print(f"POC 3: DALL-E 3 image — step: {step_content[:60]}")
    print("-" * 80)

    prompt = IKEA_IMAGE_PROMPT_TEMPLATE.format(
        PROJECT_CONTEXT=project_context,
        STEP_CONTENT=step_content,
    )
    if custom_instructions:
        prompt += f"\n\nAdditional instructions: {custom_instructions}"

    print(f"[Prompt length] {len(prompt)} chars (DALL-E 3 max ~4000)")

    resp = await client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        quality="high",
        n=1,
    )
    item = resp.data[0]
    img_url = getattr(item, "url", None)
    b64_inline = getattr(item, "b64_json", None)
    revised = getattr(item, "revised_prompt", None)
    if revised:
        print(f"[revised_prompt] {revised[:120]}...")

    if img_url:
        print(f"[OK] DALL-E 3 returned URL ({len(img_url)} chars)")
        async with httpx.AsyncClient(timeout=60.0) as h:
            r = await h.get(img_url)
            r.raise_for_status()
            img_bytes = r.content
        print(f"[OK] Downloaded {len(img_bytes)} bytes from URL")
    elif b64_inline:
        print(f"[OK] DALL-E 3 returned b64_json inline ({len(b64_inline)} chars)")
        img_bytes = base64.b64decode(b64_inline)
        print(f"[OK] Decoded {len(img_bytes)} bytes from b64_json")
    else:
        raise RuntimeError("DALL-E response had neither 'url' nor 'b64_json'")

    b64 = base64.b64encode(img_bytes).decode("ascii")
    print(f"[OK] Base64 encoded ({len(b64)} chars) — ready for MongoDB persistence")

    # Save to disk for visual inspection
    out_dir = Path("/tmp/poc_images")
    out_dir.mkdir(exist_ok=True)
    fname = out_dir / f"step_{abs(hash(step_content)) % 10**8}.png"
    fname.write_bytes(img_bytes)
    print(f"[OK] Saved local copy → {fname}")

    return {"url": img_url, "bytes": len(img_bytes), "base64_len": len(b64), "path": str(fname)}


# -----------------------------------------------------------------------------
# POC 4: Full chain — context shared between text + images
# -----------------------------------------------------------------------------
async def main():
    print("\n" + "#" * 80)
    print("# ManuelIA v2 — Core workflow POC")
    print("#" * 80)

    project = (
        "Je veux convertir un panier d'épicerie standard en grillage métallique en panier avant "
        "de vélo cargo, fixé solidement sur la fourche avant. Donne-moi les étapes pour la "
        "découpe, la fabrication des supports et la fixation, en utilisant des outils courants."
    )

    # Step 1 — chat
    chat = await poc_clarification_chat(project)

    # Step 2 — structured manual
    manual = await poc_steps_json(project, chat)

    # Build a single project_context string shared with images
    chat_text = " | ".join(m["content"] for m in chat if m["role"] != "system")
    project_context = (
        f"Project: {manual['title']}. Difficulty {manual['difficulty']}. "
        f"User request and clarifications: {chat_text[:600]}"
    )

    # Step 3 — generate image for FIRST step only (saves cost during POC)
    step0 = manual["steps"][0]
    step_content = f"{step0['title']}. {step0['image_subject']}. {step0['description']}"
    img1 = await poc_dalle3_image(project_context, step_content)

    # Step 4 — same step but with custom_instructions (regeneration test)
    print("\n" + "-" * 80)
    print("POC 3 bis: regenerate same step with custom_instructions='top-down view, zoom on hands'")
    print("-" * 80)
    img2 = await poc_dalle3_image(
        project_context,
        step_content,
        custom_instructions="top-down view, zoom on hands holding the basket",
    )

    print("\n" + "#" * 80)
    print("# ALL POC GATES PASSED")
    print("#" * 80)
    print(json.dumps({
        "chat_turns": len([m for m in chat if m["role"] != "system"]),
        "manual_title": manual["title"],
        "manual_steps": len(manual["steps"]),
        "manual_difficulty": manual["difficulty"],
        "img1_bytes": img1["bytes"],
        "img2_bytes": img2["bytes"],
        "img1_path": img1["path"],
        "img2_path": img2["path"],
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
