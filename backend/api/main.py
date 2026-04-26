from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from database import configure, init_db

import case_reference_routes
import consultation_routes
from errors import register_exception_handlers


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure()
    init_db()
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
        for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(consultation_routes.router)
    app.include_router(case_reference_routes.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
