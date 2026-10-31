from __future__ import annotations

import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

import folio.api as api
import folio.api.collections as api_collections
from folio.config import get_settings
from folio.db import connect
from folio.index.search import Hit
from folio.rag import engine


class FakeManager:
    def start(self) -> None: ...
    def stop(self) -> None: ...

    def progress(self, collection_id: str) -> dict:
        return {"state": "idle", "done": 0, "total": 0, "current": None, "errors": 0}


class FakeLLM:
    spec = "fake:model"

    def __init__(self) -> None:
        self.usage = None
        self.prompts: list[list] = []

    async def stream(self, messages, *, temperature=0.2, max_tokens=None):
        self.prompts.append(messages)
        for part in ["The answer ", "is 42 ", "[1]."]:
            yield part
        self.usage = {"prompt_tokens": 10, "completion_tokens": 3}

    async def complete(self, messages, *, temperature=0.2, max_tokens=None):
        self.prompts.append(messages)
        prompt = messages[-1].content
        return "Meaning of life" if "title" in prompt else "standalone query"


def fake_search(collection_id: str, query: str, k: int, *, path_filter=None, document_ids=None) -> list[Hit]:
    return [
        Hit(
            chunk_id="c1",
            document_id="d1",
            rel_path="notes/guide.md",
            page=None,
            heading="Answers",
            text="The answer to everything is 42.",
            score=0.91,
        )
    ]


@pytest.fixture
def fake_llm(monkeypatch, tmp_path) -> FakeLLM:
    monkeypatch.setenv("FOLIO_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    manager = FakeManager()
    monkeypatch.setattr(api, "get_index_manager", lambda: manager)
    monkeypatch.setattr(api_collections, "get_index_manager", lambda: manager)
    llm = FakeLLM()
    monkeypatch.setattr(engine, "get_client", lambda spec=None: llm)
    monkeypatch.setattr(engine, "search", fake_search)
    yield llm
    get_settings.cache_clear()


@pytest.fixture
def client(fake_llm) -> TestClient:
    with TestClient(api.create_app()) as test_client:
        yield test_client


@pytest.fixture
def collection_id(client, tmp_path) -> str:
    cid = uuid.uuid4().hex
    now = time.time()
    conn = connect()
    conn.execute(
        "INSERT INTO collections (id, name, path, embeddings, status, created_at, updated_at)"
        " VALUES (?, 'Docs', ?, 'local:test', 'idle', ?, ?)",
        (cid, str(tmp_path), now, now),
    )
    conn.commit()
    return cid


def read_events(response) -> list[tuple[str, dict]]:
    events, name = [], None
    for line in response.text.splitlines():
        if line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:") and name:
            events.append((name, json.loads(line[5:].strip())))
            name = None
    return events


def test_health(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["llm"] == get_settings().llm


def test_chat_streams_events_in_order(client, collection_id):
    response = client.post("/api/chat", json={"collection_id": collection_id, "message": "What?"})
    events = read_events(response)
    names = [name for name, _ in events]

    assert names[0] == "meta"
    assert names[1] == "sources"
    assert set(names[2:-1]) == {"token"}
    assert names[-1] == "done"

    sources = events[1][1]["sources"]
    assert sources[0]["n"] == 1
    assert sources[0]["rel_path"] == "notes/guide.md"
    assert "".join(d["text"] for n, d in events if n == "token") == "The answer is 42 [1]."
    assert events[-1][1] == {
        "usage": {"prompt_tokens": 10, "completion_tokens": 3},
        "title": "Meaning of life",
    }


def test_conversation_is_persisted_and_followups_use_history(client, collection_id, fake_llm):
    first = read_events(
        client.post("/api/chat", json={"collection_id": collection_id, "message": "What?"})
    )
    conversation_id = first[0][1]["conversation_id"]

    listed = client.get("/api/conversations", params={"collection_id": collection_id}).json()
    assert [c["id"] for c in listed] == [conversation_id]
    assert listed[0]["title"] == "Meaning of life"

    second = read_events(
        client.post(
            "/api/chat",
            json={
                "collection_id": collection_id,
                "conversation_id": conversation_id,
                "message": "Why?",
            },
        )
    )
    assert second[-1][0] == "done"
    assert "title" not in second[-1][1]

    detail = client.get(f"/api/conversations/{conversation_id}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert detail["messages"][1]["sources"][0]["chunk_id"] == "c1"
    assert detail["messages"][3]["id"] == second[0][1]["message_id"]

    final_prompt = fake_llm.prompts[-1]
    assert [m.role for m in final_prompt] == ["system", "user", "assistant", "user"]

    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 204
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404


def test_chat_unknown_collection_reports_error(client):
    events = read_events(client.post("/api/chat", json={"collection_id": "nope", "message": "x"}))
    assert events == [("error", {"message": "Colección no encontrada"})]


def test_browse_lists_directories(client, tmp_path):
    (tmp_path / "alpha").mkdir()
    (tmp_path / "file.txt").write_text("x")
    body = client.get("/api/fs/browse", params={"path": str(tmp_path)}).json()
    assert [d["name"] for d in body["dirs"]] == ["alpha"]
