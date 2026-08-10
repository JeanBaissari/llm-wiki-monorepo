#!/usr/bin/env python3
"""
validate_fixtures.py — Check test fixture wikis are in sync with current schema.

Runs four validation passes:
  1. Schema version: each fixture's .schema_version must match current
  2. Frontmatter: every page must have required fields
  3. Wikilinks: all [[links]] must resolve (except stale fixture)
  4. Stale lint: lint_wiki.py on stale fixture must detect all expected issues

Usage:
    python3 skill/scripts/validate_fixtures.py              # validate all
    python3 skill/scripts/validate_fixtures.py --quiet       # only exit code
    python3 skill/scripts/validate_fixtures.py --json        # machine output

Exit codes:
    0 — all fixtures valid
    1 — one or more fixtures invalid
    2 — runtime error (missing files, import failure)
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import yaml
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
WIKIS_DIR = FIXTURES_DIR / "wikis"
SEEDS_DIR = FIXTURES_DIR / "seeds"
TEMPLATES_SHARED = REPO_ROOT / "templates" / "_shared" / "base-schema.md"

# ── Constants ──────────────────────────────────────────────────────────
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

REQUIRED_FRONTMATTER = {"title", "type", "created", "updated", "sources", "tags"}
FIXTURE_NAMES = ["empty", "minimal", "stale", "populated"]


def compute_schema_version() -> str:
    """Derive schema version from SHA256 of base-schema.md."""
    if TEMPLATES_SHARED.exists():
        return hashlib.sha256(TEMPLATES_SHARED.read_bytes()).hexdigest()[:8]
    return "00000000"


def parse_frontmatter(text: str) -> dict | None:
    """Minimal YAML-ish frontmatter parser (matches lint_wiki.py)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    body = m.group(1)
    result: dict = {}
    i = 0
    lines = body.split("\n")
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        val = rest.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            result[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()] if inner else []
        elif val.startswith(('"', "'")):
            result[key] = val[1:-1]
        elif val.lower() in ("true", "false"):
            result[key] = val.lower() == "true"
        else:
            result[key] = val
        i += 1
    return result


def extract_wikilinks(text: str) -> list[str]:
    return WIKILINK_RE.findall(text)


def load_pages(wiki_dir: Path) -> dict[str, Path]:
    """Build slug → Path lookup for all .md files under wiki_dir/wiki/."""
    pages: dict[str, Path] = {}
    pages_dir = wiki_dir / "wiki"
    if not pages_dir.exists():
        return pages
    for p in pages_dir.rglob("*.md"):
        # Store by stem (filename without .md)
        pages[p.stem] = p
        # Store by relative path without extension — forward slashes on every
        # platform: wikilinks are authored with "/" and str(Path) yields
        # backslashes on Windows, which would make every path-style link dead.
        rel = p.relative_to(pages_dir)
        pages[str(rel.with_suffix("")).replace(os.sep, "/")] = p
    return pages


class ValidationReport:
    """Accumulate validation issues."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passes: list[str] = []

    def error(self, msg: str):
        self.errors.append(msg)

    def warning(self, msg: str):
        self.warnings.append(msg)

    def ok(self, msg: str):
        self.passes.append(msg)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def summary(self) -> str:
        lines = []
        if self.passes:
            lines.append(f"✅ {len(self.passes)} check(s) passed")
        if self.warnings:
            lines.append(f"⚠️  {len(self.warnings)} warning(s)")
        if self.errors:
            lines.append(f"❌ {len(self.errors)} error(s)")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "passes": self.passes,
            "warnings": self.warnings,
            "errors": self.errors,
            "has_errors": self.has_errors,
        }


# ══════════════════════════════════════════════════════════════════════════
# VALIDATION PASSES
# ══════════════════════════════════════════════════════════════════════════

def check_schema_versions(report: ValidationReport, current_version: str) -> dict[str, str]:
    """Check 1: Each fixture's .schema_version matches current."""
    versions: dict[str, str] = {}
    for name in FIXTURE_NAMES:
        fixture_dir = WIKIS_DIR / name
        if not fixture_dir.exists():
            report.error(f"Fixture '{name}' not found at {fixture_dir}")
            continue
        version_file = fixture_dir / ".schema_version"
        if not version_file.exists():
            report.warning(f"Fixture '{name}' has no .schema_version file")
            continue
        stored = version_file.read_text(encoding="utf-8").strip()
        versions[name] = stored
        if stored != current_version:
            report.error(
                f"FIXTURE STALE: '{name}' built with schema {stored}, "
                f"current is {current_version}. Run: python3 skill/scripts/regenerate_fixtures.py"
            )

    if not report.has_errors:
        report.ok(f"All {len(FIXTURE_NAMES)} fixtures match schema version {current_version}")
    return versions


def check_frontmatter(report: ValidationReport, fixture_name: str) -> None:
    """Check 2: All pages in the fixture have required frontmatter fields."""
    wiki_dir = WIKIS_DIR / fixture_name
    pages_dir = wiki_dir / "wiki"
    if not pages_dir.exists():
        report.warning(f"Fixture '{fixture_name}' has no wiki/ directory")
        return

    ok_count = 0
    issue_count = 0

    for md_file in pages_dir.rglob("*.md"):
        if md_file.name == "index.md":
            continue  # index.md has different requirements
        rel = md_file.relative_to(wiki_dir)
        text = md_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if fm is None:
            report.error(f"{fixture_name}: {rel} — no YAML frontmatter")
            issue_count += 1
            continue
        for field in REQUIRED_FRONTMATTER:
            if field not in fm:
                report.error(f"{fixture_name}: {rel} — missing '{field}' in frontmatter")
                issue_count += 1
        if fm is not None and all(f in fm for f in REQUIRED_FRONTMATTER):
            ok_count += 1

    if issue_count == 0 and ok_count > 0:
        report.ok(f"Frontmatter OK in '{fixture_name}': {ok_count} page(s)")
    elif ok_count == 0 and issue_count == 0:
        report.warning(f"Fixture '{fixture_name}' has no wiki pages to check")


def check_wikilinks(report: ValidationReport, fixture_name: str) -> None:
    """Check 3: All wikilinks resolve to existing pages."""
    wiki_dir = WIKIS_DIR / fixture_name
    pages = load_pages(wiki_dir)
    if not pages:
        report.warning(f"Fixture '{fixture_name}' has no pages for wikilink check")
        return

    ok_count = 0
    dead_count = 0

    pages_dir = wiki_dir / "wiki"
    for md_file in pages_dir.rglob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        links = extract_wikilinks(text)
        for link in links:
            target = link.strip()
            # Check by stem and full relative path
            if target not in pages and target.lower().replace(" ", "_") not in pages:
                # Try common alternates
                found = False
                for alt in [target.lower(), target.replace(" ", "-"), target.replace(" ", "_")]:
                    if alt in pages:
                        found = True
                        break
                if not found:
                    rel = md_file.relative_to(wiki_dir)
                    report.error(f"{fixture_name}: {rel} → [[{target}]] is a dead link")
                    dead_count += 1
        ok_count += 1

    if dead_count == 0:
        report.ok(f"Wikilinks OK in '{fixture_name}': {ok_count} page(s) checked")


def check_stale_lint(report: ValidationReport) -> None:
    """Check 4: lint_wiki.py on stale fixture detects all expected issues."""
    stale_wiki = WIKIS_DIR / "stale"
    seed_path = SEEDS_DIR / "stale.yaml"

    if not stale_wiki.exists():
        report.error("Stale fixture not found — cannot run lint check")
        return
    if not seed_path.exists():
        report.error("stale.yaml seed not found — cannot verify expected issues")
        return

    with open(seed_path, encoding="utf-8") as f:
        seed = yaml.safe_load(f)

    expected = seed.get("expected_lint_failures", [])
    if not expected:
        report.warning("No expected_lint_failures in stale.yaml seed")
        return

    # Run lint_wiki.py on the stale fixture
    lint_script = SCRIPTS_DIR / "lint_wiki.py"
    cmd = [sys.executable, str(lint_script), str(stale_wiki)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    lint_output = (result.stdout or "") + (result.stderr or "")

    # Check each expected failure
    found_count = 0
    missing_count = 0

    # Map PRD rule names to lint_wiki.py output patterns
    RULE_PATTERNS = {
        "dead_wikilinks": "Dead wikilinks",
        "stale_pages": "Stale pages",
        "orphan_pages": "Orphan pages",
        "low_confidence": "Low/medium-confidence",
        "large_pages": "Large pages",
        "contested_page": "contradiction signals",
        "contradiction_page": "contradiction signals",
        "source_drift": "Source drift",
        "missing_frontmatter": "Frontmatter validation",
    }

    for exp in expected:
        rule = exp["rule"]
        location = exp.get("location", "")
        pattern = RULE_PATTERNS.get(rule, rule)

        # Check if the pattern appears in lint output as a POSITIVE finding
        # (not "No orphan pages" or "✅ No orphan pages")
        found = False
        pattern_lower = pattern.lower()
        for line in lint_output.lower().split("\n"):
            if pattern_lower in line:
                # Skip lines that are negations: "no orphan pages", "✅ no orphan pages"
                stripped = line.strip()
                if not re.match(r'(✅|⚠️|🔴|🟡|🟢)?\s*no\s', stripped, re.IGNORECASE):
                    found = True
                    break
        if found:
            found_count += 1
        elif location and location.lower() in lint_output.lower():
            # Fallback: check if location is mentioned in a positive context
            location_lower = location.lower()
            for line in lint_output.lower().split("\n"):
                if location_lower in line:
                    if not re.match(r'(✅|⚠️|🔴|🟡|🟢)?\s*no\s', line.strip(), re.IGNORECASE):
                        found = True
                        break
            if found:
                found_count += 1
            else:
                report.error(
                    f"STALE FIXTURE: expected lint rule '{rule}' ({exp['description']}) "
                    f"not triggered. lint_wiki.py may have changed."
                )
                missing_count += 1
        else:
            report.error(
                f"STALE FIXTURE: expected lint rule '{rule}' ({exp['description']}) "
                f"not triggered. lint_wiki.py may have changed."
            )
            missing_count += 1

    if missing_count == 0:
        report.ok(f"Stale fixture lint check: all {found_count} expected issues detected")
    else:
        report.error(
            f"Stale fixture: {missing_count}/{len(expected)} expected issues NOT detected. "
            f"Update tests/fixtures/seeds/stale.yaml if lint rules changed."
        )


def validate_fixtures(quiet: bool = False) -> int:
    """Run all validation passes. Returns exit code."""
    report = ValidationReport()

    # Ensure required directories exist
    if not WIKIS_DIR.exists():
        print("✗ tests/fixtures/wikis/ not found", file=sys.stderr)
        return 2
    if not TEMPLATES_SHARED.exists():
        print("✗ templates/_shared/base-schema.md not found", file=sys.stderr)
        return 2

    current_version = compute_schema_version()

    if not quiet:
        print(f"Schema version: {current_version}")
        print(f"Validating {len(FIXTURE_NAMES)} fixture(s)...\n")

    # ── Pass 1: Schema version ──
    check_schema_versions(report, current_version)

    # ── Pass 2: Frontmatter ──
    for name in FIXTURE_NAMES:
        check_frontmatter(report, name)

    # ── Pass 3: Wikilinks (skip stale — it deliberately has dead links) ──
    for name in FIXTURE_NAMES:
        if name != "stale":
            check_wikilinks(report, name)

    # ── Pass 4: Stale lint ──
    check_stale_lint(report)

    # ── Print results ──
    if report.errors:
        # Errors always print (even --quiet): CI consumers (test_fixtures_fresh)
        # surface stderr as the failure detail — silent failures are undebuggable.
        print("❌ ERRORS:", file=sys.stderr)
        for e in report.errors:
            print(f"   {e}", file=sys.stderr)
    if not quiet:
        if report.warnings:
            print("\n⚠️  WARNINGS:")
            for w in report.warnings:
                print(f"   {w}")
        print(f"\n{report.summary()}")

    if report.has_errors:
        if not quiet:
            print("\nFix: python3 skill/scripts/regenerate_fixtures.py")
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate test fixture wikis against current schema."
    )
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress output, return exit code only")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--schema-version", action="store_true",
                        help="Print current schema version and exit")
    args = parser.parse_args()

    if args.schema_version:
        print(compute_schema_version())
        return

    if args.json:
        report = ValidationReport()
        current_version = compute_schema_version()
        check_schema_versions(report, current_version)
        for name in FIXTURE_NAMES:
            check_frontmatter(report, name)
        for name in FIXTURE_NAMES:
            if name != "stale":
                check_wikilinks(report, name)
        check_stale_lint(report)
        result = {
            "schema_version": current_version,
            "exit_code": 1 if report.has_errors else 0,
            "report": report.to_dict(),
        }
        print(json.dumps(result, indent=2))
        sys.exit(result["exit_code"])

    sys.exit(validate_fixtures(quiet=args.quiet))


if __name__ == "__main__":
    main()
