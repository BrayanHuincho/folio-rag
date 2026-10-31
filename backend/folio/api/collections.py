from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from folio.config import get_settings
from folio.db import connect
from folio.ingest.pipeline import get_index_manager

router = APIRouter(prefix="/collections", tags=["collections"])

COLLECTION_SQL = """
SELECT c.*,
       (SELECT COUNT(*) FROM documents d WHERE d.collection_id = c.id) AS doc_count,
       (SELECT COALESCE(SUM(d.chunk_count), 0) FROM documents d WHERE d.collection_id = c.id)
           AS chunk_count,
       (SELECT COALESCE(SUM(d.size), 0) FROM documents d WHERE d.collection_id = c.id)
           AS size_bytes
FROM collections c
"""


class CollectionIn(BaseModel):
    name: str
    path: str


def _serialize(row) -> dict:
    progress = get_index_manager().progress(row["id"])
    return {
        "id": row["id"],
        "name": row["name"],
        "path": row["path"],
        "status": row["status"],
        "error": row["error"],
        "doc_count": row["doc_count"],
        "chunk_count": row["chunk_count"],
        "size_bytes": row["size_bytes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "progress": {k: progress.get(k) for k in ("state", "done", "total", "current")},
        "managed": Path(row["path"]).resolve().is_relative_to(uploads_dir().resolve()),
    }


def uploads_dir() -> Path:
    return get_settings().data_dir / "uploads"


def get_collection(collection_id: str) -> dict:
    row = connect().execute(COLLECTION_SQL + " WHERE c.id = ?", (collection_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Colección no encontrada")
    return _serialize(row)


def _safe_relative(filename: str) -> Path | None:
    # el navegador manda la ruta relativa al subir carpetas; no dejamos salir del destino
    parts = [p for p in PurePosixPath(filename.replace("\\", "/")).parts if p not in ("", ".", "..", "/")]
    return Path(*parts) if parts else None


async def _save_files(target: Path, files: list[UploadFile]) -> list[str]:
    limit = get_settings().max_file_mb * 1024 * 1024
    saved: list[str] = []
    for upload in files:
        relative = _safe_relative(upload.filename or "")
        if relative is None:
            continue
        dest = (target / relative).resolve()
        if not dest.is_relative_to(target.resolve()):
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with dest.open("wb") as out:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > limit:
                    break
                out.write(chunk)
        if written > limit:
            dest.unlink(missing_ok=True)
            continue
        saved.append(relative.as_posix())
    return saved


def _guess_name(files: list[UploadFile]) -> str:
    first = PurePosixPath((files[0].filename or "").replace("\\", "/"))
    if len(first.parts) > 1:
        return first.parts[0]
    return first.stem if len(files) == 1 else "Mis documentos"


@router.get("")
def list_collections() -> list[dict]:
    rows = connect().execute(COLLECTION_SQL + " ORDER BY c.created_at").fetchall()
    return [_serialize(row) for row in rows]


@router.post("")
def create_collection(body: CollectionIn) -> dict:
    path = Path(body.path).expanduser()
    if not path.is_dir():
        raise HTTPException(422, f"No es una carpeta: {body.path}")
    name = body.name.strip() or path.name
    created = get_index_manager().add_collection(name, str(path.resolve()))
    return get_collection(created["id"])


@router.post("/upload")
async def create_from_upload(name: str = Form(""), files: list[UploadFile] = File(...)) -> dict:
    target = uploads_dir() / uuid.uuid4().hex[:12]
    target.mkdir(parents=True)
    await _save_files(target, files)
    label = name.strip() or _guess_name(files)
    created = get_index_manager().add_collection(label, str(target))
    return get_collection(created["id"])


@router.post("/{collection_id}/files")
async def add_files(collection_id: str, files: list[UploadFile] = File(...)) -> dict:
    collection = get_collection(collection_id)
    paths = await _save_files(Path(collection["path"]), files)
    get_index_manager().reindex(collection_id)
    return {"saved": len(paths), "paths": paths}


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: str) -> Response:
    collection = get_collection(collection_id)
    get_index_manager().remove_collection(collection_id)
    if collection["managed"]:
        shutil.rmtree(collection["path"], ignore_errors=True)
    return Response(status_code=204)


@router.post("/{collection_id}/reindex", status_code=202)
def reindex(collection_id: str, full: bool = False) -> dict:
    get_collection(collection_id)
    get_index_manager().reindex(collection_id, full=full)
    return {"ok": True}


@router.get("/{collection_id}/events")
async def collection_events(collection_id: str, request: Request) -> EventSourceResponse:
    get_collection(collection_id)
    manager = get_index_manager()
    queue = manager.subscribe(collection_id)

    async def events():
        try:
            yield {"event": "progress", "data": json.dumps(manager.progress(collection_id))}
            while not await request.is_disconnected():
                try:
                    update = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    continue
                yield {"event": "progress", "data": json.dumps(update)}
        finally:
            manager.unsubscribe(collection_id, queue)

    return EventSourceResponse(events(), ping=15)
