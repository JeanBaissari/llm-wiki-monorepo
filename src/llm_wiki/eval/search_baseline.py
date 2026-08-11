#!/usr/bin/env python3
"""search_baseline.py — Keyword-vs-hybrid search eval runner + gate (LWM_032).

Scores ``keyword`` and ``hybrid`` retrieval on a committed search gold set
(``query → relevant page-ids``, distinct from the link-suggestion set) and
provides the **fail-closed** promotion gate that certifies the v0.5.0 default
flip: hybrid may become the default only when, on the held-out GATE split,
``hybrid.recall ≥ keyword.recall - tol`` AND ``hybrid.precision@k ≥
keyword.precision@k - tol`` for every k, with gibberish negatives still empty.
See ADR-0020.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

from llm_wiki.eval.metrics import mean, negative_pass, precision_at_k_padded, recall_at_k
from llm_wiki.semantic.embedder import Embedder

PRECISION_KS = (1, 3, 5, 10)
RECALL_K = 10
DEFAULT_TOL = 1e-6


def _page_id(path: str) -> str:
    return Path(path).stem


def run_search_baseline(wiki_root, items, mode: str, k: int = 10, embedder=None) -> dict:
    """Score one mode over gold ``items`` ([{query, relevant[], kind}]).

    Returns ``{mode, precision_at_k:{k:v}, recall, negative_pass_rate, n}``.
    """
    from llm_wiki.search.query import hybrid_search, keyword_search

    prec = {kk: [] for kk in PRECISION_KS}
    rec = []
    neg = []
    for item in items:
        query = item["query"]
        relevant = item.get("relevant", [])
        if mode == "keyword":
            res = keyword_search(wiki_root, query, max(k, RECALL_K))
        else:
            res = hybrid_search(wiki_root, query, max(k, RECALL_K), embedder=embedder)
        predicted = []
        for r in res:
            pid = _page_id(r["path"])
            if pid not in predicted:
                predicted.append(pid)

        if item.get("kind") == "negative" or not relevant:
            neg.append(negative_pass(predicted))
        else:
            for kk in PRECISION_KS:
                # Padded precision (hits/k): the retrieval-standard form. The
                # min-normalized precision_at_k is for variable-length LINK
                # suggestion lists; comparing two retrieval modes with
                # different result counts on it is apples-to-oranges (hybrid's
                # extra semantic candidates would dilute its precision even
                # when they are on-topic). See metrics.precision_at_k_padded.
                prec[kk].append(precision_at_k_padded(predicted, relevant, kk))
            rec.append(recall_at_k(predicted, relevant, RECALL_K))

    return {
        "mode": mode,
        "precision_at_k": {kk: round(mean(prec[kk]), 6) for kk in PRECISION_KS},
        "recall": round(mean(rec), 6),
        "negative_pass_rate": round(mean(neg), 6) if neg else 1.0,
        "n": len(items),
    }


def search_eval_gate(keyword: dict, hybrid: dict, tol: float = DEFAULT_TOL) -> "tuple[bool, dict]":
    """Fail-closed promotion gate. Returns (allow_flip, report)."""
    recall_ok = hybrid["recall"] >= keyword["recall"] - tol
    prec_ok = all(
        hybrid["precision_at_k"][kk] >= keyword["precision_at_k"][kk] - tol
        for kk in PRECISION_KS
    )
    neg_ok = hybrid["negative_pass_rate"] >= 1.0 - tol
    allow = recall_ok and prec_ok and neg_ok
    report = {
        "recall_parity": recall_ok,
        "precision_no_regress": prec_ok,
        "negatives_empty": neg_ok,
        "allow_flip": allow,
        "keyword": keyword,
        "hybrid": hybrid,
        "reason": "hybrid >= keyword on GATE" if allow
                  else "fail-closed: hybrid regresses keyword on GATE",
    }
    return allow, report


def load_search_goldset(path) -> dict:
    """Load + validate the search gold set (asserts tune ∩ gate = ∅)."""
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items", [])
    tune = {i["query"] for i in items if i.get("split") == "tune"}
    gate = {i["query"] for i in items if i.get("split") == "gate"}
    overlap = tune & gate
    if overlap:
        raise ValueError(f"search gold set tune∩gate must be empty; leaked: {sorted(overlap)}")
    return data


def split_items(data: dict, split: str) -> "list[dict]":
    return [i for i in data.get("items", []) if i.get("split") == split]


# ── Deterministic concept embedder (offline proxy for the [semantic] layer) ──

# Topic lanes (BKD-002 growth, 2026-08-11): every page in SEARCH_GOLD_PAGES
# carries at least one topic keyword so NO page embeds to "none" — none-topic
# queries (no-answer/gibberish negatives) then match nothing semantically and
# must return empty under hybrid, keeping the negative lane deterministic.
_TOPICS = {
    "ml": ["neural network", "deep learning", "backpropagation", "layers", "gradient"],
    "attn": ["attention", "transformer", "sequences", "encoding"],
    "bev": ["coffee", "brewed", "beverage", "roasted", "beans", "espresso", "latte", "milk", "caffeine"],
    "sys": ["memory", "caching", "management"],
}
_DIM = {"ml": 0, "attn": 1, "bev": 2, "sys": 3, "none": 4}


def _topic_of(text: str) -> str:
    t = text.lower()
    best, score = "none", 0
    for topic, kws in _TOPICS.items():
        hits = sum(1 for kw in kws if kw in t)
        if hits > score:
            best, score = topic, hits
    return best


# The synthetic gold wiki the search gold set is labelled against. Each page is
# a single topical sentence so keyword and concept-hybrid behavior is fully
# deterministic (LWM_032 fixture lane). Grown by BKD-002 from 4 → 15 pages
# across four topic lanes (ml / attn / bev / sys) so the gold set can carry
# exact-token, paraphrase, multi-relevant and no-answer query lanes.
SEARCH_GOLD_PAGES = {
    # ml lane
    "neural_network.md": "A neural network learns weights via backpropagation.",
    "deep_learning.md": "Deep learning stacks many neural network layers.",
    "backpropagation.md": "A neural network learns weights via backpropagation.",
    "layers.md": "Neural network layers learn hierarchical features.",
    "gradient_descent.md": "Gradient descent minimizes loss via backpropagation.",
    # attn lane
    "transformer.md": "The transformer uses attention over sequences.",
    "self_attention.md": "Self-attention lets sequences relate tokens directly.",
    "encoder.md": "The transformer encoder processes sequences.",
    "positional_encoding.md": "Positional encoding marks token order in transformer sequences.",
    # bev lane
    "coffee.md": "Coffee is a brewed beverage from roasted beans.",
    "espresso.md": "Espresso is a strong brewed beverage made under pressure.",
    "latte.md": "A latte is espresso with steamed milk.",
    "caffeine.md": "Caffeine is a stimulant found in coffee.",
    # sys lane
    "memory_management.md": "Memory management allocates and reclaims application memory.",
    "caching.md": "Caching strategies store frequently accessed data.",
}

class ConceptEmbedder(Embedder):
    """Deterministic offline proxy for the [semantic] layer.

    Two-signal embedding, mirroring how real dense models behave:

    * **topic one-hot** (ml|attn|bev|sys|none) — semantic breadth: a paraphrase
      query ("deep learning technique") matches the ml pages keyword misses.
    * **token bag-of-words** over the gold wiki's vocabulary — lexical
      fidelity: an exact-token page ("transformer") ranks above same-topic
      pages ("self_attention") because their vectors share tokens.

    The two terms make the proxy ranking-faithful: hybrid surfaces paraphrase
    matches (topic) without diluting top-k precision on exact-token queries
    (tokens) — the behavior a real embedder exhibits and that the committed
    gate must certify offline (ADR-0020 / LWM_032).
    """

    model_id = "concept"
    revision = "r"
    normalization = "l2"
    quantization = "float32"

    # Fixed vocabulary: sorted tokens across the gold wiki pages + query lane
    # (deterministic; unknown tokens fall into the unk bucket).
    _VOCAB: "list[str]" = sorted(
        {
            tok
            for body in SEARCH_GOLD_PAGES.values()
            for tok in re.findall(r"[a-z0-9]+", body.lower())
        }
    ) + ["unk"]

    TOPIC_SCALE = 2.0  # topic dominates for paraphrase recall...
    TOKEN_SCALE = 1.0  # ...tokens discriminate within a topic

    @classmethod
    def is_available(cls) -> bool:
        return True

    @property
    def dimension(self) -> int:
        return 5 + len(self._VOCAB)

    def embed(self, texts):
        # L2-normalize the output, honoring the Embedder contract (the real
        # Model2VecEmbedder normalizes in embed() too): the vector store stores
        # vectors as-is and cosine similarity is a plain dot product over
        # normalized vectors. Raw vectors would let longer pages dominate the
        # ranking regardless of topical fit.
        out = []
        for t in texts:
            topic = _topic_of(t)
            v = [0.0] * (5 + len(self._VOCAB))
            v[_DIM[topic]] = self.TOPIC_SCALE
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                try:
                    idx = self._VOCAB.index(tok)
                except ValueError:
                    idx = self._VOCAB.index("unk")
                v[5 + idx] += self.TOKEN_SCALE
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out




def build_search_gold_wiki(wiki_root, embedder: "Embedder | None" = None):
    """Build the deterministic gold wiki (pages + FTS5 index + optional vectors).

    ``wiki_root`` is the wiki *project root* (parent of the ``wiki/`` dir), as
    consumed by ``run_search_baseline``. Returns ``wiki_root``.
    """
    from llm_wiki.search.index import index_wiki
    from llm_wiki.semantic.embed import embed_wiki

    w = Path(wiki_root) / "wiki"
    w.mkdir(parents=True, exist_ok=True)
    for nm, body in SEARCH_GOLD_PAGES.items():
        (w / nm).write_text(
            f"---\ntitle: {nm[:-3]}\ntype: concept\n---\n\n# {nm[:-3]}\n\n{body}\n",
            encoding="utf-8",
        )
    index_wiki(Path(wiki_root), rebuild=True)
    if embedder is not None:
        embed_wiki(Path(wiki_root), embedder=embedder)
    return Path(wiki_root)


def compute_search_baseline(
    wiki_root,
    goldset_path,
    split: str = "gate",
    k: int = 10,
    embedder: "Embedder | None" = None,
    tol: float = DEFAULT_TOL,
) -> dict:
    """Compute the committed search baseline: keyword + hybrid on one split.

    Returns the baseline artifact dict (both modes, the fail-closed gate
    verdict, and provenance). This is what ``tests/eval/baseline/
    search_eval_baseline.json`` and ``tests/test_search_baseline_reproducible``
    are derived from.
    """
    data = load_search_goldset(goldset_path)
    items = split_items(data, split)
    keyword = run_search_baseline(wiki_root, items, "keyword", k=k)
    hybrid = run_search_baseline(wiki_root, items, "hybrid", k=k, embedder=embedder)
    allow, _report = search_eval_gate(keyword, hybrid, tol=tol)
    embedder_name = embedder.model_id if embedder is not None else "default"
    return {
        "task": "search-retrieval",
        "split": split,
        "tolerance": tol,
        "keyword": keyword,
        "hybrid": hybrid,
        "allow_hybrid_default": allow,
        "generated_by": (
            f"llm_wiki.eval.search_baseline.compute_search_baseline "
            f"(embedder={embedder_name}, k={k})"
        ),
        "note": (
            "Freeze of the LWM_032 search-eval gate on the held-out GATE split. "
            "Reproduce offline with the deterministic concept embedder; CI "
            "re-certifies with the real [semantic] embedder (model2vec)."
        ),
    }


def main() -> int:
    import argparse
    import json
    import tempfile

    parser = argparse.ArgumentParser(
        description="Compute the committed search-eval baseline (LWM_032 / ADR-0020). "
                    "Keyword vs hybrid on the frozen GATE split."
    )
    parser.add_argument("--goldset", default="tests/eval/gold/search_goldset.json",
                        help="Search gold set path (default: tests/eval/gold/search_goldset.json)")
    parser.add_argument("--split", default="gate", choices=["tune", "gate"])
    parser.add_argument("--embedder", default="concept", choices=["concept", "default"],
                        help="Embedder for the hybrid mode (default: concept — deterministic offline proxy)")
    parser.add_argument("--wiki", default=None,
                        help="Existing wiki root to score (default: build the synthetic gold wiki in a temp dir)")
    parser.add_argument("--output", default=None,
                        help="Write the baseline JSON artifact to this path")
    args = parser.parse_args()

    from llm_wiki.semantic.embedder import get_embedder

    embedder = ConceptEmbedder() if args.embedder == "concept" else get_embedder()
    if embedder is None and args.embedder == "default":
        print("error: default embedder unavailable ([semantic] extra absent)", file=sys.stderr)
        return 2

    if args.wiki:
        root = Path(args.wiki)
    else:
        tmp = tempfile.TemporaryDirectory()
        root = build_search_gold_wiki(tmp.name, embedder=embedder)

    baseline = compute_search_baseline(
        root, args.goldset, split=args.split, embedder=embedder
    )

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
