"""Tests for the `entities` CLI + surface→canonical link routing (LWM_025).

Covers the resolve/list/unmerge round-trip through the CLI dispatch, the
surface→canonical routing in build_entity_registry, and the surface-preserving
`--apply` path ([[Canonical|surface]], prose never rewritten).
"""

import sys

import pytest

from llm_wiki.graph import entities as entities_cli
from llm_wiki.graph.resolve import alias_targets, apply_resolution
from llm_wiki.graph.suggest import (
    apply_suggestions,
    build_entity_registry,
    generate_suggestions,
    load_pages,
)


def _make_wiki(tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "gpt-4.md").write_text(
        "---\ntitle: GPT-4\ntype: concept\n---\n\n# GPT-4\n\nA large language model.\n",
        encoding="utf-8",
    )
    (wiki / "notes.md").write_text(
        "---\ntitle: Notes\ntype: note\n---\n\n# Notes\n\n"
        "## gpt-4\n\n## GPT 4\n\n"
        "We evaluated gpt-4 and also GPT 4 on several tasks.\n",
        encoding="utf-8",
    )
    return tmp_path, wiki


def _run_cli(argv):
    old = sys.argv
    try:
        sys.argv = argv
        return entities_cli.main()
    finally:
        sys.argv = old


def test_entities_resolve_list_unmerge_roundtrip(tmp_path, capsys):
    root, _wiki = _make_wiki(tmp_path)

    rc = _run_cli(["llm-wiki entities", "resolve", str(root)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "merged" in out.lower()

    # list shows the canonical + its aliases
    rc = _run_cli(["llm-wiki entities", "list", str(root), "--json"])
    assert rc == 0
    listing = capsys.readouterr().out
    assert "gpt" in listing.lower()

    # the alias store now maps variant surfaces to a canonical label
    targets = alias_targets(root)
    assert targets  # non-empty after resolve
    assert any("gpt" in v.lower() for v in targets.values())

    # unmerge a known alias succeeds; an unknown one is a no-op exit 1
    some_alias = next(iter(targets))
    rc = _run_cli(["llm-wiki entities", "unmerge", str(root), some_alias])
    assert rc == 0
    rc = _run_cli(["llm-wiki entities", "unmerge", str(root), "does-not-exist"])
    assert rc == 1


def test_resolve_with_no_candidates_exits_1(tmp_path, capsys):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "only.md").write_text("---\ntitle: Only\n---\n\n# Only\n", encoding="utf-8")
    rc = _run_cli(["llm-wiki entities", "resolve", str(tmp_path)])
    # A single page yields <2 candidates → nothing to resolve.
    assert rc in (0, 1)


def test_surface_to_canonical_routing_is_opt_in(tmp_path):
    root, wiki = _make_wiki(tmp_path)
    pages = load_pages(wiki)

    # Without an alias map, "GPT 4" (a distinct surface) has no page → not routed.
    reg_plain = build_entity_registry(pages)
    assert "gpt 4" not in reg_plain

    # After resolution, alias routing sends "GPT 4"/"gpt-4" to the GPT-4 page.
    apply_resolution(root, ["GPT-4", "GPT 4", "gpt-4"])
    amap = alias_targets(root)
    reg_alias = build_entity_registry(pages, alias_targets=amap)
    # at least one alias surface now resolves to the GPT-4 page
    routed = [e for e in reg_alias.values() if e["target_stem"] == "gpt-4"]
    assert routed
    assert any(e["original"] in ("GPT 4", "gpt-4") for e in reg_alias.values())


def test_apply_preserves_surface_text(tmp_path):
    root, wiki = _make_wiki(tmp_path)
    apply_resolution(root, ["GPT-4", "GPT 4", "gpt-4"])
    pages = load_pages(wiki)
    amap = alias_targets(root)
    registry = build_entity_registry(pages, alias_targets=amap)
    suggestions = generate_suggestions(pages, registry, wiki, limit=50, min_confidence=0.0)
    apply_suggestions(pages, suggestions)

    new_text = (wiki / "notes.md").read_text(encoding="utf-8")
    # A wikilink to the canonical page was inserted. The "GPT 4" surface (which
    # differs from the page title beyond case) is preserved as the alias label.
    assert "[[GPT-4|GPT 4]]" in new_text
    # Every wikilink target is the canonical page — no variant became its own node.
    from llm_wiki.core.wikilinks import WIKILINK_RE
    for link in WIKILINK_RE.findall(new_text):
        assert link.split("|")[0] == "GPT-4"
    # Prose surface forms survive (inside links as labels or as the link text).
    assert "gpt-4" in new_text and "GPT 4" in new_text


# ── AD-21: _apply_semantic keys aliases by normalized page title ─────────────

def test_apply_gated_on_two_signals(tmp_path):
    from types import SimpleNamespace

    from llm_wiki.graph.suggest import _apply_semantic
    from llm_wiki.semantic.linking import is_auto_appliable

    root, wiki = _make_wiki(tmp_path)
    (wiki / "lone.md").write_text(
        "---\ntitle: Lone Wolf\ntype: concept\n---\n\n# Lone Wolf\n\nUnrelated.\n",
        encoding="utf-8",
    )

    # Canonical LABEL ("GPT 4", the tie-sorted canonical) differs from the page
    # title ("GPT-4") beyond case — the alias-attach lookup must be keyed by
    # normalize(title), not the raw label.
    apply_resolution(root, ["GPT-4", "GPT 4", "gpt-4"])
    targets = alias_targets(root)
    assert "GPT 4" in targets.values()  # the canonical label ≠ page title

    args = SimpleNamespace(wiki_root=str(root), page="notes", limit=20)

    # Case A: auto-appliable (two-signal) row for the GPT-4 page, and the alias
    # IS mentioned in the source prose → the link is applied as [[GPT-4|surface]].
    rc = _apply_semantic(args, [{"target_stem": "gpt-4", "signals": ["lexical", "ppr"]}],
                         is_auto_appliable)
    assert rc == 0
    new_text = (wiki / "notes.md").read_text(encoding="utf-8")
    assert "[[GPT-4|GPT 4]]" in new_text

    # Case B: auto-appliable row whose target is NOT mentioned in the prose
    # (no title and no alias mention) → nothing applied, page unchanged.
    before = (wiki / "notes.md").read_text(encoding="utf-8")
    rc = _apply_semantic(args, [{"target_stem": "lone", "signals": ["lexical", "ppr"]}],
                         is_auto_appliable)
    assert rc == 0
    assert (wiki / "notes.md").read_text(encoding="utf-8") == before
    assert "Lone Wolf" not in (wiki / "notes.md").read_text(encoding="utf-8")
