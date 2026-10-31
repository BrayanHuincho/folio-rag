from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .base import ChatMessage, LLMError, StreamingClient, http_error

TIMEOUT = httpx.Timeout(120.0, connect=10.0)


class OpenAICompatClient(StreamingClient):
    def __init__(
        self,
        spec: str,
        model: str,
        base_url: str,
        api_key: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        self.spec = spec
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json", **(extra_headers or {})}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        self.usage = None

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        self.usage = None
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload, headers=self.headers
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode(errors="replace")
                    raise http_error(self.spec, response.status_code, body)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if event.get("error"):
                        raise LLMError(f"{self.spec}: {event['error']}")
                    if event.get("usage"):
                        self.usage = event["usage"]
                    for choice in event.get("choices") or []:
                        text = (choice.get("delta") or {}).get("content")
                        if text:
                            yield text
