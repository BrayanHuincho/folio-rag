from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

from folio.config import get_settings
from folio.db import connect
from folio.index.search import Hit, search
from folio.llm import ChatMessage, get_client

from .prompts import CONDENSE_PROMPT, NO_SOURCES, SYSTEM_PROMPT, TITLE_PROMPT, format_source

log = logging.getLogger(__name__)

HISTORY_TURNS = 6
SNIPPET_CHARS = 280
ATTACHMENT_TOP_K = 12
ATTACHMENT_WAIT_SECONDS = 90

Event = tuple[str, dict]


class ChatError(Exception):
    pass


async def chat(
    collection_id: str,
    message: str,
    *,
    conversation_id: str | None = None,
    model: str | None = None,
    top_k: int | None = None,
    attachments: list[str] | None = None,
) -> AsyncIterator[Event]:
    try:
        async for event in _chat(
            collection_id, message, conversation_id, model, top_k, attachments or []
        ):
            yield event
    except Exception as exc:
        log.exception("chat failed")
        yield "error", {"message": str(exc) or exc.__class__.__name__}


async def _chat(
    collection_id: str,
    message: str,
    conversation_id: str | None,
    model: str | None,
    top_k: int | None,
    attachments: list[str],
) -> AsyncIterator[Event]:
    settings = get_settings()
    conn = connect()

    if not conn.execute("SELECT 1 FROM collections WHERE id = ?", (collection_id,)).fetchone():
        raise ChatError("Colección no encontrada")

    is_new = conversation_id is None
    if is_new:
        spec = model or settings.llm
        conversation_id = _create_conversation(conn, collection_id, spec)
        history: list[ChatMessage] = []
    else:
        row = conn.execute(
            "SELECT model FROM conversations WHERE id = ? AND collection_id = ?",
            (conversation_id, collection_id),
        ).fetchone()
        if not row:
            raise ChatError("Conversación no encontrada")
        spec = model or row["model"] or settings.llm
        history = _load_history(conn, conversation_id)

    client = get_client(spec)
    message_id = uuid.uuid4().hex
    yield "meta", {"conversation_id": conversation_id, "message_id": message_id, "model": spec}

    attached = await _wait_for_documents(conn, collection_id, attachments) if attachments else []
    if attachments and not attached:
        raise ChatError("No pude leer los archivos adjuntos. Revisa que el formato sea compatible.")

    query = await _condense(history, message, spec) if history else message
    k = top_k or settings.top_k
    if attached:
        # con adjuntos el usuario pregunta por ese archivo: traemos más de él
        k = max(k, ATTACHMENT_TOP_K)
    hits = await asyncio.to_thread(
        search, collection_id, query, k, document_ids=[d["id"] for d in attached] or None
    )
    sources = [_source(n, hit) for n, hit in enumerate(hits, start=1)]
    yield "sources", {"sources": sources}

    context = "\n\n".join(
        format_source(n, h.rel_path, h.page, h.heading, h.text) for n, h in enumerate(hits, 1)
    )
    prompt = [
        ChatMessage("system", SYSTEM_PROMPT.format(context=context or NO_SOURCES)),
        *history,
        ChatMessage("user", message),
    ]

    parts: list[str] = []
    async for text in client.stream(prompt, max_tokens=get_settings().max_tokens):
        parts.append(text)
        yield "token", {"text": text}

    # se guarda recién aquí para no dejar preguntas huérfanas si el modelo falla
    _insert_message(
        conn, uuid.uuid4().hex, conversation_id, "user", message, None,
        json.dumps(attached) if attached else None,
    )
    _insert_message(
        conn, message_id, conversation_id, "assistant", "".join(parts), json.dumps(sources)
    )

    done: dict = {}
    if client.usage:
        done["usage"] = client.usage
    if is_new:
        title = await _title(message, spec)
        conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
        conn.commit()
        done["title"] = title
    yield "done", done


def _create_conversation(conn, collection_id: str, spec: str) -> str:
    conversation_id = uuid.uuid4().hex
    now = time.time()
    conn.execute(
        "INSERT INTO conversations (id, collection_id, title, model, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (conversation_id, collection_id, "Nueva conversación", spec, now, now),
    )
    conn.commit()
    return conversation_id


def _load_history(conn, conversation_id: str) -> list[ChatMessage]:
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ?"
        " ORDER BY created_at DESC LIMIT ?",
        (conversation_id, HISTORY_TURNS * 2),
    ).fetchall()
    return [ChatMessage(r["role"], r["content"]) for r in reversed(rows)]


async def _wait_for_documents(conn, collection_id: str, rel_paths: list[str]) -> list[dict]:
    # recién subidos pueden seguir indexándose; esperamos un poco antes de rendirnos
    wanted = [p.replace("\\", "/") for p in rel_paths]
    placeholders = ",".join("?" * len(wanted))
    sql = (
        "SELECT id, rel_path, ext, size, status FROM documents WHERE collection_id = ?"
        f" AND replace(rel_path, '\\', '/') IN ({placeholders})"
    )
    deadline = time.monotonic() + ATTACHMENT_WAIT_SECONDS
    while True:
        rows = [dict(r) for r in conn.execute(sql, (collection_id, *wanted))]
        pending = len(rows) < len(wanted) or any(r["status"] == "pending" for r in rows)
        if not pending or time.monotonic() > deadline:
            break
        await asyncio.sleep(0.5)
    return [
        {"id": r["id"], "rel_path": r["rel_path"], "ext": r["ext"], "size": r["size"]}
        for r in rows
        if r["status"] == "indexed"
    ]


def _insert_message(
    conn, message_id, conversation_id, role, content, sources_json, attachments_json=None
) -> None:
    now = time.time()
    conn.execute(
        "INSERT INTO messages"
        " (id, conversation_id, role, content, sources_json, attachments_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (message_id, conversation_id, role, content, sources_json, attachments_json, now),
    )
    conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
    conn.commit()


def _source(n: int, hit: Hit) -> dict:
    snippet = " ".join(hit.text.split())
    if len(snippet) > SNIPPET_CHARS:
        snippet = snippet[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"
    return {
        "n": n,
        "chunk_id": hit.chunk_id,
        "document_id": hit.document_id,
        "rel_path": hit.rel_path,
        "page": hit.page,
        "heading": hit.heading,
        "snippet": snippet,
        "score": round(float(hit.score), 4),
    }


def _fast_client(fallback: str):
    return get_client(get_settings().fast_llm or fallback)


async def _condense(history: list[ChatMessage], question: str, spec: str) -> str:
    transcript = "\n".join(f"{m.role}: {m.content[:1000]}" for m in history)
    try:
        query = await _fast_client(spec).complete(
            [ChatMessage("user", CONDENSE_PROMPT.format(history=transcript, question=question))],
            temperature=0,
            max_tokens=200,
        )
    except Exception:
        log.warning("query condensing failed; using the raw question", exc_info=True)
        return question
    return query.strip() or question


async def _title(question: str, spec: str) -> str:
    fallback = question.strip().splitlines()[0][:60] if question.strip() else "Nueva conversación"
    try:
        title = await _fast_client(spec).complete(
            [ChatMessage("user", TITLE_PROMPT.format(question=question[:1000]))],
            temperature=0.3,
            max_tokens=30,
        )
    except Exception:
        log.warning("title generation failed", exc_info=True)
        return fallback
    return title.strip().strip("\"'").rstrip(".") or fallback
