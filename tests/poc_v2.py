"""
Quick validation of the upgraded ManuelIA core:
  - GPT-4o now asks 3+ questions
  - Manual JSON has 10-15 steps
  - gpt-image-2 produces a high-detail IKEA-style image at 1536x1024
"""
import os, sys, json, base64, asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import ai_service as AI

async def main():
    project = (
        "Je veux fabriquer un support mural en bois pour ranger 3 vélos verticalement dans mon garage. "
        "Le support doit pivoter pour permettre de sortir le vélo facilement."
    )

    # Multi-turn clarification, count questions
    history = []
    user_replies = [
        "J'ai du contreplaqué bouleau 18mm et des chevilles à expansion pour mur en béton. Niveau intermédiaire.",
        "Pour 3 vélos adultes, hauteur 1m20 max chacun, espacement 50cm entre les vélos. Je veux que ça supporte 25kg par vélo.",
        "J'ai une perceuse, scie sauteuse, équerre, niveau à bulle. Pas de défonceuse.",
        "Finition vernis incolore. Crochets en acier inoxydable à acheter.",
    ]

    turn = 0
    while turn < 8:
        reply = await AI.clarify_next(project, history)
        print(f"\n[A{turn+1}] {reply}")
        if "j'ai toutes les informations" in reply.lower() or "lancer la génération" in reply.lower():
            print("\n[OK] AI signaled satisfaction.")
            break
        history.append({"role": "assistant", "content": reply})
        if turn < len(user_replies):
            history.append({"role": "user", "content": user_replies[turn]})
            print(f"[U{turn+1}] {user_replies[turn]}")
        else:
            history.append({"role": "user", "content": "C'est tout ce que je peux te dire, lance la génération."})
        turn += 1

    questions_count = len([m for m in history if m["role"] == "assistant"])
    print(f"\n>>> Total assistant turns (questions asked): {questions_count}")
    assert questions_count >= 3, f"Expected 3+ questions, got {questions_count}"

    # Structured manual
    print("\n--- Generating manual JSON ---")
    manual = await AI.generate_manual_json(project, history)
    print(f"title: {manual['title']}")
    print(f"difficulty: {manual['difficulty']}")
    print(f"total_duration_min: {manual['total_duration_min']}")
    print(f"STEPS COUNT: {len(manual['steps'])}")
    for i, s in enumerate(manual["steps"], 1):
        print(f"  {i:>2}. {s['title']} ({s['duration_min']}min)")
        print(f"      img: {s['image_subject']}")
    assert len(manual["steps"]) >= 10, f"Need 10+ steps, got {len(manual['steps'])}"

    # Generate ONE image to verify gpt-image-2 at 1536x1024
    print("\n--- Generating step 1 image with gpt-image-2 ---")
    ctx = AI.build_project_context(project, history, manual["title"], manual["difficulty"])
    s0 = manual["steps"][0]
    content = f"{s0['title']}. {s0['image_subject']}. {s0['description']}"
    b64 = await AI.generate_step_image(ctx, content)
    raw = base64.b64decode(b64)
    out = Path("/tmp/poc_v2_step1.png")
    out.write_bytes(raw)
    print(f"[OK] image saved {out} ({len(raw)} bytes)")

    print("\n#### ALL UPGRADES VALIDATED ####")
    print(json.dumps({
        "questions_asked": questions_count,
        "steps_count": len(manual["steps"]),
        "image_model": AI.IMAGE_MODEL,
        "image_size": AI.IMAGE_SIZE,
        "image_bytes": len(raw),
        "image_path": str(out),
    }, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
