#!/usr/bin/env python3
"""cli.py — ``llm-wiki eval`` surface for the link-suggestion baseline.

Runs the current lexical link-suggester over a wiki, scores it against a gold
set (default: the committed seed), and prints an absolute ``EvalReport``. With
``--baseline-out`` it writes the report JSON — the committed baseline artifact
the eval-regression gate (LWM_023) consumes.

Deterministic and offline: no network, no LLM. Exit 0 on any successful run so
a low-but-non-regressing absolute score is surfaced, not hidden behind a
non-zero exit (ADR-0022).

Usage:
    llm-wiki eval <wiki_root>
    llm-wiki eval <wiki_root> --split gate --k 5 --json
    llm-wiki eval <wiki_root> --baseline-out tests/eval/baseline/eval_baseline.json

Exit codes:
    0 — eval ran (any absolute score, including low ones)
    2 — usage error (bad arguments / gold set missing or malformed)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from llm_wiki.eval.baseline import run_link_suggest_baseline
from llm_wiki.eval.goldset import GoldSetError, load_goldset
from llm_wiki.eval.harness import EvalReport

# Committed seed gold set, resolved relative to the repo root
# (src/llm_wiki/eval/cli.py -> parents[3] == repo root).
DEFAULT_GOLDSET = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "eval"
    / "fixtures"
    / "goldset_seed.json"
)


def _format_human(report: EvalReport, wiki_root: str, goldset_path: str) -> str:
    d = report.to_dict()
    return "\n".join(
        [
            f"Link-suggestion eval: {wiki_root}",
            f"  Gold set:   {goldset_path}",
            f"  Split:      {d['split'] if d['split'] is not None else 'all'}",
            f"  k:          {d['k']}",
            "",
            f"  Positives:  {d['n_positive']}",
            f"  Negatives:  {d['n_negative']}",
            "",
            f"  precision@{d['k']}:       {d['precision_at_k']}",
            f"  recall@{d['k']}:          {d['recall_at_k']}",
            f"  F1:                {d['f1']}",
            f"  negative_pass_rate: {d['negative_pass_rate']}",
        ]
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="llm-wiki eval",
        description="Evaluate the lexical link-suggester against a gold set.",
    )
    parser.add_argument("wiki_root", help="Path to the wiki root directory")
    parser.add_argument(
        "--goldset",
        default=str(DEFAULT_GOLDSET),
        help="Path to the gold-set JSON (default: committed seed)",
    )
    parser.add_argument(
        "--split",
        choices=["gate", "tune", "all"],
        default="gate",
        help="Gold-set split to score (default: gate — the held-out split)",
    )
    parser.add_argument(
        "--k", type=int, default=5, help="precision@k / recall@k cutoff (default: 5)"
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit the report as JSON to stdout"
    )
    parser.add_argument(
        "--baseline-out",
        default=None,
        help="Write the report JSON to this path (the committed baseline artifact)",
    )
    args = parser.parse_args(argv)

    try:
        goldset = load_goldset(args.goldset)
    except FileNotFoundError:
        print(f"Error: gold set not found: {args.goldset}", file=sys.stderr)
        return 2
    except (GoldSetError, ValueError) as exc:
        print(f"Error: invalid gold set: {exc}", file=sys.stderr)
        return 2

    split = None if args.split == "all" else args.split
    report = run_link_suggest_baseline(args.wiki_root, goldset, k=args.k, split=split)
    report_json = json.dumps(report.to_dict(), indent=2, sort_keys=True)

    if args.baseline_out:
        out_path = Path(args.baseline_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_json + "\n", encoding="utf-8")

    if args.json:
        print(report_json)
    else:
        print(_format_human(report, args.wiki_root, args.goldset))

    return 0


if __name__ == "__main__":
    sys.exit(main())
