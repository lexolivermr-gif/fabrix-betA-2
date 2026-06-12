"""POC of the 3-layer consistency pipeline: text anchor + image anchor + validation."""
import asyncio, sys, base64, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import ai_service as AI


async def main():
    project = (
        "Construire un porte-vélo mural pivotant en bois de bouleau 18mm pour 3 vélos adultes "
        "dans un garage, fixé au mur béton avec chevilles à expansion."
    )
    history = [
        {"role": "assistant", "content": "Quel type de bois ?"},
        {"role": "user", "content": "Contreplaqué bouleau 18mm, finition vernis incolore."},
        {"role": "assistant", "content": "Quels outils as-tu ?"},
        {"role": "user", "content": "Perceuse, scie sauteuse, équerre, niveau à bulle."},
        {"role": "assistant", "content": "Niveau d'expérience ?"},
        {"role": "user", "content": "Intermédiaire."},
    ]
    title = "Porte-vélo mural pivotant 3 vélos"
    difficulty = "Intermédiaire"
    project_ctx = AI.build_project_context(project, history, title, difficulty)

    print("Building style anchor (layer 1)...")
    t0 = time.time()
    style_anchor = await AI.build_style_anchor(title, project_ctx)
    print(f"[OK] style_anchor in {time.time() - t0:.1f}s")

    # Step 1 — NO reference image (text-to-image)
    step1 = {
        "title": "Découper les panneaux de bouleau",
        "main_object": "birch plywood sheet on a workbench",
        "main_action": "cutting plywood with a jigsaw along a marked line",
        "viewpoint": "top-down view",
        "has_character": True,
        "must_include": ["jigsaw tool", "marked cutting line", "two hands holding the saw"],
        "must_exclude": ["other tools", "wall background"],
        "description": "Découper le panneau à 80x50cm avec la scie sauteuse.",
    }
    print("\n[Step 1] generating WITHOUT reference image (text-to-image)...")
    t0 = time.time()
    s1_b64, s1_prompt, s1_meta = await AI.generate_step_image_v2(
        manual_title=title,
        project_context=project_ctx,
        style_anchor=style_anchor,
        current_step=step1,
        prev_step=None,
        next_step={"main_action": "sanding edges", "main_object": "plywood board"},
        project_user_id="poc-3layer",
        reference_image_b64=None,
        on_status=lambda m: print(f"  - {m}"),
    )
    Path("/tmp/poc_3layer_step1.png").write_bytes(base64.b64decode(s1_b64))
    print(f"[OK] step 1 ({time.time() - t0:.1f}s) attempts={s1_meta['attempts']} validated={s1_meta['validated']}")
    print(f"     reason: {s1_meta['last_reason']}")

    # Step 2 — WITH step 1 as reference image (img2img)
    step2 = {
        "title": "Percer les trous de fixation dans le mur",
        "main_object": "concrete wall with marked drill points",
        "main_action": "drilling pilot holes into concrete with a hammer drill",
        "viewpoint": "isometric 3/4 view",
        "has_character": True,
        "must_include": ["power drill with masonry bit", "two stick figure hands gripping the drill", "marked points on wall"],
        "must_exclude": ["plywood", "jigsaw", "any text labels"],
        "description": "Percer 6 trous de 8mm dans le mur béton avec une mèche à béton.",
    }
    print("\n[Step 2] generating WITH step1 as reference image (img2img)...")
    t0 = time.time()
    s2_b64, s2_prompt, s2_meta = await AI.generate_step_image_v2(
        manual_title=title,
        project_context=project_ctx,
        style_anchor=style_anchor,
        current_step=step2,
        prev_step=step1,
        next_step={"main_action": "installing expansion anchors", "main_object": "concrete wall"},
        project_user_id="poc-3layer",
        reference_image_b64=s1_b64,   # <-- LAYER 2 IN ACTION
        on_status=lambda m: print(f"  - {m}"),
    )
    Path("/tmp/poc_3layer_step2.png").write_bytes(base64.b64decode(s2_b64))
    print(f"[OK] step 2 ({time.time() - t0:.1f}s) attempts={s2_meta['attempts']} validated={s2_meta['validated']} used_ref={s2_meta['used_reference']}")
    print(f"     reason: {s2_meta['last_reason']}")

    print("\n#### 3-LAYER PIPELINE VALIDATED ####")
    print("Files saved:")
    print("  /tmp/poc_3layer_step1.png (no reference, plain text-to-image)")
    print("  /tmp/poc_3layer_step2.png (uses step 1 as visual anchor)")


if __name__ == "__main__":
    asyncio.run(main())
