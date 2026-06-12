"""POC : Claude Sonnet 4.5 single-call manual + parallel gpt-image-2 pipeline."""
import asyncio, sys, base64, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import ai_service as AI


async def main():
    project = (
        "Construire un porte-vélo mural pivotant en bouleau 18mm pour 3 vélos adultes dans un garage, "
        "fixé au mur béton avec chevilles à expansion."
    )
    history = [
        {"role": "assistant", "content": "Quel bois ?"},
        {"role": "user", "content": "Contreplaqué bouleau 18mm, vernis incolore."},
        {"role": "assistant", "content": "Outils dispo ?"},
        {"role": "user", "content": "Perceuse, scie sauteuse, équerre, niveau."},
        {"role": "assistant", "content": "Niveau ?"},
        {"role": "user", "content": "Intermédiaire."},
    ]

    print("=" * 60)
    print("[1/3] ONE Claude Sonnet 4.5 call -> full manual JSON")
    print("=" * 60)
    t0 = time.time()
    manual = await AI.generate_manual_json(project, history, lang="fr")
    print(f"[OK] Claude in {time.time()-t0:.1f}s")
    print(f"  title: {manual['title']}")
    print(f"  difficulty: {manual['difficulty']}")
    print(f"  steps count: {len(manual['steps'])}")
    print(f"  materials: {manual.get('materials')}")
    print(f"  tools: {manual.get('tools')}")
    print(f"  style_anchor: {manual['style_anchor'][:120]}...")
    for i, s in enumerate(manual["steps"], 1):
        print(f"    {i}. {s['title']} ({s['duration_min']}min)")
        print(f"       img: {s['image_prompt'][:120]}...")

    print("\n" + "=" * 60)
    print("[2/3] Parallel gpt-image-2 pipeline")
    print("=" * 60)

    state_log = []
    async def _on_step(idx, state, extra):
        state_log.append((time.time(), idx, state))
        print(f"  [+{time.time()-t0:.0f}s] step {idx+1}: {state}")

    t0 = time.time()
    step_imgs, cover_b64 = await AI.generate_all_step_images(
        manual,
        on_step_state=_on_step,
        concurrency=3,
        project_user_id="poc-fabrix",
    )
    print(f"[OK] Total parallel image gen: {time.time()-t0:.1f}s")
    print(f"  step images: {len(step_imgs)} -- cover: {bool(cover_b64)}")

    # Save first 2 images for inspection
    Path("/tmp/poc_fabrix_step1.png").write_bytes(base64.b64decode(step_imgs[0]))
    Path("/tmp/poc_fabrix_step2.png").write_bytes(base64.b64decode(step_imgs[1]))
    Path("/tmp/poc_fabrix_cover.png").write_bytes(base64.b64decode(cover_b64))
    print("  saved: /tmp/poc_fabrix_step1.png, step2.png, cover.png")

    print("\n#### CLAUDE + PARALLEL PIPELINE OK ####")

if __name__ == "__main__":
    asyncio.run(main())
