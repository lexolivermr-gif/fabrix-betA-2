"""
Standalone preview server for the Engineer.

The main app (`server.py`) also mounts these routes; this file exists so the
engine can be run and demoed on its own, without the accounts/Stripe/Mongo
stack that the rest of Fabrix needs:

    cd backend && python3 -m engineer.serve --host 0.0.0.0 --port 8001

Then open /preview.html for a minimal UI, or talk to the API directly:

    GET  /api/engineer/health     which model provider is configured
    GET  /api/engineer/example    the bundled toothpick-crossbow spec
    POST /api/engineer/ask        next clarifying question
    POST /api/engineer/design     full validated spec
    POST /api/engineer/validate   {spec} -> {errors, warnings}
    POST /api/engineer/sheets     {spec} -> nomenclature + one SVG per step
    POST /api/engineer/pdf        {spec} -> the finished manual
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware


def build_app() -> FastAPI:
    from .routes import router

    app = FastAPI(
        title="Fabrix Engineer",
        description="One model interrogates, reasons out the mechanism, and "
                    "draws every sheet of the build guide.",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
        allow_headers=["*"], allow_credentials=False,
    )
    app.include_router(router)

    here = Path(__file__).parent

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(here / "preview.html")

    @app.get("/preview.html", include_in_schema=False)
    def preview():
        return FileResponse(here / "preview.html")

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Fabrix Engineer preview server")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--reload", action="store_true")
    args = ap.parse_args()

    import uvicorn
    uvicorn.run("engineer.serve:build_app", factory=True, host=args.host,
                port=args.port, reload=args.reload)


app = None  # built by factory; kept importable for `uvicorn engineer.serve:build_app`

if __name__ == "__main__":
    main()
