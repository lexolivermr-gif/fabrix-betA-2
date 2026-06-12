"""Quick test of the new v3 pipeline: prompt-builder → gpt-image-2 → validator."""
import asyncio, sys, base64, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import ai_service as AI

async def main():
    project = (
        "Convertir un panier d'épicerie en grillage métallique en panier avant de vélo, "
        "fixé sur la fourche avec des supports en L."
    )
    history = [
        {"role": "assistant", "content": "Quel diamètre fait la fourche avant ?"},
        {"role": "user", "content": "1 pouce et quart, fourche aluminium VTC."},
        {"role": "assistant", "content": "Quelle quincaillerie vas-tu utiliser ?"},
        {"role": "user", "content": "Supports L en acier 3mm, boulons M6, écrous nylstop, rondelles."},
        {"role": "assistant", "content": "Niveau d'expérience ?"},
        {"role": "user", "content": "Intermédiaire, j'ai déjà fait du bricolage."},
    ]
    title = "Panier avant de vélo à partir d'un caddy"
    difficulty = "Intermédiaire"
    project_ctx = AI.build_project_context(project, history, title, difficulty)

    print("=" * 60)
    print("Step 1/3: building style anchor (one-shot, reused)")
    print("=" * 60)
    t0 = time.time()
    style_anchor = await AI.build_style_anchor(title, project_ctx)
    print(f"[OK] style_anchor ({time.time()-t0:.1f}s):")
    print(style_anchor)

    current_step = {
        "title": "Marquer les points de perçage sur la fourche",
        "main_object": "bike front fork made of aluminum",
        "main_action": "marking drill points with a pencil",
        "viewpoint": "close-up side view",
        "has_character": True,
        "must_include": ["aluminum fork", "pencil", "ruler", "small dotted marks"],
        "must_exclude": ["actual drilling action", "the basket", "any text labels"],
        "description": "Marquer 4 points sur la fourche, espacés de 5 cm, à l'aide d'un crayon et d'un mètre ruban. Aligner les marques avec le futur support L.",
    }
    prev_step = {"main_action": "preparing tools", "main_object": "workbench with bolts and brackets"}
    next_step = {"main_action": "drilling pilot holes", "main_object": "aluminum bike fork"}

    print("\n" + "=" * 60)
    print("Step 2/3: run full pipeline (prompt → image → validate)")
    print("=" * 60)
    t0 = time.time()
    b64, prompt, meta = await AI.generate_step_image_v2(
        manual_title=title,
        project_context=project_ctx,
        style_anchor=style_anchor,
        current_step=current_step,
        prev_step=prev_step,
        next_step=next_step,
        project_user_id="poc-v3-test",
        on_status=lambda m: print(f"  -> {m}"),
    )
    print(f"\n[OK] pipeline finished ({time.time()-t0:.1f}s)")
    print(f"  attempts: {meta['attempts']}")
    print(f"  validated: {meta['validated']}")
    print(f"  last_reason: {meta['last_reason']}")

    out = Path("/tmp/poc_v3_pipeline.png")
    out.write_bytes(base64.b64decode(b64))
    print(f"  image saved: {out} ({len(b64) // 1024} KB base64)")

    print("\n" + "=" * 60)
    print("Step 3/3: prompt preview")
    print("=" * 60)
    print(prompt[:600] + ("\n... [truncated]" if len(prompt) > 600 else ""))

if __name__ == "__main__":
    asyncio.run(main())
