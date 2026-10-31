import time

from folio.db import connect
from folio.index.search import fts_query, search
from folio.ingest.pipeline import IndexManager, is_ignored


def wait_idle(manager: IndexManager, collection_id: str, timeout: float = 20) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        progress = manager.progress(collection_id)
        if progress["state"] == "idle" and progress["total"]:
            return progress
        time.sleep(0.05)
    raise TimeoutError(manager.progress(collection_id))


def build(tmp_path, settings):
    folder = tmp_path / "docs"
    (folder / "sub").mkdir(parents=True)
    (folder / "node_modules").mkdir()
    (folder / "cats.md").write_text("# Cats\nCats purr and sleep all day.", encoding="utf-8")
    (folder / "sub" / "rockets.txt").write_text("Rockets need fuel and oxygen to launch.", encoding="utf-8")
    (folder / "secret.txt").write_text("Rockets secret ignored file.", encoding="utf-8")
    (folder / "node_modules" / "x.txt").write_text("Rockets in node modules.", encoding="utf-8")
    (folder / ".folioignore").write_text("secret.*\n", encoding="utf-8")
    manager = IndexManager()
    collection = manager.add_collection("Docs", folder)
    wait_idle(manager, collection["id"])
    return manager, collection, folder


def test_fts_query_escapes_operators():
    assert fts_query('rockets AND "fuel" NEAR(x) -*') == '"rockets" OR "and" OR "fuel" OR "near"'
    assert fts_query("***") == ""


def test_folioignore_patterns():
    assert is_ignored("logs/a.txt", ["logs/"])
    assert is_ignored("a/b.tmp", ["*.tmp"])
    assert not is_ignored("a/b.txt", ["*.tmp"])


def test_hybrid_search_and_incremental(tmp_path, settings):
    manager, collection, folder = build(tmp_path, settings)
    try:
        conn = connect()
        paths = {r["rel_path"] for r in conn.execute("SELECT rel_path FROM documents")}
        assert paths == {"cats.md", "sub/rockets.txt"}

        hits = search(collection["id"], "rocket fuel", k=2)
        assert hits[0].rel_path == "sub/rockets.txt"
        filtered = search(collection["id"], "rockets", k=5, path_filter="cats")
        assert filtered and all(h.rel_path == "cats.md" for h in filtered)
        assert search(collection["id"], 'cats" OR (', k=3)[0].rel_path == "cats.md"
        cats_id = conn.execute("SELECT id FROM documents WHERE rel_path = 'cats.md'").fetchone()[0]
        scoped = search(collection["id"], "rocket fuel", k=5, document_ids=[cats_id])
        assert scoped and all(h.rel_path == "cats.md" for h in scoped)

        (folder / "cats.md").unlink()
        (folder / "dogs.txt").write_text("Dogs bark loudly.", encoding="utf-8")
        manager.reindex(collection["id"])
        time.sleep(0.2)
        wait_idle(manager, collection["id"])
        paths = {r["rel_path"] for r in conn.execute("SELECT rel_path FROM documents")}
        assert paths == {"dogs.txt", "sub/rockets.txt"}
        assert search(collection["id"], "dogs bark", k=1)[0].rel_path == "dogs.txt"
        assert conn.execute("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'purr'").fetchone()[0] == 0
    finally:
        manager.stop()
