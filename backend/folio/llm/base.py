from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChatMessage:
    role: str
    content: str


class LLMError(RuntimeError):
    pass


HTTP_HINTS = {
    401: "La API key no es válida o fue revocada.",
    402: "No te queda saldo suficiente en el proveedor. Recarga créditos o usa un modelo más barato.",
    403: "El proveedor rechazó la petición: revisa los permisos de tu API key.",
    404: "El modelo no existe o no tienes acceso a él.",
    429: "Demasiadas peticiones seguidas. Espera unos segundos y vuelve a intentarlo.",
}


def http_error(spec: str, status: int, body: str) -> LLMError:
    hint = HTTP_HINTS.get(status) or (
        "El proveedor está teniendo problemas. Inténtalo de nuevo en un momento."
        if status >= 500
        else f"El proveedor respondió con error {status}."
    )
    return LLMError(f"{spec}: {hint}\n\nDetalle: {body[:300]}")


class LLMClient(Protocol):
    spec: str
    usage: dict | None

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]: ...

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str: ...


class StreamingClient:
    spec: str
    usage: dict | None = None

    def stream(self, messages, *, temperature=0.2, max_tokens=None) -> AsyncIterator[str]:
        raise NotImplementedError

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        parts = [
            part
            async for part in self.stream(messages, temperature=temperature, max_tokens=max_tokens)
        ]
        return "".join(parts)
