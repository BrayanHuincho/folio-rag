from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from folio.rag import engine

router = APIRouter(tags=["chat"])


class ChatIn(BaseModel):
    collection_id: str
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    model: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    attachments: list[str] = Field(default_factory=list, max_length=20)


@router.post("/chat")
async def chat(body: ChatIn) -> EventSourceResponse:
    async def events():
        async for event, data in engine.chat(
            body.collection_id,
            body.message,
            conversation_id=body.conversation_id,
            model=body.model,
            top_k=body.top_k,
            attachments=body.attachments,
        ):
            yield {"event": event, "data": json.dumps(data, ensure_ascii=False)}

    return EventSourceResponse(events())
