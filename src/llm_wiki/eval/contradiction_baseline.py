#!/usr/bin/env python3
"""contradiction_baseline.py — Contradiction + confidence eval runner + gates.

Scores the LWM_034 deterministic detector (and the confidence scorer) on a
committed **contradiction** gold set (``tests/eval/gold/contradiction_goldset.
json``) and a **confidence** gold set (``tests/eval/gold/confidence_goldset.
json``) over one deterministic gold wiki, freezing the committed baselines
(``tests/eval/baseline/contradiction_baseline.json`` + ``confidence_baseline.
json``):

* **contradiction gate** — recall over the gold positive pairs and precision
  over the gold negative pairs; every detected pair must either match a gold
  positive (true positive) or be absent (the gold negatives encode the
  near-miss families the detector must NOT flag: equal values after unit
  normalization, same-subject consistency, different subjects).
* **confidence gate** — accuracy of the deterministic scorer's
  ``high|medium|low`` labels against the gold labels, plus the hard
  "no evidence -> low, never high" property.

Both are fail-on-drop via ``tests/test_contradiction_eval.py`` /
``tests/test_confidence_eval.py`` (ADR-0022), tune/gate splits disjoint.
Mirrors the ask/search baseline module structure (``ask_baseline.py``,
``search_baseline.py``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_TOL = 1e-6

# ══════════════════════════════════════════════════════════════════════════
# Deterministic gold wiki — LWM_034 fixture lane
# ══════════════════════════════════════════════════════════════════════════
#
# Pages are tiny single-claim pages so extraction + detection are fully
# deterministic. The subject of every prose claim grounds to a page title
# (the LWM_025 entity layer). Raw source files referenced by the confidence
# pages are materialized so the citation-support signal resolves.
#
# Contradiction positives (must be detected):
#   (server-a, server-b)   numeric value conflict        "has 3.2 MB" vs "has 4.0 MB"
#   (apollo-a, apollo-b)   polarity conflict             "is" vs "is not"
#   (flag-a, flag-b)       mutually exclusive category   "enabled" vs "disabled"
#   (latency-a, latency-b) numeric value conflict        "500 ms" vs "2 s"
#
# Contradiction negatives (must NOT be detected):
#   (size-a, size-b)       "3.2 MB" vs "3.2 MiB"  — equal after normalization
#   (dup-a, dup-b)         "1.0" vs "1.0"         — consistent, not a conflict
#   (diffsub-a, diffsub-b) different subjects
#   (solo)                 a single claim with no partner

def _page(title: str, body: str, sources=None, updated: str = "2026-07-15",
          extra_fm: str = "") -> str:
    src = ", ".join(f'"{s}"' for s in (sources or []))
    fm = (
        "---\n"
        f"title: {title}\n"
        "type: concept\n"
        f"sources: [{src}]\n"
        f"updated: {updated}\n"
        "created: 2026-01-15\n"
        "tags: [fixture]\n"
        f"{extra_fm}"
        "---\n\n"
    )
    return fm + body + "\n"


_CONTRA_GOLD_PAGES = {
    # — subject holders (entities the prose claims ground to) —
    "cache-subject.md": _page("Server Cache", "# Server Cache\n\nServer Cache is the shared in-memory layer."),
    "apollo-subject.md": _page("Apollo 11", "# Apollo 11\n\nApollo 11 was a crewed lunar mission."),
    "flag-subject.md": _page("Feature Flag", "# Feature Flag\n\nFeature Flag is a configuration switch."),
    "latency-subject.md": _page("Latency Budget", "# Latency Budget\n\nLatency Budget is a service objective."),
    "size-subject.md": _page("Cache Size", "# Cache Size\n\nCache Size is a deployment attribute."),
    "version-subject.md": _page("Version Number", "# Version Number\n\nVersion Number is a release identifier."),
    # — contradiction positives —
    "server-a.md": _page("Server A", "# Server A\n\nServer Cache has 3.2 MB of cache."),
    "server-b.md": _page("Server B", "# Server B\n\nServer Cache has 4.0 MB of cache."),
    "apollo-a.md": _page("Apollo Timeline", "# Apollo Timeline\n\nApollo 11 is the first crewed mission to land on the Moon."),
    "apollo-b.md": _page("Apollo Record", "# Apollo Record\n\nApollo 11 is not the first crewed mission to land on the Moon."),
    "flag-a.md": _page("Release Notes", "# Release Notes\n\nFeature Flag is enabled."),
    "flag-b.md": _page("Operations Log", "# Operations Log\n\nFeature Flag is disabled."),
    "latency-a.md": _page("Load Test", "# Load Test\n\nLatency Budget is 500 ms."),
    "latency-b.md": _page("SLO Document", "# SLO Document\n\nLatency Budget is 2 s."),
    # — contradiction negatives —
    "size-a.md": _page("Deployment A", "# Deployment A\n\nCache Size is 3.2 MB."),
    "size-b.md": _page("Deployment B", "# Deployment B\n\nCache Size is 3.2 MiB."),
    "dup-a.md": _page("Version Note A", "# Version Note A\n\nVersion Number is 1.0."),
    "dup-b.md": _page("Version Note B", "# Version Note B\n\nVersion Number is 1.0."),
    "diffsub-a.md": _page("Alpha System", "# Alpha System\n\nAlpha System is a database."),
    "diffsub-b.md": _page("Beta System", "# Beta System\n\nBeta System is a database."),
    "solo.md": _page("Standalone Fact", "# Standalone Fact\n\nStandalone Fact is a unique statement."),
    # — confidence gold pages (no contradiction partners) —
    "well-evidenced.md": _page(
        "Well Evidenced", "# Well Evidenced\n\nWell Evidenced is thoroughly documented.",
        sources=["wellsrc-a", "wellsrc-b", "wellsrc-c"], updated="2026-08-01",
    ),
    "moderately-evidenced.md": _page(
        "Moderately Evidenced", "# Moderately Evidenced\n\nModerately Evidenced is partially documented.",
        sources=["medsrc-a", "medsrc-missing"], updated="2026-05-01",
    ),
    "thinly-evidenced.md": _page(
        "Thinly Evidenced", "# Thinly Evidenced\n\nThinly Evidenced is barely documented.",
        sources=["thinsrc-missing"], updated="2025-06-01",
    ),
    "no-evidence.md": (
        "---\ntitle: No Evidence Page\ntype: concept\n"
        "created: 2026-01-15\ntags: [fixture]\n---\n\n"
        "# No Evidence Page\n\nNo Evidence Page is an unsupported assertion.\n"
    ),
    "well-evidenced-2.md": _page(
        "Well Evidenced II", "# Well Evidenced II\n\nWell Evidenced II is thoroughly documented.",
        sources=["wellsrc-a", "wellsrc-b", "wellsrc-c"], updated="2026-08-01",
    ),
    "moderately-evidenced-2.md": _page(
        "Moderately Evidenced II", "# Moderately Evidenced II\n\nModerately Evidenced II is partially documented.",
        sources=["medsrc-a", "medsrc-missing"], updated="2026-05-01",
    ),
    "thinly-evidenced-2.md": _page(
        "Thinly Evidenced II", "# Thinly Evidenced II\n\nThinly Evidenced II is barely documented.",
        sources=["thinsrc-missing"], updated="2025-06-01",
    ),
}

# Raw source files the confidence pages reference (deterministic resolution).
_CONTRA_RAW_SOURCES = {
    "raw/sources/wellsrc-a.md": "# Well source A\n\nContent for well-evidenced pages.\n",
    "raw/sources/wellsrc-b.md": "# Well source B\n\nContent for well-evidenced pages.\n",
    "raw/sources/wellsrc-c.md": "# Well source C\n\nContent for well-evidenced pages.\n",
    "raw/sources/medsrc-a.md": "# Medium source A\n\nContent for moderately-evidenced pages.\n",
    "raw/sources/server-manual-a.md": "# Server manual A\n\nServer Cache capacity documentation.\n",
    "raw/sources/server-manual-b.md": "# Server manual B\n\nServer Cache capacity documentation.\n",
}


def build_contradiction_gold_wiki(wiki_root) -> Path:
    """Build the deterministic LWM_034 gold wiki under ``wiki_root``.

    ``wiki_root`` is the wiki *project root* (parent of ``wiki/``). Returns
    ``wiki_root``. Pure file writes — no FTS index, no vectors (the detector
    and scorer are lexical and deterministic).
    """
    root = Path(wiki_root)
    w = root / "wiki"
    w.mkdir(parents=True, exist_ok=True)
    for nm, content in _CONTRA_GOLD_PAGES.items():
        (w / nm).write_text(content, encoding="utf-8")
    for rel, content in _CONTRA_RAW_SOURCES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return root


# ══════════════════════════════════════════════════════════════════════════
# Gold-set loaders
# ══════════════════════════════════════════════════════════════════════════


def load_contradiction_goldset(path) -> dict:
    """Load + validate the contradiction gold set (tune ∩ gate = ∅ asserted)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items", [])
    tune = {_pair_key(i) for i in items if i.get("split") == "tune"}
    gate = {_pair_key(i) for i in items if i.get("split") == "gate"}
    overlap = tune & gate
    if overlap:
        raise ValueError(f"contradiction gold set tune∩gate must be empty; leaked: {sorted(overlap)}")
    return data


def load_confidence_goldset(path) -> dict:
    """Load + validate the confidence gold set (tune ∩ gate = ∅ asserted)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items", [])
    tune = {i["page"] for i in items if i.get("split") == "tune"}
    gate = {i["page"] for i in items if i.get("split") == "gate"}
    overlap = tune & gate
    if overlap:
        raise ValueError(f"confidence gold set tune∩gate must be empty; leaked: {sorted(overlap)}")
    return data


def split_items(data: dict, split: str) -> "list[dict]":
    return [i for i in data.get("items", []) if i.get("split") == split]


def _claim_sig(claim: dict) -> tuple:
    return (claim.get("page"), claim.get("subject"), claim.get("predicate"),
            claim.get("object"), claim.get("polarity"))


def _pair_key(item: dict) -> str:
    pair = item.get("pair", [])
    sigs = sorted(_claim_sig(c) for c in pair)
    return " | ".join(repr(s) for s in sigs)


def _detected_pair_matches(detection: dict, item: dict) -> bool:
    """A detection matches a gold pair when its two claim signatures equal the
    gold pair's (either order)."""
    gold_sigs = {_claim_sig(c) for c in item.get("pair", [])}
    det_sigs = {_claim_sig(detection["claim_a"]), _claim_sig(detection["claim_b"])}
    return det_sigs == gold_sigs


# ══════════════════════════════════════════════════════════════════════════
# Runners
# ══════════════════════════════════════════════════════════════════════════


def run_contradiction_baseline(wiki_root, all_items) -> dict:
    """Score the deterministic detector over a gold ``all_items`` list.

    ``all_items`` must carry BOTH splits (every detection on the gold wiki is
    labeled, so precision is well-defined — the detector is global, unlike
    query-level search/ask). Returns full-set precision/recall plus the
    held-out GATE-split metrics (``gate_precision``/``gate_recall``) that the
    fail-on-drop test asserts. A detection matching a gold negative (or no
    item at all) is a false positive.
    """
    from llm_wiki.quality.contradictions import _analyze

    _layout, _pages, _claims, detections = _analyze(wiki_root)

    positives = [i for i in all_items if i.get("expected", True)]
    negatives = [i for i in all_items if not i.get("expected", True)]
    gate_positives = [p for p in positives if p.get("split") == "gate"]
    gate_negatives = [n for n in negatives if n.get("split") == "gate"]

    tp = 0
    for det in detections:
        if any(_detected_pair_matches(det, p) for p in positives):
            tp += 1
    fp = len(detections) - tp
    fn = len(positives) - tp

    gate_tp = sum(
        1 for d in detections if any(_detected_pair_matches(d, p) for p in gate_positives)
    )
    gate_fp = sum(
        1 for d in detections if any(_detected_pair_matches(d, n) for n in gate_negatives)
    )
    gate_fn = len(gate_positives) - gate_tp

    neg_leaks = sum(
        1 for d in detections if any(_detected_pair_matches(d, n) for n in negatives)
    )
    return {
        "precision": round(tp / len(detections), 6) if detections else 1.0,
        "recall": round(tp / len(positives), 6) if positives else 1.0,
        "gate_precision": round(gate_tp / (gate_tp + gate_fp), 6) if (gate_tp + gate_fp) else 1.0,
        "gate_recall": round(gate_tp / len(gate_positives), 6) if gate_positives else 1.0,
        "n_positive": len(positives),
        "n_negative": len(negatives),
        "n_detected": len(detections),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "gate_n_positive": len(gate_positives),
        "gate_n_negative": len(gate_negatives),
        "gate_true_positives": gate_tp,
        "gate_false_positives": gate_fp,
        "gate_false_negatives": gate_fn,
        "negative_pass_rate": round(1.0 - neg_leaks / len(negatives), 6) if negatives else 1.0,
    }


def run_confidence_baseline(wiki_root, items) -> dict:
    """Score the deterministic confidence scorer over gold ``items``.

    Accuracy = fraction of gold pages whose predicted label equals the gold
    label. The "no evidence -> low" property is additionally asserted by
    tests; here it is reported per-page.
    """
    from llm_wiki.quality.contradictions import score_confidence

    scores = score_confidence(wiki_root)
    correct = 0
    per_page = {}
    for item in items:
        page = item["page"]
        gold = item["gold"]
        res = scores.get(page, {})
        pred = res.get("label")
        ok = pred == gold
        correct += 1 if ok else 0
        per_page[page] = {"gold": gold, "predicted": pred, "ok": ok,
                          "evidence_score": res.get("evidence_score"),
                          "confidence_source": res.get("confidence_source")}
    return {
        "accuracy": round(correct / len(items), 6) if items else 1.0,
        "n": len(items),
        "per_page": per_page,
    }


def compute_contradiction_baseline(wiki_root, goldset_path, split: str = "gate") -> dict:
    """Committed-baseline artifact for the contradiction gate (ADR-0022)."""
    data = load_contradiction_goldset(goldset_path)
    items = data["items"]  # every detection on the gold wiki is labeled
    result = run_contradiction_baseline(wiki_root, items)
    return {
        "task": "contradiction-detection",
        "split": split,
        "tolerance": DEFAULT_TOL,
        **result,
        "generated_by": "llm_wiki.eval.contradiction_baseline.compute_contradiction_baseline",
        "note": (
            "Freeze of the LWM_034 contradiction gate: deterministic detector "
            "precision/recall over the gold wiki (all detections labeled), with "
            "the held-out GATE split reported as gate_precision/gate_recall "
            "and fail-on-drop asserted by tests/test_contradiction_eval.py. "
            "Gold negatives encode near-miss families (unit-normalized "
            "equality, consistency, distinct subjects) that must never be "
            "flagged."
        ),
    }


def compute_confidence_baseline(wiki_root, goldset_path, split: str = "gate") -> dict:
    """Committed-baseline artifact for the confidence gate."""
    data = load_confidence_goldset(goldset_path)
    items = split_items(data, split)
    result = run_confidence_baseline(wiki_root, items)
    return {
        "task": "confidence-scoring",
        "split": split,
        "tolerance": DEFAULT_TOL,
        **result,
        "generated_by": "llm_wiki.eval.contradiction_baseline.compute_confidence_baseline",
        "note": (
            "Freeze of the LWM_034 confidence gate on the held-out GATE split: "
            "deterministic scorer accuracy against gold labels. Pages without "
            "sources/updated must score low (never high); author-marked pages "
            "preserve their explicit confidence (confidence_source: author)."
        ),
    }


# ── CLI ────────────────────────────────────────────────────────────────────


def main() -> int:
    import argparse
    import tempfile

    parser = argparse.ArgumentParser(
        description="Compute the committed LWM_034 contradiction + confidence "
                    "eval baselines (fail-on-drop, ADR-0022)."
    )
    parser.add_argument("--goldset", default=None,
                        help="Path to a gold set JSON (auto-detected by task)")
    parser.add_argument("--task", choices=["contradiction", "confidence", "both"],
                        default="both")
    parser.add_argument("--split", default="gate", choices=["tune", "gate"])
    parser.add_argument("--wiki", default=None,
                        help="Existing wiki root to score (default: build the "
                             "synthetic gold wiki in a temp dir)")
    parser.add_argument("--output", default=None,
                        help="Write the baseline JSON artifact to this path")
    args = parser.parse_args()

    if args.wiki:
        root = Path(args.wiki)
    else:
        tmp = tempfile.TemporaryDirectory()
        root = build_contradiction_gold_wiki(tmp.name)

    out = {}
    if args.task in ("contradiction", "both"):
        gs = args.goldset or "tests/eval/gold/contradiction_goldset.json"
        out["contradiction"] = compute_contradiction_baseline(root, gs, split=args.split)
    if args.task in ("confidence", "both"):
        gs = args.goldset or "tests/eval/gold/confidence_goldset.json"
        out["confidence"] = compute_confidence_baseline(root, gs, split=args.split)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}")
    else:
        print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
