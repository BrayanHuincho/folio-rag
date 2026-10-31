from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from folio import __version__
from folio.config import REPO_ROOT, get_settings
from folio.db import init_db
from folio.ingest import set_image_describer
from folio.ingest.pipeline import get_index_manager
from folio.llm.vision import describe_image

from . import chat, collections, conversations, documents, fs, models

WEB_DIST = REPO_ROOT / "web" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if get_settings().ocr:
        set_image_describer(describe_image)
    manager = get_index_manager()
    manager.start()
    try:
        yield
    finally:
        manager.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="Folio", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")

    @api.get("/health")
    def health() -> dict:
        settings = get_settings()
        return {
            "ok": True,
            "version": __version__,
            "llm": settings.llm,
            "embeddings": settings.embeddings,
        }

    for module in (collections, documents, conversations, chat, models, fs):
        api.include_router(module.router)
    app.include_router(api)

    if WEB_DIST.is_dir():
        _mount_spa(app)
    return app


def _mount_spa(app: FastAPI) -> None:
    root = WEB_DIST.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)
