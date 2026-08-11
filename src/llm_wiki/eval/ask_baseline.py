#!/usr/bin/env python3
"""ask_baseline.py — Ask citation-precision eval runner + gate (LWM_033).

Scores ``ask``'s deterministic retrieval context (question → cited page stems)
on a committed **ask** gold set (``tests/eval/gold/ask_goldset.json``, distinct
from the search gold set) and freezes the committed baseline
(``tests/eval/baseline/ask_baseline.json``) by citation precision@k, with
gibberish negatives staying empty — fail-on-drop via
``tests/test_ask_eval.py`` (ADR-0022).

The gate scores the deterministic offline retrieval (the concept embedder +
the summary-aware rerank), NEVER the LLM call — the same contract ``--no-llm``
pins (AC#2). ``build_ask_gold_wiki`` extends the search gold wiki's four topic
lanes (ml / attn / bev / sys) with one ``type: community-summary`` page per
lane, so ask questions have a summary node to cite.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from llm_wiki.eval.metrics import mean, negative_pass, precision_at_k_padded
from llm_wiki.eval.search_baseline import ConceptEmbedder
from llm_wiki.semantic.embedder import Embedder

PRECISION_KS = (1, 3, 5)
DEFAULT_TOL = 1e-6
K = 10

# One deterministic community-summary page per topic lane. Members are page
# stems (the ask wiki's own gold pages) — ``ask`` resolves them via the page
# set either way (frontmatter ``members`` accepts stems or titles).
ASK_GOLD_SUMMARIES = {
    "community_ml": {
        "title": "Machine Learning Community",
        "members": ["neural_network", "deep_learning", "backpropagation",
                    "layers", "gradient_descent"],
        "key_entities": ["Neural Network", "Deep Learning", "Backpropagation"],
        "body": ("The machine learning community covers neural networks, deep "
                 "learning, backpropagation, layers, and gradient descent."),
    },
    "community_attn": {
        "title": "Attention Community",
        "members": ["transformer", "self_attention", "encoder",
                    "positional_encoding"],
        "key_entities": ["Transformer", "Self-Attention"],
        "body": ("The attention community covers the transformer, self-attention, "
                 "the encoder, and positional encoding."),
    },
    "community_bev": {
        "title": "Beverage Community",
        "members": ["coffee", "espresso", "latte", "caffeine"],
        "key_entities": ["Coffee", "Espresso", "Latte"],
        "body": ("The beverage community covers coffee, espresso, latte, "
                 "and caffeine."),
    },
    "community_sys": {
        "title": "Systems Community",
        "members": ["memory_management", "caching"],
        "key_entities": ["Memory Management", "Caching"],
        "body": ("The systems community covers memory management and caching "
                 "strategies."),
    },
}


class AskConceptEmbedder(ConceptEmbedder):
    """Deterministic offline embedder for the ask gold wiki.

    The base ``ConceptEmbedder`` vocab is built from ``SEARCH_GOLD_PAGES`` only;
    the ask gold wiki's community-summary bodies introduce extra tokens. Without
    them in the vocab, those tokens land in the ``unk`` bucket and SHARE a
    dimension with gibberish-query tokens — leaking false vector matches into
    the negative lane. Extending the vocab to cover every ask gold wiki token
    keeps the negative lane empty (mirrors the search gate's invariant) while
    the two-signal ranking behavior (topic one-hot + token BOW) is unchanged.
    """

    _VOCAB = sorted(
        set(ConceptEmbedder._VOCAB)
        | {
            tok
            for info in ASK_GOLD_SUMMARIES.values()
            for tok in re.findall(r"[a-z0-9]+", info["body"].lower())
        }
    )


def build_ask_gold_wiki(wiki_root, embedder: "Embedder | None" = None):
    """Deterministic ask gold wiki: the search gold pages + a community-summary
    page per topic lane, FTS5-indexed, optionally embedded.

    ``wiki_root`` is the wiki *project root* (parent of ``wiki/``). Returns
    ``wiki_root``. Reuses ``build_search_gold_wiki`` for the pages + index, then
    adds the summary pages and rebuilds the index so they are first-class,
    searchable nodes.
    """
    from llm_wiki.eval.search_baseline import build_search_gold_wiki
    from llm_wiki.search.index import index_wiki
    from llm_wiki.semantic.embed import embed_wiki

    build_search_gold_wiki(wiki_root)  # pages + FTS5 index (no vectors yet)
    w = Path(wiki_root) / "wiki"
    out = w / "communities"
    out.mkdir(exist_ok=True)
    for stem, info in ASK_GOLD_SUMMARIES.items():
        members = ", ".join(f'"{m}"' for m in info["members"])
        ke = ", ".join(f'"{e}"' for e in info["key_entities"])
        page = (
            "---\n"
            f"title: {info['title']}\n"
            "type: community-summary\n"
            "community: 0\n"
            "level: 0\n"
            f"members: [{members}]\n"
            f"key_entities: [{ke}]\n"
            "generated_by: ask-gold-wiki\n"
            "updated: 2026-08-11\n"
            "---\n\n"
            f"# {info['title']}\n\n{info['body']}\n"
        )
        (out / f"{stem}.md").write_text(page, encoding="utf-8")
    index_wiki(Path(wiki_root), rebuild=True)
    if embedder is not None:
        embed_wiki(Path(wiki_root), embedder=embedder)
    return Path(wiki_root)


def load_ask_goldset(path) -> dict:
    """Load + validate the ask gold set (asserts tune ∩ gate = ∅)."""
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items", [])
    tune = {i["question"] for i in items if i.get("split") == "tune"}
    gate = {i["question"] for i in items if i.get("split") == "gate"}
    overlap = tune & gate
    if overlap:
        raise ValueError(f"ask gold set tune∩gate must be empty; leaked: {sorted(overlap)}")
    return data


def split_items(data: dict, split: str) -> "list[dict]":
    return [i for i in data.get("items", []) if i.get("split") == split]


def run_ask_baseline(wiki_root, items, mode: str, k: int = K,
                     embedder: "Embedder | None" = None) -> dict:
    """Score one retrieval mode over gold ``items`` ([{question, relevant[],
    kind}]) on the DETERMINISTIC retrieval context (never the LLM call).

    Citations are the reranked stems from ``ask.retrieve_grounded_passages``.
    Returns ``{mode, precision_at_k:{k:v}, negative_pass_rate, n}``.
    """
    from llm_wiki.graph.ask import retrieve_grounded_passages

    prec = {kk: [] for kk in PRECISION_KS}
    neg = []
    for item in items:
        question = item["question"]
        relevant = item.get("relevant", [])
        retrieval = retrieve_grounded_passages(
            wiki_root, question, keyword=(mode == "keyword"), top_k=k,
            embedder=embedder,
        )
        citations = retrieval["citations"]
        if item.get("kind") == "negative" or not relevant:
            neg.append(negative_pass(citations))
        else:
            for kk in PRECISION_KS:
                prec[kk].append(precision_at_k_padded(citations, relevant, kk))
    return {
        "mode": mode,
        "precision_at_k": {kk: round(mean(prec[kk]), 6) for kk in PRECISION_KS},
        "negative_pass_rate": round(mean(neg), 6) if neg else 1.0,
        "n": len(items),
    }


def compute_ask_baseline(wiki_root, goldset_path, split: str = "gate",
                         k: int = K, embedder: "Embedder | None" = None) -> dict:
    """Committed-baseline artifact: deterministic hybrid citation precision@k
    on one split (default the held-out GATE split) + provenance."""
    data = load_ask_goldset(goldset_path)
    items = split_items(data, split)
    hy = run_ask_baseline(wiki_root, items, "hybrid", k=k, embedder=embedder)
    kw = run_ask_baseline(wiki_root, items, "keyword", k=k, embedder=embedder)
    embedder_name = embedder.model_id if embedder is not None else "default"
    return {
        "task": "ask-qa",
        "split": split,
        "tolerance": DEFAULT_TOL,
        "k": k,
        "hybrid": hy,
        "keyword": kw,
        "generated_by": (
            f"llm_wiki.eval.ask_baseline.compute_ask_baseline "
            f"(embedder={embedder_name}, k={k})"
        ),
        "note": (
            "Freeze of the LWM_033 ask-eval gate on the held-out GATE split: "
            "citation precision@k over the deterministic retrieval context "
            "(hybrid via the concept embedder + summary-aware rerank), never "
            "the LLM call. Hybrid (the ask default) >= keyword at every k; "
            "gibberish negatives stay empty. Fail-on-drop asserted by "
            "tests/test_ask_eval.py."
        ),
    }


def main() -> int:
    import argparse
    import json
    import tempfile

    parser = argparse.ArgumentParser(
        description="Compute the committed ask-eval baseline (LWM_033 / ADR-0029). "
                    "Citation precision@k on the deterministic retrieval path."
    )
    parser.add_argument("--goldset", default="tests/eval/gold/ask_goldset.json",
                        help="Ask gold set path")
    parser.add_argument("--split", default="gate", choices=["tune", "gate"])
    parser.add_argument("--embedder", default="concept", choices=["concept", "default"],
                        help="Embedder for the hybrid mode (default: concept — "
                             "deterministic offline proxy)")
    parser.add_argument("--wiki", default=None,
                        help="Existing wiki root to score (default: build the "
                             "synthetic ask gold wiki in a temp dir)")
    parser.add_argument("--output", default=None,
                        help="Write the baseline JSON artifact to this path")
    args = parser.parse_args()

    from llm_wiki.semantic.embedder import get_embedder

    embedder = AskConceptEmbedder() if args.embedder == "concept" else get_embedder()
    if embedder is None and args.embedder == "default":
        print("error: default embedder unavailable ([semantic] extra absent)",
              file=sys.stderr)
        return 2

    if args.wiki:
        root = Path(args.wiki)
    else:
        tmp = tempfile.TemporaryDirectory()
        root = build_ask_gold_wiki(tmp.name, embedder=embedder)

    baseline = compute_ask_baseline(root, args.goldset, split=args.split,
                                    embedder=embedder)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(json.dumps(baseline, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
