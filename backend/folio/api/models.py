from __future__ import annotations

import asyncio

from fastapi import APIRouter

from folio import llm
from folio.config import get_settings

router = APIRouter(tags=["models"])


@router.get("/models")
async def list_models() -> dict:
    settings = get_settings()
    configured = set(llm.configured_providers())
    pinned = [spec.strip() for spec in settings.models.split(",") if spec.strip()]

    if pinned:
        lists = [[{"id": s, "name": s.partition(":")[2]} for s in pinned if s.startswith(f"{p}:")]
                 for p in llm.PROVIDERS]
    else:
        lists = await asyncio.gather(
            *(llm.list_models(p) if p in configured else _empty() for p in llm.PROVIDERS)
        )

    return {
        "default": settings.llm,
        "pinned": bool(pinned),
        "providers": [
            {
                "id": provider,
                "configured": provider in configured,
                "models": [
                    {k: m[k] for k in ("id", "name", "context", "free", "price_in", "price_out") if k in m}
                    for m in models
                ],
            }
            for provider, models in zip(llm.PROVIDERS, lists)
            # ollama y lmstudio no llevan key: solo cuentan si están encendidos
            if models or (provider in configured and provider not in llm.LOCAL_PROVIDERS)
        ],
    }


async def _empty() -> list[dict]:
    return []
