# Fabrix (ex ManuelIA v2) — Updated Development Plan (FastAPI + React + MongoDB)

## 1) Objectives
- Deliver **Fabrix** as a SaaS web app that generates **step-by-step illustrated manuals** in IKEA-style.
- Add a second service **Fix‑It** (photo-based repair guidance) using Claude Vision.
- Enforce **production-grade performance**: a complete manual must generate in **< 15 minutes**.
- Lock model usage:
  - **Text + logic + vision**: **Claude Sonnet 4.5** (`claude-sonnet-4-5`) for *all* reasoning and any image analysis (Fix‑It).
  - **Images**: **OpenAI gpt-image-2** only.
  - Remove the post-generation validator loop; quality relies on prompt generation logic.
  - **Hard requirement**: Log the exact model requested + the model returned for each AI call. If mismatch, emit a visible error log.
- Maintain the app UX/design system (dark violet, faithful to reference HTML) while rebranding to **Fabrix**.

## 2) Implementation Steps

### Phase 0 — Current Status / Completed Work (already done)
**Backend**
- ✅ FastAPI + MongoDB + JWT/bcrypt auth
- ✅ Manuals CRUD + viewer endpoints
- ✅ Public share endpoint: `GET /api/manuals/{id}/public`
- ✅ Stripe checkout endpoints + webhook handler (webhook secret still pending)
- ✅ PDF export endpoint exists
- ✅ Job progress polling endpoint exists
- ✅ gpt-image-2 integrated and verified; image-to-image (reference) verified
- ✅ Regenerate single step and regenerate-all endpoints exist

**Frontend**
- ✅ Full React UI matching reference HTML (sidebar/topbar/dashboard/wizard/viewer/credits/settings/share)
- ✅ Wizard progress UX (spinner + label + progress bar)
- ✅ Viewer includes regen panel + regenerate-all + share + export PDF

**Important note from production issue**
- The earlier 2h generation was caused by:
  1) slow gpt-image-2 high-quality sequential generation + validator retries,
  2) **backend reload** causing in-memory jobs to be lost.
- A Mongo-backed job tracker is required for production reliability.

---

### Phase 1 — Model Switch (STRICT ORDER STEP 1)
**Goal:** replace all GPT‑4o calls with **Claude Sonnet 4.5** and remove the post-gen validation loop.

1. **Remove OpenAI text/vision usage**
   - Replace `chat.completions` usage for:
     - clarification chat
     - steps/manual JSON generation
     - any “prompt builder” chat logic
     - any vision validation logic
   - New provider: **Claude Sonnet 4.5** via `emergentintegrations`.

2. **Model lock + model logging (mandatory)**
   - Implement a single wrapper `call_claude(model="claude-sonnet-4-5", ...)` that:
     - logs requested model
     - logs returned model (if exposed by SDK)
     - logs error prominently if mismatch
   - Implement a similar wrapper for OpenAI image calls:
     - logs `gpt-image-2`
     - errors if any other model is used

3. **Remove validation loop**
   - Delete `validate_image` and the retry loop based on validator.
   - Any retries afterwards will be based on explicit regen actions only.

**Phase 1 acceptance gates**
- All text/vision calls run through Claude Sonnet 4.5.
- No GPT‑4o calls remain.
- Image model remains gpt-image-2.

---

### Phase 2 — Performance Optimizations (STRICT ORDER STEP 2)
**Goal:** manual generation completes in < 15 minutes.

A) **Single Claude call to generate the full manual JSON**
- Replace multi-step prompting with **one Claude call** producing JSON:
  - `title`
  - `diagnostic` (Fix‑It only; optional for manual)
  - `materials` + `tools`
  - `style_anchor` (text style guide)
  - `steps` array (6–8 only) where each step includes:
    - `title`, `description`, `tip`, `duration_min`
    - `image_prompt` (English, optimized for gpt-image-2)
- Enforce **6–8 steps maximum** (hard cap).

B) **Step 1 image first (sequential)**
- Generate image for step 1 alone.
- Store in manual:
  - `style_anchor`
  - `reference_image_b64` (step 1 image)

C) **Steps 2..N in parallel**
- Generate remaining images in parallel using `asyncio.gather`.
- Use a semaphore (configurable) of **3–4** concurrent image calls.
- Each call includes:
  - `style_anchor`
  - **reference image = step 1** (always, never previous)
  - `image_prompt` for that step

D) **Progress reporting in real-time**
- Use a **Mongo-backed job tracker**:
  - job survives backend reloads
  - per-step status: pending / running / done / error
  - global progress: “Image 4 sur 7 générée”
- Frontend wizard generation screen polls and displays:
  - overall progress
  - current image index / total

E) **Eliminate slow/expensive loops**
- No vision validation + no validator retries.
- Retry only via explicit user regen actions.

**Phase 2 acceptance gates**
- Manual generation under typical conditions completes in < 15 minutes for 6–8 steps.
- Jobs continue correctly even if backend reloads.

---

### Phase 3 — New Service: Fix‑It (STRICT ORDER STEP 3)
**Goal:** add second tab/flow that starts from a user photo.

1. **Backend**
- New endpoints:
  - `POST /api/fixit/analyze-and-generate`
    - accepts image upload (jpg/png/webp) up to 10MB + optional text
    - calls Claude Sonnet 4.5 Vision
    - returns same manual JSON schema as manual generation
  - `POST /api/fixit/generate-images` (or reuse the same `/manuals/generate` job path)
- Important constraint:
  - user photo goes ONLY to Claude for analysis
  - never sent to gpt-image-2

2. **Frontend**
- Add a second tab “Fix‑It” alongside Manual
- UI:
  - mandatory upload + optional description
  - if photo unusable → clear error message, no generation
  - output goes to the same viewer page (same PDF/share)

---

### Phase 4 — Refined Regeneration (STRICT ORDER STEP 4)
**Goal:** regeneration uses the stored anchors.

- Single-step regen uses:
  - `style_anchor`
  - `reference_image_b64` (step 1)
  - original step `image_prompt`
  - user `custom_instructions`
- Regenerate-all uses:
  - step 1 regenerated first (updates reference)
  - steps 2..N regenerated in parallel with same semaphore limit
- Add progress indicator for regen-all (per-step grid)

---

### Phase 5 — Multilingual (STRICT ORDER STEP 5)
**Goal:** full i18n for UI + Claude content generation language.

- Languages: **FR, EN, ES, DE, PT, IT**
- Browser auto-detect + manual selector in header
- No hard-coded UI strings: all in i18n JSON files
- Claude generates manual content in active language
- Image prompts remain English internally
- PDF uses the manual language

---

### Phase 6 — Sharing + PDF Gate + Rebrand to Fabrix (STRICT ORDER STEP 6)
1. **Public share**
- Keep `/share/{id}` read-only, no auth

2. **PDF export paywall gate**
- Add `pdf_unlocked: bool` per manual
- Export PDF button checks flag first
- Pricing logic to be added later; for now:
  - if locked → show upgrade/payment message
  - if unlocked → allow export

3. **Rebrand**
- Replace all user-facing “ManuelIA” with **Fabrix**:
  - sidebar logo, titles, settings, footer, metadata

---

### Phase 7 — Stripe Webhook End-to-End Test (STRICT ORDER STEP 7)
**Goal:** confirm payment test → webhook received → credits added.

1. Request `STRIPE_WEBHOOK_SECRET` from user
2. Configure webhook signature verification
3. Run end-to-end test:
   - complete test checkout
   - webhook triggers
   - credits/plan updated in Mongo
4. Confirm explicitly in final report.

---

## 3) Next Actions
1. **Implement Phase 1**: switch GPT‑4o → Claude Sonnet 4.5 everywhere + remove validator loop + enforce model logging.
2. **Implement Phase 2**: performance overhaul:
   - single Claude JSON generation
   - step 1 image first
   - parallel images 2..N
   - Mongo job tracker with per-step grid progress
3. After performance is stable: implement Fix‑It, then regen refinements, then i18n.
4. Implement PDF gate + Fabrix rebrand.
5. Request webhook secret and run Stripe webhook E2E.

## 4) Success Criteria
- **Models**:
  - All text/vision uses Claude Sonnet 4.5 only.
  - All image generation uses gpt-image-2 only.
  - Model usage is logged and mismatches trigger visible errors.
- **Performance**:
  - Manual generation for 6–8 steps completes in < 15 minutes.
  - Steps 2..N are generated in parallel with concurrency 3–4.
- **Fix‑It**:
  - Photo required; unusable photo leads to a clear retry message.
  - Output format identical to Manual (viewer/share/PDF).
- **UX**:
  - Real-time progress displayed ("Image X / N") and per-step status grid.
- **Monetization**:
  - PDF export gated by `pdf_unlocked`.
  - Stripe webhook tested end-to-end once secret provided.
- **Brand**:
  - UI shows “Fabrix” everywhere.
