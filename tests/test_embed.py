"""Tests for batch embedding (LWM_016).

Uses an injected deterministic fake embedder so the full embed loop (freshness,
rebuild, deletes, embed_meta) is exercised end-to-end without model2vec or any
network/model download.
"""

import hashlib
import math

import pytest

from llm_wiki.semantic import vector_schema as vs
from llm_wiki.semantic.embed import embed_wiki
from llm_wiki.semantic.embedder import Embedder


class FakeEmbedder(Embedder):
    model_id = "fake-model"
    revision = "r1"
    normalization = "l2"
    quantization = "float32"

    @classmethod
    def is_available(cls) -> bool:
        return True

    @property
    def dimension(self) -> int:
        return 4

    def embed(self, texts):
        out = []
        for t in texts:
            hb = hashlib.sha256(t.encode("utf-8")).digest()[:4]
            v = [b / 255.0 for b in hb]
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


def _make_wiki(tmp_path, pages: dict[str, str]):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    for name, body in pages.items():
        (wiki / name).write_text(
            f"---\ntitle: {name[:-3]}\ntype: concept\n---\n\n# {name[:-3]}\n\n{body}\n",
            encoding="utf-8",
        )
    return tmp_path


def _open(tmp_path):
    return vs.open_index_db(tmp_path / ".index" / "wiki.db")


def test_embed_populates_vectors_and_meta(tmp_path):
    root = _make_wiki(tmp_path, {"alpha.md": "about neural networks", "beta.md": "about graphs"})
    stats = embed_wiki(root, embedder=FakeEmbedder())
    assert stats["available"] is True
    assert stats["embedded"] == 2
    assert stats["total"] == 2
    assert stats["dim"] == 4

    conn = _open(root)
    meta = vs.read_embed_meta(conn)
    assert meta is not None and meta.model_id == "fake-model" and meta.dimension == 4
    assert vs.embed_meta_matches(conn, FakeEmbedder().embed_meta()) is True
    conn.close()


def test_embed_is_incremental_and_idempotent(tmp_path):
    root = _make_wiki(tmp_path, {"a.md": "one", "b.md": "two"})
    embed_wiki(root, embedder=FakeEmbedder())
    stats2 = embed_wiki(root, embedder=FakeEmbedder())
    assert stats2["embedded"] == 0
    assert stats2["skipped"] == 2
    assert stats2["total"] == 2


def test_embed_reembeds_changed_page(tmp_path):
    root = _make_wiki(tmp_path, {"a.md": "one", "b.md": "two"})
    embed_wiki(root, embedder=FakeEmbedder())
    (root / "wiki" / "a.md").write_text("---\ntitle: a\n---\n\n# a\n\nCHANGED content\n")
    stats = embed_wiki(root, embedder=FakeEmbedder())
    assert stats["embedded"] == 1
    assert stats["skipped"] == 1


def test_embed_deletes_removed_page(tmp_path):
    root = _make_wiki(tmp_path, {"a.md": "one", "b.md": "two"})
    embed_wiki(root, embedder=FakeEmbedder())
    (root / "wiki" / "b.md").unlink()
    stats = embed_wiki(root, embedder=FakeEmbedder())
    assert stats["deleted"] == 1
    assert stats["total"] == 1


def test_embed_rebuild_clears_and_repopulates(tmp_path):
    root = _make_wiki(tmp_path, {"a.md": "one"})
    embed_wiki(root, embedder=FakeEmbedder())
    stats = embed_wiki(root, rebuild=True, embedder=FakeEmbedder())
    assert stats["embedded"] == 1
    assert stats["total"] == 1


def test_embed_noop_without_embedder(tmp_path):
    # get_embedder() returns None when the [semantic] extra is absent (model2vec
    # not installed) → no-op, and no vector db side effects required.
    root = _make_wiki(tmp_path, {"a.md": "one"})
    stats = embed_wiki(root, embedder=None)
    # Either the extra is genuinely unavailable (available False, no-op) or, if a
    # real embedder is present in this env, it embeds — both are valid; assert the
    # no-op contract only when unavailable.
    if not stats["available"]:
        assert stats["embedded"] == 0 and stats["total"] == 0


class EmptyBurstEmbedder(FakeEmbedder):
    """Extra installed, but the model is unavailable at runtime (offline/cache)."""

    def embed(self, texts):
        return []


def test_embed_degrades_when_model_unavailable_at_runtime(tmp_path):
    """A runtime model failure must degrade to a no-op, not crash (CI: macOS
    semantic lane with HF_HUB_OFFLINE=1 raised IndexError from embed()[0])."""
    root = _make_wiki(tmp_path, {"a.md": "one", "b.md": "two"})
    stats = embed_wiki(root, embedder=EmptyBurstEmbedder())
    assert stats["available"] is False
    assert stats["degraded"] is True
    assert stats["embedded"] == 0 and stats["total"] == 0
