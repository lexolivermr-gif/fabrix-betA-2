# Fabrix — Restoration PRD

## Original Problem Statement
"I have an existing full-stack app called Fabrix. Here is the complete source code as a zip. Please restore it exactly as-is: Python FastAPI backend + React frontend. Do not modify any logic, just set it up and deploy it."

## Architecture
- **Backend**: FastAPI (Python 3.11) on port 8001, routes mounted under `/api`
- **Frontend**: React 19 + Craco + TailwindCSS + Radix UI on port 3000
- **Database**: MongoDB (local, via `MONGO_URL`)
- **Auth**: JWT (HS256) + bcrypt
- **AI**: Claude Sonnet 4.5 (text/vision) via `emergentintegrations`, OpenAI gpt-image-1/2 (images)
- **Payments**: Stripe (test keys)
- **PDF**: ReportLab

## Backend modules
- `server.py` — main FastAPI app (785 lines, /api routes)
- `auth.py` — JWT auth helpers
- `models.py` — Pydantic models
- `ai_service.py` — Claude + OpenAI image wrappers
- `jobs.py` — Mongo-backed job tracker for manual generation
- `pdf_service.py` — PDF rendering for manuals
- `stripe_service.py` — Stripe checkout + webhook handlers

## What's Been Implemented (restored from zip, 2026-01)
- Full Fabrix source restored from user-provided zip into `/app`
- Backend dependencies installed (added `reportlab==4.2.5`; rest already in base image)
- Frontend dependencies installed via `yarn install`
- `REACT_APP_BACKEND_URL` and `FRONTEND_URL` updated to current preview URL (`https://fabrix-restore.preview.emergentagent.com`)
- All other env vars (OpenAI, Stripe, Emergent LLM key, JWT) preserved exactly as shipped in the zip
- Backend and frontend services running under supervisor (healthy: `/api/` → 200, `/` → 200)
- Login page renders correctly (ManuelIA branded — dark violet theme)

## Env Vars (restored as-is)
- `MONGO_URL`, `DB_NAME` — protected, untouched
- `OPENAI_API_KEY`, `STRIPE_SECRET_KEY`, `EMERGENT_LLM_KEY` — from zip
- `STRIPE_WEBHOOK_SECRET` — empty (per zip, was always pending)
- `JWT_ALGORITHM=HS256`, `JWT_EXPIRE_HOURS=168`

## Known Items From Original Plan (not in scope for restoration)
- Phase 7: Stripe webhook E2E test (still requires `STRIPE_WEBHOOK_SECRET`)
- All Phase 1–6 work was already completed in the zipped codebase

## Next Action Items
- Optional end-to-end functional testing (auth, manual generation, Fix‑It, PDF export, share, Stripe checkout)
- Provide `STRIPE_WEBHOOK_SECRET` to enable webhook E2E test
- Deploy to production
