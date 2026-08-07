"""Tests for opt-in community summaries (LWM_030).

Covers default-untouched-when-not-invoked, one-call-per-community + global,
dry-run (no calls/writes), first-class page storage + idempotency, the
faithfulness filter (key_entities ⊆ member entities), and graceful LLM failure.
The summarizer is injected for deterministic offline runs (no network).
"""

from llm_wiki.graph import summarize
from llm_wiki.graph.summarize import CommunitySummary, summarize_communities


def _make_two_community_wiki(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    def page(name, title, links):
        body = "".join(f"See [[{l}]].\n" for l in links)
        (wiki / f"{name}.md").write_text(
            f"---\ntitle: {title}\ntype: concept\n---\n\n# {title}\n\n{body}",
            encoding="utf-8",
        )

    # Cluster A (triangle) and cluster B (triangle) — two clear communities.
    page("a1", "A1", ["A2", "A3"])
    page("a2", "A2", ["A1", "A3"])
    page("a3", "A3", ["A1", "A2"])
    page("b1", "B1", ["B2", "B3"])
    page("b2", "B2", ["B1", "B3"])
    page("b3", "B3", ["B1", "B2"])
    return tmp_path, wiki


class _CountingSummarizer:
    def __init__(self, key_entities=None):
        self.calls = 0
        self.key_entities = key_entities

    def __call__(self, system, user):
        self.calls += 1
        ke = self.key_entities if self.key_entities is not None else ["A1"]
        return CommunitySummary(title=f"Theme {self.calls}",
                                summary="A generated theme.", key_entities=ke)


def test_default_unchanged_when_not_invoked(tmp_path):
    _root, wiki = _make_two_community_wiki(tmp_path)
    # Never running the operation leaves no communities/ directory.
    assert not (wiki / "communities").exists()


def test_one_call_per_community_plus_global(tmp_path):
    root, wiki = _make_two_community_wiki(tmp_path)
    s = _CountingSummarizer()
    stats = summarize_communities(root, summarizer=s)
    # 2 communities → 2 per-community calls + 1 global root call.
    assert stats["communities"] == 2
    assert stats["summarized"] == 2
    assert s.calls == 3
    assert (wiki / "communities" / "global-summary.md").exists()


def test_dry_run_makes_no_calls_no_writes(tmp_path):
    root, wiki = _make_two_community_wiki(tmp_path)
    s = _CountingSummarizer()
    stats = summarize_communities(root, dry_run=True, summarizer=s)
    assert s.calls == 0
    assert stats["written"] == 0
    assert not (wiki / "communities").exists()


def test_pages_written_and_idempotent(tmp_path):
    root, wiki = _make_two_community_wiki(tmp_path)
    s1 = _CountingSummarizer()
    summarize_communities(root, summarizer=s1)
    comm_pages = list((wiki / "communities").glob("L0-*.md"))
    assert len(comm_pages) == 2
    text = comm_pages[0].read_text(encoding="utf-8")
    assert "type: community-summary" in text
    assert "member_sha:" in text

    # Re-run: unchanged member sets are skipped (no new calls for them).
    s2 = _CountingSummarizer()
    stats2 = summarize_communities(root, summarizer=s2)
    assert stats2["skipped"] == 2
    assert stats2["summarized"] == 0


def test_faithfulness_filters_non_member_entities(tmp_path):
    root, wiki = _make_two_community_wiki(tmp_path)
    # One valid member entity (A1) + one hallucinated non-member.
    s = _CountingSummarizer(key_entities=["A1", "TOTALLY-NOT-A-MEMBER"])
    summarize_communities(root, summarizer=s)
    all_text = "\n".join(p.read_text(encoding="utf-8")
                         for p in (wiki / "communities").glob("L0-*.md"))
    assert "TOTALLY-NOT-A-MEMBER" not in all_text  # dropped by faithfulness filter


def test_llm_failure_skips_without_corrupt_write(tmp_path):
    root, wiki = _make_two_community_wiki(tmp_path)

    def failing(system, user):
        return None  # simulate exhausted retries

    stats = summarize_communities(root, summarizer=failing)
    assert stats["failed"] >= 1
    assert stats["written"] == 0
    # No partial/corrupt pages written.
    assert not list((wiki / "communities").glob("L0-*.md")) if (wiki / "communities").exists() else True


def test_max_communities_cap(tmp_path):
    root, _wiki = _make_two_community_wiki(tmp_path)
    s = _CountingSummarizer()
    stats = summarize_communities(root, max_communities=1, summarizer=s)
    assert stats["communities"] == 1
    assert stats["summarized"] == 1
