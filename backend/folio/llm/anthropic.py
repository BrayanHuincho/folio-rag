from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .base import ChatMessage, LLMError, StreamingClient, http_error

API_URL = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096
TIMEOUT = httpx.Timeout(120.0, connect=10.0)


class AnthropicClient(StreamingClient):
    def __init__(self, spec: str, model: str, api_key: str):
        self.spec = spec
        self.model = model
        self.headers = {
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }
        self.usage = None

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": m.role, "content": m.content} for m in messages if m.role != "system"
            ],
            "max_tokens": max_tokens or DEFAULT_MAX_TOKENS,
            "temperature": temperature,
            "stream": True,
        }
        if system:
            payload["system"] = system

        self.usage = None
        usage: dict = {}
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream(
                "POST", f"{API_URL}/messages", json=payload, headers=self.headers
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode(errors="replace")
                    raise http_error(self.spec, response.status_code, body)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    kind = event.get("type")
                    if kind == "content_block_delta":
                        text = event.get("delta", {}).get("text")
                        if text:
                            yield text
                    elif kind == "message_start":
                        usage.update(event.get("message", {}).get("usage") or {})
                    elif kind == "message_delta":
                        usage.update(event.get("usage") or {})
                    elif kind == "error":
                        raise LLMError(f"{self.spec}: {event.get('error')}")
        if usage:
            self.usage = {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
            }
