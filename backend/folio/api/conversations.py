from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from folio.db import connect

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
def list_conversations(collection_id: str | None = None) -> list[dict]:
    # las que fallaron antes de guardar algo no aportan nada en el historial
    sql = (
        "SELECT id, title, model, updated_at FROM conversations c"
        " WHERE EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id)"
    )
    params: tuple = ()
    if collection_id:
        sql += " AND collection_id = ?"
        params = (collection_id,)
    rows = connect().execute(sql + " ORDER BY updated_at DESC", params).fetchall()
    return [dict(row) for row in rows]


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    conn = connect()
    row = conn.execute(
        "SELECT id, title, model FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Conversación no encontrada")
    messages = conn.execute(
        "SELECT id, role, content, sources_json, attachments_json, created_at FROM messages"
        " WHERE conversation_id = ? ORDER BY created_at",
        (conversation_id,),
    ).fetchall()
    return {
        **dict(row),
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "sources": json.loads(m["sources_json"]) if m["sources_json"] else [],
                "attachments": json.loads(m["attachments_json"]) if m["attachments_json"] else [],
                "created_at": m["created_at"],
            }
            for m in messages
        ],
    }


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


@router.patch("/{conversation_id}")
def rename_conversation(conversation_id: str, body: RenameIn) -> dict:
    conn = connect()
    cursor = conn.execute(
        "UPDATE conversations SET title = ? WHERE id = ?", (body.title.strip(), conversation_id)
    )
    conn.commit()
    if not cursor.rowcount:
        raise HTTPException(404, "Conversación no encontrada")
    return {"id": conversation_id, "title": body.title.strip()}


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str) -> Response:
    conn = connect()
    cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    if not cursor.rowcount:
        raise HTTPException(404, "Conversación no encontrada")
    return Response(status_code=204)
