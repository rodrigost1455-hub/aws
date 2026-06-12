from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers import clients as clients_router
from .routers import reports as reports_router


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="AW Client Report Portal", version="1.0")

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        # optional one-shot seed when AW_DEV_SEED=1
        if os.environ.get("AW_DEV_SEED") == "1":
            from scripts.seed import seed_if_empty  # type: ignore
            seed_if_empty()

    # /api routes FIRST so the static catch-all can't shadow them.
    app.include_router(clients_router.router)
    app.include_router(reports_router.client_router)
    app.include_router(reports_router.report_router)

    @app.post("/api/dev/seed", tags=["dev"])
    def dev_seed():
        if os.environ.get("AW_ALLOW_DEV_SEED") != "1":
            raise HTTPException(403, "dev seed disabled")
        from scripts.seed import seed_demo  # type: ignore
        n = seed_demo()
        return {"seeded": n}

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/", include_in_schema=False)
        def root():
            return FileResponse(STATIC_DIR / "index.html")

        @app.get("/{path:path}", include_in_schema=False)
        def static_passthrough(path: str):
            # serve top-level requests for client.html / styles.css / etc.
            if path.startswith("api/"):
                raise HTTPException(404)
            f = STATIC_DIR / path
            if f.is_file():
                return FileResponse(f)
            raise HTTPException(404)

    return app


app = create_app()
