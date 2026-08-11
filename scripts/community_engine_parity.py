#!/usr/bin/env python3
"""community_engine_parity.py — Leiden vs Louvain parity gate CLI (BKD-003).

Runs the committed fixture gate set through both engines and writes
``reports/community-engine-parity.json`` with the flip verdict. See
``llm_wiki.eval.community_parity`` for the policy.

Exit codes: 0 = measured and allowed, or skipped (no [leiden] extra);
1 = measured and flip NOT allowed (fail-closed — the parity gate is red);
2 = usage error.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "graphs"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "community-engine-parity.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Leiden vs Louvain community-engine parity gate (ADR-0025 / BKD-003)."
    )
    parser.add_argument("--fixtures", default=str(FIXTURES_DIR),
                        help=f"Graph fixture dir (default: {FIXTURES_DIR})")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help="Report artifact path")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--margin-nmi", type=float, default=0.95)
    parser.add_argument("--json", action="store_true", help="Print the report to stdout")
    args = parser.parse_args()

    from llm_wiki.eval.community_parity import compute_parity

    report = compute_parity(
        Path(args.fixtures), seed=args.seed, nmi_margin=args.margin_nmi
    )

    if report["status"] == "skipped":
        print(json.dumps(report, indent=2) if args.json else report["reason"],
              file=sys.stderr)
        return 0

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        g = report["gate"]
        print(f"Leiden modularity {g['modularity_non_degradation']['leiden']} vs "
              f"Louvain {g['modularity_non_degradation']['louvain']} "
              f"-> {'PASS' if g['modularity_non_degradation']['pass'] else 'FAIL'}")
        print(f"NMI agreement (structured): "
              f"{g['nmi_agreement_structured']['mean_nmi']} "
              f"(margin {g['nmi_agreement_structured']['margin']}) "
              f"-> {'PASS' if g['nmi_agreement_structured']['pass'] else 'FAIL'}")
        print(f"flip_allowed: {report['flip_allowed']} "
              f"({'' if report['flip_allowed'] else 'NOT '}allowed — ADR-0025 "
              f"flip decision is a separate evidence-linked change)")
        print(f"report: {out}")

    return 0 if report["flip_allowed"] else 1


if __name__ == "__main__":
    sys.exit(main())
