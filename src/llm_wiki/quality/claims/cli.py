"""CLI commands for claims health and diff."""
import argparse
import sys

from llm_wiki.quality.claims.storage import ClaimsManager, has_sidecar


def cmd_health(wiki_root: str) -> int:
    if not has_sidecar(wiki_root):
        print("No claim sidecar found. This wiki has no claim tracking enabled.")
        return 0

    mgr = ClaimsManager(wiki_root)
    report = mgr.health_report()
    print("=== Claim Health Report ===")
    print(f"  Total claims:         {report['total_claims']}")
    print(f"  Total events:         {report['total_events']}")
    print(f"  Total contradictions: {report['total_contradictions']}")
    print(f"  Open contradictions:  {report['open_contradictions']}")
    print(f"  Stale claims:         {report['stale_claims']}")
    print(f"  Pages with claims:    {report['pages_with_claims']}")
    print(f"  Active claims:        {report['active_claims']}")
    print(f"  Status breakdown:     {report['status_breakdown']}")
    print(f"  Severity breakdown:   {report['severity_breakdown']}")

    if report["open_contradictions"] > 0:
        print("\n⚠  Open contradictions detected!")
        for c in mgr.get_open_contradictions():
            print(f"    {c['contradiction_id']} ({c['severity']}): {c['claim_ids']}")

    stale = mgr.get_stale_claims()
    if stale:
        print(f"\n⚠  {len(stale)} stale claim(s) (not updated in 180+ days):")
        for s in stale:
            print(f"    {s['claim_id']}: {s['statement'][:60]}...")

    return 1 if report["open_contradictions"] > 0 else 0


def cmd_diff(wiki_root_a: str, wiki_root_b: str) -> int:
    mgr_a = ClaimsManager(wiki_root_a)
    mgr_b = ClaimsManager(wiki_root_b)
    diff = mgr_a.diff(mgr_b)

    print("=== Claim Diff ===")
    print(f"  Added:   {diff['added']}")
    print(f"  Removed: {diff['removed']}")
    print(f"  Changed: {diff['changed']}")

    if diff["added_details"]:
        print("\n  Added claims:")
        for c in diff["added_details"]:
            print(f"    + {c['claim_id']}: {c['statement']}")

    if diff["removed_details"]:
        print("\n  Removed claims:")
        for c in diff["removed_details"]:
            print(f"    - {c['claim_id']}: {c['statement']}")

    if diff["changed_details"]:
        print("\n  Changed claims:")
        for c in diff["changed_details"]:
            print(f"    ~ {c['claim_id']}: {c['before'].get('status')} -> {c['after'].get('status')}")

    return 1 if diff["added"] > 0 or diff["removed"] > 0 or diff["changed"] > 0 else 0


def cmd_redteam(wiki_root: str, as_json: bool = False, overrides: "list[str] | None" = None) -> int:
    """Run red-team analysis and print recommendations."""
    import json as json_mod
    from llm_wiki.core.config import ConfigError, resolve_tuning
    if not has_sidecar(wiki_root):
        print("No claim sidecar found. This wiki has no claim tracking enabled.")
        return 0

    try:
        tuning = resolve_tuning(wiki_root, cli_overrides=overrides)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    mgr = ClaimsManager(wiki_root)
    report = mgr.redteam_report(tuning=tuning)

    if as_json:
        print(json_mod.dumps(report, indent=2, default=str))
    else:
        print("=== Claim Red-Team Report ===")
        print(f"  Total claims:          {report['total_claims']}")
        print(f"  Open contradictions:   {report['open_contradictions']}")
        print(f"  Stale claims:           {report['stale_claims']}")
        print(f"  Low confidence claims:  {report['low_confidence_claims']}")
        print(f"  Contested claims:       {report['contested_claims']}")
        print(f"  Health score:           {report['health_score']}/100")

        if report["recommendations"]:
            print("\n📋 Recommendations:")
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"  {i}. [{rec['action']}] {rec['detail']}")

    # fail line: claims.failBelow (LWM_031), default 70 — byte-identical.
    return 1 if report["health_score"] < tuning.claims.failBelow else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Claim/event/contradiction sidecar management.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  llm-wiki claims health ~/my-wiki\n"
            "  llm-wiki claims diff ~/my-wiki /tmp/snapshot"
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand")

    health_parser = subparsers.add_parser("health", help="Show claim sidecar health report")
    health_parser.add_argument("wiki_root", help="Path to the wiki root directory")

    diff_parser = subparsers.add_parser("diff", help="Compare claims between two wiki snapshots")
    diff_parser.add_argument("wiki_root_a", help="Path to the first wiki root")
    diff_parser.add_argument("wiki_root_b", help="Path to the second wiki root")

    redteam_parser = subparsers.add_parser("redteam", help="Red-team analysis of claim quality")
    redteam_parser.add_argument("wiki_root", help="Path to the wiki root directory")
    redteam_parser.add_argument("--json", action="store_true", help="Output as JSON")
    redteam_parser.add_argument("--set", action="append", default=[], dest="overrides",
                                metavar="section.key=value",
                                help="Tuning override, e.g. claims.penaltyStale=4 (LWM_031)")

    args = parser.parse_args()

    if args.subcommand == "health":
        return cmd_health(args.wiki_root)
    elif args.subcommand == "diff":
        return cmd_diff(args.wiki_root_a, args.wiki_root_b)
    elif args.subcommand == "redteam":
        return cmd_redteam(args.wiki_root, args.json if hasattr(args, 'json') else False,
                           overrides=args.overrides)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
