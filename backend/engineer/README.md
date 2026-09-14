# Fabrix Engineer

One model does the whole job: it asks the clarifying questions, works out the
mechanism, writes the steps, **and draws every blueprint sheet**. The renderer
is deliberately dumb — it draws exactly what the model specified and invents
nothing, which is what makes picture and prose impossible to contradict.

```
brief ──► engineer.ask()     one focused question at a time ──► READY
      └─► engineer.design()  reasoning ➞ build spec (JSON)
                                 │
                                 ├─ validate_spec()   coherence contract
                                 │      ✗ ──► repair loop (errors back to the model)
                                 └─ render ──► SVG sheets + PDF manual
```

## Files

| file | what it does |
|---|---|
| `llm.py` | one `complete()` over Anthropic / OpenAI / Gemini / OpenRouter / any OpenAI-compatible endpoint. No SDKs, `httpx` or stdlib. |
| `prompts.py` | the interrogation rules and the full drawing-language reference the model reads before it draws. |
| `agent.py` | `ask()`, `design()` (with the validate-and-repair loop). |
| `schema.py` | `normalize_spec()`, `validate_spec()` — the coherence contract. |
| `blueprint/theme.py` | the visual contract: white sheet, IKEA blue geometry, red criticals, white characters on navy plates. |
| `blueprint/prims.py` | one primitive list, two backends (SVG + ReportLab). |
| `blueprint/scene.py` | `build_sheet()` — layout, auto-fit, and the `Placer` that makes label collisions impossible. |
| `render.py` | `step_svg()`, `all_svgs()`, `overview_svg()` (parts list). |
| `manual_pdf.py` | `build_pdf(spec) -> bytes`, A4. |
| `proof.py` | ASCII-sheet proofing + `check_sheet()` for automated coherence checks. |
| `cli.py` | `python -m engineer.cli {validate|render|proof} spec.json` |
| `routes.py` | the HTTP surface (also mounted by `server.py` at `/api/engineer`). |
| `serve.py` | standalone preview server — runs with none of the accounts/Stripe/Mongo stack. |
| `examples/toothpick_crossbow.json` | the acceptance build. |

## Run it

```bash
cd backend

# whole pipeline with no model needed — uses the bundled spec
python3 -m engineer.cli validate engineer/examples/toothpick_crossbow.json
python3 -m engineer.cli render   engineer/examples/toothpick_crossbow.json --out ../build

# live API + a minimal UI at http://localhost:8001/preview.html
python3 -m engineer.serve --host 0.0.0.0 --port 8001
```

To let the model do the work, set one of:

```bash
OPENROUTER_API_KEY=...     # one key, 20+ providers, free tiers to test on
ANTHROPIC_API_KEY=...      # strongest reasoning + instruction following
OPENAI_API_KEY=...         # strictest JSON mode
GEMINI_API_KEY=...         # cheapest frontier, 2M context
LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=...   # anything OpenAI-compatible
```

`/api/engineer/health` reports which one is live.

## The coherence contract

`validate_spec()` rejects a spec where the picture could disagree with the
words:

1. every ref in `parts_used` / `context_parts` exists in `materials`
2. **every ref in `parts_used` is drawn on that step's sheet** — if the text
   touches it, the picture shows it
3. anything drawn that isn't in `parts_used` is declared in `context_parts`
4. dimension numbers come from a part's declared size or from `fits`, so a
   number on a sheet cannot drift from the number in the prose
5. no empty drawings

Failures go back to the model as a repair request, so the model fixes its own
drawing instead of the app shipping a contradictory sheet.
