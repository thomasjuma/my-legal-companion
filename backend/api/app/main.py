from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from database import configure, init_db

from core.errors import register_exception_handlers
from routers import auth_routes, consultation_routes, case_reference_routes, chat_routes

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Repo-root `.env` in local dev; in App Runner / Docker only process env (e.g. DATABASE_URL) applies.
    load_dotenv(
        Path(__file__).resolve().parent.parent.parent / ".env", override=False
    )
    try:
        configure()
        init_db()
    except Exception:
        # Do not block startup: App Runner health checks need GET /health. Fix DB / env if APIs fail.
        _log.exception("DB startup failed — check DATABASE_URL, Aurora SG, and network from App Runner")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Legal Companion API",
        version="0.1.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    # CORS configuration
    # Get origins from CORS_ORIGINS env var (comma-separated) or fall back to localhost
    cors_origins = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:4200"
        ).split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_routes.router)
    app.include_router(consultation_routes.router)
    app.include_router(case_reference_routes.router)
    app.include_router(chat_routes.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)