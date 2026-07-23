"""CLI entry for lint — wraps lint service with argparse."""
import json
import os
import sys
from pathlib import Path

from llm_wiki.quality.lint.service import lint


def check_templates(templates_dir: Path) -> int:
    """Validate template structure."""
    issues = 0
    if not templates_dir.exists():
        print(f"Templates directory not found: {templates_dir}", file=sys.stderr)
        return 1

    for tdir in sorted(templates_dir.iterdir()):
        if not tdir.is_dir() or tdir.name.startswith("_"):
            continue
        purpose = tdir / "PURPOSE.md"
        schema = tdir / "SCHEMA.md"
        if not purpose.exists():
            print(f"  ⚠  {tdir.name}: missing PURPOSE.md")
            issues += 1
        if not schema.exists():
            print(f"  ⚠  {tdir.name}: missing SCHEMA.md")
            issues += 1

    return 1 if issues > 0 else 0


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Comprehensive health check for an LLM Wiki.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  llm-wiki lint ~/my-wiki\n"
            "  llm-wiki lint --check-templates\n"
        ),
    )
    parser.add_argument("wiki_root", nargs="?",
                        help="Path to the wiki root directory")
    parser.add_argument("--check-templates", nargs="?", const=".",
                        metavar="TEMPLATES_DIR",
                        help="Validate template structure instead of a wiki")
    parser.add_argument("--json", action="store_true",
                        help="Output issues as JSON")

    args = parser.parse_args()

    if args.check_templates is not None:
        templates_dir = Path(args.check_templates).resolve()
        return check_templates(templates_dir)

    if not args.wiki_root:
        parser.print_help()
        return 2

    return lint(args.wiki_root)


if __name__ == "__main__":
    sys.exit(main())
