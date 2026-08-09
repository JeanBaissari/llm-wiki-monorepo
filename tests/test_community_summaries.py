"""Tests for opt-in community summaries (LWM_030).

Covers default-untouched-when-not-invoked, one-call-per-community + global,
dry-run (no calls/writes), first-class page storage + idempotency, the
faithfulness filter (key_entities ⊆ member entities), and graceful LLM failure.
The summarizer is injected for deterministic offline runs (no network).
"""

import json

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


class _RecordingSummarizer(_CountingSummarizer):
    """Summarizer that records every (system, user) prompt pair."""

    def __init__(self, key_entities=None):
        super().__init__(key_entities)
        self.records = []

    def __call__(self, system, user):
        self.records.append((system, user))
        return super().__call__(system, user)


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


def _summary_page(title, sha, level=0, summary="A generated theme."):
    return (
        "---\n"
        f"title: {title}\n"
        "type: community-summary\n"
        f"community: 0\n"
        f"level: {level}\n"
        "members: []\n"
        "key_entities: []\n"
        f"member_sha: {sha}\n"
        "generated_by: summarize-communities\n"
        "updated: 2026-01-01\n"
        "---\n\n"
        f"# {title}\n\n{summary}\n"
    )


def test_global_summary_faithful_when_community_leaks(tmp_path):
    """AD-9: a hallucinated entity returned by the LLM for BOTH a community and
    the global root must never reach any rendered page — the global reference
    is built from real member entities, not from raw (unfiltered) LLM output."""
    root, wiki = _make_two_community_wiki(tmp_path)
    s = _CountingSummarizer(key_entities=["A1", "HALLUCINATED-GLOBAL"])
    summarize_communities(root, summarizer=s)
    all_text = "\n".join(p.read_text(encoding="utf-8")
                         for p in (wiki / "communities").glob("*.md"))
    assert "A1" in all_text
    assert "HALLUCINATED-GLOBAL" not in all_text  # dropped in community AND global pages


def test_orphan_cleanup_removes_stale_pages(tmp_path):
    """AD-12: summary pages whose member_sha left the current partition are
    removed; unrelated files in communities/ are never touched."""
    root, wiki = _make_two_community_wiki(tmp_path)
    out = wiki / "communities"
    out.mkdir()
    stale1 = out / "L0-0000000000000000.md"
    stale1.write_text(_summary_page("Old Theme", "0000000000000000"), encoding="utf-8")
    stale2 = out / "L0-1111111111111111.md"
    stale2.write_text(_summary_page("Old Theme 2", "1111111111111111"), encoding="utf-8")
    note = out / "note.md"  # unrelated page, no community-summary type
    note.write_text("---\ntitle: Note\ntype: concept\n---\n\n# Note\n", encoding="utf-8")
    fake_summary = out / "L0-2222222222222222.md"  # matches naming, wrong type
    fake_summary.write_text(
        "---\ntitle: Not Summary\ntype: concept\nmember_sha: 2222222222222222\n---\n\n# N\n",
        encoding="utf-8")

    s = _CountingSummarizer()
    stats = summarize_communities(root, summarizer=s)

    assert stats["removed"] == 2
    assert not stale1.exists()
    assert not stale2.exists()
    assert note.exists()
    assert fake_summary.exists()
    # Expected current pages: derive the partition the same way production does
    # (isolated non-summary pages in communities/ are legitimate singleton
    # communities — the cleanup must never touch them).
    from llm_wiki.core.layout import discover_layout
    from llm_wiki.graph.insights import detect_communities_for_insights
    from llm_wiki.graph.suggest import load_pages

    layout = discover_layout(root)
    pages = load_pages(wiki, frozenset(f"{s}.md" for s in layout.skip_stems))
    member_pages = {stem: v for stem, v in pages.items()
                    if (v[2] or {}).get("type") != "community-summary"}
    nodes, edges = summarize._build_graph(member_pages)
    assignments = detect_communities_for_insights(nodes, edges, engine=None)
    by_comm = {}
    for stem, cid in assignments.items():
        if stem in pages and (pages[stem][2] or {}).get("type") == "community-summary":
            continue
        by_comm.setdefault(cid, []).append(stem)
    current = {summarize._member_sha(members) for members in by_comm.values()}
    summary_files = {p.name for p in out.glob("L0-*.md")
                     if "type: community-summary" in p.read_text(encoding="utf-8")}
    assert summary_files == {f"L0-{sha}.md" for sha in current}
    # Re-run is idempotent: no new removals, unchanged communities skipped.
    stats2 = summarize_communities(root, summarizer=_CountingSummarizer())
    assert stats2["removed"] == 0
    assert stats2["skipped"] == len(current)


def test_levels_flag_hierarchy(tmp_path):
    """AD-13: --levels 2 produces level-0 AND level-1 pages, one call per
    community per level, and the level-1 parent prompt includes its children's
    summary text (parents summarize child summaries)."""
    root, wiki = _make_two_community_wiki(tmp_path)
    s = _RecordingSummarizer()
    stats = summarize_communities(root, levels=2, summarizer=s)

    assert stats["levels"] == 2
    l0 = sorted((wiki / "communities").glob("L0-*.md"))
    l1 = list((wiki / "communities").glob("L1-*.md"))
    assert len(l0) == 2
    assert len(l1) == 1
    assert "level: 1" in l1[0].read_text(encoding="utf-8")
    # 2 level-0 + 1 level-1 parent + 1 global root.
    assert s.calls == 4
    parent_user = s.records[2][1]
    assert "Child summaries" in parent_user
    assert "Theme 1" in parent_user and "Theme 2" in parent_user


def test_degrade_flat_when_no_hierarchy(tmp_path):
    """AD-13: with no Leiden hierarchy source (opt-in [leiden] extra), an
    explicit --engine leiden caps at flat + global — levels > 1 are no-ops
    with the degrade noted in the stats, no crash."""
    root, wiki = _make_two_community_wiki(tmp_path)
    s = _CountingSummarizer()
    stats = summarize_communities(root, levels=3, engine="leiden", summarizer=s)

    assert stats["hierarchy"] == "flat"
    assert stats["levels"] == 1
    assert not list((wiki / "communities").glob("L1-*.md"))
    assert (wiki / "communities" / "global-summary.md").exists()
    assert stats["calls"] == 3  # 2 flat communities + global only


def test_partition_levels_deterministic(tmp_path):
    root, wiki = _make_two_community_wiki(tmp_path)
    from llm_wiki.core.layout import discover_layout
    from llm_wiki.graph.suggest import load_pages

    layout = discover_layout(root)
    pages = load_pages(wiki, frozenset())
    nodes, edges = summarize._build_graph(pages)
    a = summarize._partition_levels(nodes, edges, engine=None, max_levels=2)
    b = summarize._partition_levels(nodes, edges, engine=None, max_levels=2)
    assert a == b  # deterministic coarsening
    levels, source = a
    assert source == "agglomerated"
    assert len(levels) == 2
    assert levels[1]["level"] == 1


def test_summary_faithfulness_metric():
    """LWM_030 AC#7 metric: rate of key_entities ⊆ member entities (1.0 perfect)."""
    members = {0: {"A1", "A2"}, 1: {"B1"}}
    assert summarize.summary_faithfulness([(0, ["A1", "A2"]), (1, ["B1"])], members) == 1.0
    assert summarize.summary_faithfulness(
        [{"community": 0, "key_entities": ["A1"]},
         {"community": 1, "key_entities": ["B1", "BOGUS"]}], members) == 0.5
    assert summarize.summary_faithfulness([(0, ["NOPE"]), (1, ["ALSO-NOPE"])], members) == 0.0
    # Case-normalized comparison; empty key_entities counts as faithful.
    assert summarize.summary_faithfulness([(0, ["a1"])], {0: {"A1"}}) == 1.0
    assert summarize.summary_faithfulness([(0, [])], members) == 1.0
    assert summarize.summary_faithfulness([], members) == 1.0  # vacuous


def test_offline_provider_via_response_file(tmp_path, monkeypatch):
    """LWM_030 deferred row: deterministic offline flow via LLM_WIKI_RESPONSE_FILE.

    The agent-native (opencode) provider reads LLM_WIKI_RESPONSE_FILE when no
    response arrives; with the poll timeout zeroed and the file holding a fixed
    CommunitySummary JSON, ``summarize_communities`` runs fully offline through
    the REAL default-provider path — verbatim responses, no network, no API key.
    """
    from llm_wiki.providers import registry

    root, wiki = _make_two_community_wiki(tmp_path)
    rf = tmp_path / "response.json"
    rf.write_text(json.dumps({
        "title": "Offline Theme",
        "summary": "A deterministic offline summary.",
        "key_entities": ["A1"],
    }), encoding="utf-8")

    # Offline wiring: agent-mode default provider + response file + no polling.
    monkeypatch.setenv("LLM_WIKI_RESPONSE_FILE", str(rf))
    monkeypatch.setenv("LLM_WIKI_AGENT_MODE", "1")      # default provider → opencode
    monkeypatch.setenv("LLM_WIKI_OPCODE_DIR", str(tmp_path / "opcode"))
    monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "0")  # never poll → read file
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "DEEPSEEK_API_KEY", "TOGETHER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert registry.detect_default_provider() == "opencode"

    stats = summarize_communities(root, timeout=30)
    assert stats["summarized"] == 2
    assert stats["calls"] == 3  # 2 communities + 1 global root
    assert stats["written"] == 3

    # Verbatim: the offline title/summary text lands in the rendered pages.
    pages = [p.read_text(encoding="utf-8") for p in (wiki / "communities").glob("*.md")]
    assert sum("Offline Theme" in t for t in pages) == 3
    assert all("A deterministic offline summary." in t for t in pages)
    # key_entities from the file pass the faithfulness filter per community.
    l0 = (wiki / "communities" / "L0-*.md").parent.glob("L0-*.md")
    l0_text = "\n".join(p.read_text(encoding="utf-8") for p in l0)
    assert '"A1"' in l0_text  # A1 is a member of community A
    assert "TOTALLY-NOT-A-MEMBER" not in l0_text  # nothing hallucinated
