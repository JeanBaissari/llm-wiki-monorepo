#!/usr/bin/env python3
"""baseline.py — Score the CURRENT lexical link-suggester against a gold set.

The eval harness is retrieval-framed (``query -> ranked item ids``). This module
adapts the lexical link-suggester (``llm_wiki.graph.suggest``) onto that frame so
the same ``evaluate`` path scores today's lexical system and tomorrow's
hybrid/semantic one without change (LWM_022 / ADR-0022):

    query    -> source page stem
    relevant -> correct target stems for that source (gold labels)
    predicted-> the suggester's target stems for that source, ranked by score

It produces the committed baseline the eval-regression gate (LWM_023) diffs
future changes against.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

from llm_wiki.core.layout import discover_layout
from llm_wiki.eval.goldset import GoldSet, Split
from llm_wiki.eval.harness import EvalReport, evaluate
from llm_wiki.graph.suggest import (
    build_entity_registry,
    generate_suggestions,
    load_pages,
)

# Effectively unbounded for wikis of any realistic size; min_confidence=0.0 so
# the ranking (not a display threshold) decides what counts as retrieved.
_UNBOUNDED_LIMIT = 1_000_000


def predictions_for(wiki_root: str | Path) -> dict[str, list[str]]:
    """Return ``{source_stem: [target_stems ranked by score desc]}``.

    Runs the lexical suggester over every page in the discovered wiki and groups
    its suggestions by source. Ties on score break on ``target_stem`` so the
    ranking is deterministic regardless of hash seeding.
    """
    layout = discover_layout(wiki_root)
    wiki_dir = Path(layout.pages_dir)
    if not wiki_dir.is_dir():
        return {}

    skip_files = frozenset(f"{stem}.md" for stem in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)
    if not pages:
        return {}

    registry = build_entity_registry(pages)
    if not registry:
        return {}

    suggestions = generate_suggestions(
        pages, registry, wiki_dir, limit=_UNBOUNDED_LIMIT, min_confidence=0.0
    )

    # A target can be reached via more than one entity alias (title + a heading
    # or slug that equals its stem), yielding duplicate suggestions for the same
    # target. Keep only the highest-scored occurrence per (source, target) so the
    # ranked list has distinct targets — otherwise duplicates inflate precision
    # and crowd real relevant items out of the top-k, distorting the baseline.
    best: dict[str, dict[str, float]] = defaultdict(dict)
    for s in suggestions:
        src, tgt, score = s["source_stem"], s["target_stem"], s["score"]
        if tgt not in best[src] or score > best[src][tgt]:
            best[src][tgt] = score

    predictions: dict[str, list[str]] = {}
    for source_stem, scored in best.items():
        ranked = sorted(scored.items(), key=lambda t: (-t[1], t[0]))
        predictions[source_stem] = [target for target, _ in ranked]
    return predictions


def run_link_suggest_baseline(
    wiki_root: str | Path,
    goldset: GoldSet,
    k: int = 5,
    split: Optional[Split] = "gate",
) -> EvalReport:
    """Score the lexical suggester over ``wiki_root`` against ``goldset``.

    ``split`` defaults to ``"gate"`` (the held-out, never-tuned split). Pass
    ``None`` to score every item regardless of split.
    """
    predictions = predictions_for(wiki_root)
    return evaluate(predictions, goldset, k=k, split=split)
