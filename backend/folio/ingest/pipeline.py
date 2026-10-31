import asyncio
import fnmatch
import hashlib
import logging
import mimetypes
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from folio.config import get_settings
from folio.db import connect, init_db
from folio.embed import get_embedder
from folio.index import store
from folio.ingest.chunker import Chunk, chunk
from folio.ingest.parsers import ParseError, UnsupportedFile, parse, supported
from folio.ingest.watcher import FolderWatcher

log = logging.getLogger(__name__)

IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".idea", ".vscode"}
EMBED_BATCH = 64


def load_ignore(root: Path) -> list[str]:
    file = root / ".folioignore"
    if not file.is_file():
        return []
    lines = file.read_text(encoding="utf-8", errors="replace").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def is_ignored(rel_path: str, patterns: list[str], is_dir: bool = False) -> bool:
    parts = rel_path.split("/")
    for pattern in patterns:
        dir_only = pattern.endswith("/")
        pattern = pattern.strip("/")
        if dir_only and not is_dir and "/" not in rel_path:
            continue
        if "/" in pattern:
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, pattern + "/*"):
                return True
            continue
        candidates = parts if not dir_only else (parts if is_dir else parts[:-1])
        if any(fnmatch.fnmatch(part, pattern) for part in candidates):
            return True
    return False


def scan(root: Path) -> list[Path]:
    patterns = load_ignore(root)
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        base = Path(current)
        rel_base = base.relative_to(root).as_posix()
        rel_base = "" if rel_base == "." else rel_base + "/"
        dirs[:] = [
            d for d in dirs
            if d not in IGNORED_DIRS and not d.startswith(".") and not is_ignored(rel_base + d, patterns, True)
        ]
        for name in names:
            if name.startswith(".") and name != ".env":
                continue
            path = base / name
            if supported(path) and not is_ignored(rel_base + name, patterns):
                files.append(path)
    return sorted(files)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def embedding_text(item: Chunk, rel_path: str) -> str:
    context = rel_path if not item.heading else f"{rel_path} > {item.heading}"
    return f"{context}\n{item.text}"


@dataclass
class Progress:
    state: str = "idle"
    done: int = 0
    total: int = 0
    current: str | None = None
    errors: int = 0

    def as_dict(self) -> dict:
        return {"state": self.state, "done": self.done, "total": self.total,
                "current": self.current, "errors": self.errors}


@dataclass
class _Job:
    lock: threading.Lock = field(default_factory=threading.Lock)
    pending: bool = False
    full: bool = False
    cancelled: bool = False


class IndexManager:
    def __init__(self, workers: int = 2):
        self._jobs = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="folio-index")
        self._parsers = ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) // 2),
                                           thread_name_prefix="folio-parse")
        self._state: dict[str, _Job] = {}
        self._progress: dict[str, Progress] = {}
        self._subscribers: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}
        self._watchers: dict[str, FolderWatcher] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        init_db()
        conn = connect()
        rows = conn.execute("SELECT id, path FROM collections").fetchall()
        for row in rows:
            self._watch(row["id"], Path(row["path"]))
            self.reindex(row["id"])

    def stop(self) -> None:
        with self._lock:
            watchers = list(self._watchers.values())
            self._watchers.clear()
            for job in self._state.values():
                job.cancelled = True
        for watcher in watchers:
            watcher.stop()
        self._jobs.shutdown(wait=False, cancel_futures=True)
        self._parsers.shutdown(wait=False, cancel_futures=True)

    def add_collection(self, name: str, path: str | Path) -> dict:
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"{root} is not a directory")
        init_db()
        now = time.time()
        collection = {
            "id": uuid.uuid4().hex, "name": name.strip() or root.name, "path": str(root),
            "embeddings": get_settings().embeddings, "status": "idle", "error": None,
            "created_at": now, "updated_at": now,
        }
        conn = connect()
        with conn:
            conn.execute(
                "INSERT INTO collections (id, name, path, embeddings, status, error, created_at, updated_at)"
                " VALUES (:id, :name, :path, :embeddings, :status, :error, :created_at, :updated_at)",
                collection,
            )
        self._watch(collection["id"], root)
        self.reindex(collection["id"])
        return collection

    def remove_collection(self, collection_id: str) -> None:
        with self._lock:
            watcher = self._watchers.pop(collection_id, None)
            job = self._state.pop(collection_id, None)
            self._progress.pop(collection_id, None)
        if watcher:
            watcher.stop()
        if job:
            job.cancelled = True
        conn = connect()
        with conn:
            conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        store.invalidate(collection_id)

    def reindex(self, collection_id: str, full: bool = False) -> None:
        job = self._job(collection_id)
        with self._lock:
            job.full = job.full or full
            if job.pending:
                return
            job.pending = True
        self._jobs.submit(self._run, collection_id)

    def progress(self, collection_id: str) -> dict:
        with self._lock:
            progress = self._progress.get(collection_id) or Progress()
            return progress.as_dict()

    def subscribe(self, collection_id: str) -> asyncio.Queue:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        with self._lock:
            self._subscribers.setdefault(collection_id, []).append((loop, queue))
        queue.put_nowait(self.progress(collection_id))
        return queue

    def unsubscribe(self, collection_id: str, queue: asyncio.Queue) -> None:
        with self._lock:
            subscribers = self._subscribers.get(collection_id, [])
            self._subscribers[collection_id] = [item for item in subscribers if item[1] is not queue]

    def _job(self, collection_id: str) -> _Job:
        with self._lock:
            return self._state.setdefault(collection_id, _Job())

    def _watch(self, collection_id: str, root: Path) -> None:
        if not root.is_dir():
            return
        with self._lock:
            if collection_id in self._watchers:
                return
            watcher = FolderWatcher(root, lambda _changes: self.reindex(collection_id))
            self._watchers[collection_id] = watcher
        watcher.start()

    def _publish(self, collection_id: str, progress: Progress) -> None:
        event = progress.as_dict()
        with self._lock:
            self._progress[collection_id] = progress
            subscribers = list(self._subscribers.get(collection_id, []))
        for loop, queue in subscribers:
            try:
                loop.call_soon_threadsafe(_offer, queue, event)
            except RuntimeError:
                self.unsubscribe(collection_id, queue)

    def _set_status(self, collection_id: str, status: str, error: str | None = None) -> None:
        conn = connect()
        with conn:
            conn.execute(
                "UPDATE collections SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                (status, error, time.time(), collection_id),
            )

    def _run(self, collection_id: str) -> None:
        job = self._job(collection_id)
        with job.lock:
            with self._lock:
                job.pending = False
                full, job.full = job.full, False
            if job.cancelled:
                return
            try:
                self._index(collection_id, job, full)
            except Exception as exc:
                log.exception("indexing failed for %s", collection_id)
                self._set_status(collection_id, "error", str(exc))
                self._publish(collection_id, Progress(state="error", current=str(exc)))

    def _index(self, collection_id: str, job: _Job, full: bool) -> None:
        conn = connect()
        row = conn.execute("SELECT path, embeddings FROM collections WHERE id = ?", (collection_id,)).fetchone()
        if row is None:
            return
        root = Path(row["path"])
        if not root.is_dir():
            raise FileNotFoundError(f"folder not found: {root}")

        progress = Progress(state="scanning")
        self._publish(collection_id, progress)
        self._set_status(collection_id, "indexing")

        files = scan(root)
        existing = {
            r["rel_path"]: r
            for r in conn.execute(
                "SELECT id, rel_path, size, mtime, sha256, status FROM documents WHERE collection_id = ?",
                (collection_id,),
            )
        }
        seen = {path.relative_to(root).as_posix() for path in files}
        for rel_path, doc in existing.items():
            if rel_path not in seen:
                store.delete_document(conn, collection_id, doc["id"])

        embedder = get_embedder(row["embeddings"])
        max_bytes = get_settings().max_file_mb * 1024 * 1024
        settings = get_settings()
        progress = Progress(state="indexing", total=len(files))
        self._publish(collection_id, progress)

        work = []
        for path in files:
            rel_path = path.relative_to(root).as_posix()
            try:
                stat = path.stat()
            except OSError:
                progress.done += 1
                continue
            doc = existing.get(rel_path)
            if not full and doc and doc["size"] == stat.st_size and doc["mtime"] == stat.st_mtime \
                    and doc["status"] in ("indexed", "skipped"):
                progress.done += 1
                continue
            work.append((path, rel_path, stat, doc))
        self._publish(collection_id, progress)

        def prepare(item):
            path, rel_path, stat, doc = item
            if stat.st_size > max_bytes:
                return item, None, None, f"larger than {settings.max_file_mb} MB", "skipped"
            digest = sha256_of(path)
            if not full and doc and doc["sha256"] == digest and doc["status"] == "indexed":
                return item, digest, None, None, "unchanged"
            try:
                chunks = chunk(parse(path), settings.chunk_size, settings.chunk_overlap)
            except UnsupportedFile as exc:
                return item, digest, None, str(exc), "skipped"
            except ParseError as exc:
                return item, digest, None, str(exc), "error"
            return item, digest, chunks, None, "indexed"

        for result in self._parsers.map(prepare, work):
            if job.cancelled:
                return
            (path, rel_path, stat, doc), digest, chunks, error, status = result
            progress.current = rel_path
            doc_id = doc["id"] if doc else uuid.uuid4().hex
            try:
                if status == "indexed" and chunks:
                    vectors = self._embed(embedder, chunks, rel_path)
                    self._upsert(conn, collection_id, doc_id, path, rel_path, stat, digest, "indexed", None,
                                 len(chunks))
                    store.replace_document_chunks(conn, collection_id, doc_id, chunks, vectors)
                elif status == "unchanged":
                    self._upsert(conn, collection_id, doc_id, path, rel_path, stat, digest, "indexed", None,
                                 None)
                else:
                    if status == "indexed":
                        status, error = "skipped", "no text content"
                    self._upsert(conn, collection_id, doc_id, path, rel_path, stat, digest, status, error, 0)
                    store.clear_document_chunks(conn, collection_id, doc_id)
            except Exception as exc:
                log.warning("failed to index %s", rel_path, exc_info=True)
                status = "error"
                self._upsert(conn, collection_id, doc_id, path, rel_path, stat, digest, "error", str(exc), 0)
            if status == "error":
                progress.errors += 1
            progress.done += 1
            self._publish(collection_id, progress)

        self._set_status(collection_id, "idle")
        self._publish(collection_id, Progress(state="idle", done=progress.total, total=progress.total,
                                              errors=progress.errors))

    @staticmethod
    def _embed(embedder, chunks: list[Chunk], rel_path: str) -> np.ndarray:
        texts = [embedding_text(item, rel_path) for item in chunks]
        parts = [embedder.embed(texts[i : i + EMBED_BATCH]) for i in range(0, len(texts), EMBED_BATCH)]
        return np.vstack(parts)

    @staticmethod
    def _upsert(conn, collection_id, doc_id, path, rel_path, stat, digest, status, error, chunk_count) -> None:
        mime = mimetypes.guess_type(path.name)[0]
        with conn:
            conn.execute(
                "INSERT INTO documents (id, collection_id, path, rel_path, ext, mime, size, mtime, sha256, status,"
                " error, chunk_count, indexed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, 0), ?)"
                " ON CONFLICT(id) DO UPDATE SET size = excluded.size, mtime = excluded.mtime,"
                " sha256 = excluded.sha256, status = excluded.status, error = excluded.error,"
                " chunk_count = COALESCE(?, documents.chunk_count), indexed_at = excluded.indexed_at",
                (doc_id, collection_id, str(path), rel_path, path.suffix.lower(), mime, stat.st_size,
                 stat.st_mtime, digest, status, error, chunk_count, time.time(), chunk_count),
            )


def _offer(queue: asyncio.Queue, event: dict) -> None:
    # un cliente lento no debe frenar la indexación: descartamos el evento más viejo
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(event)


_manager: IndexManager | None = None
_manager_lock = threading.Lock()


def get_index_manager() -> IndexManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = IndexManager()
        return _manager
