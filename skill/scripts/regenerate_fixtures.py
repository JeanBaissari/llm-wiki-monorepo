#!/usr/bin/env python3
"""
regenerate_fixtures.py — Rebuild test fixture wikis from seed data.

Reads declarative YAML seed files from tests/fixtures/seeds/ and produces
the corresponding fixture wikis under tests/fixtures/wikis/.

Usage:
    python3 skill/scripts/regenerate_fixtures.py              # rebuild all
    python3 skill/scripts/regenerate_fixtures.py --fixture minimal  # rebuild one

Why:
    When wiki schema changes (new frontmatter fields, template updates),
    committed fixtures silently rot. This script regenerates them from
    seeds so they stay in sync. Seeds are the source of truth.

Determinism:
    Same seed + same schema version → identical output. Safe to run twice.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import yaml
from pathlib import Path
from datetime import date

# ── Paths ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "skill" / "scripts"
SEEDS_DIR = REPO_ROOT / "tests" / "fixtures" / "seeds"
WIKIS_DIR = REPO_ROOT / "tests" / "fixtures" / "wikis"
TEMPLATES_SHARED = REPO_ROOT / "templates" / "_shared" / "base-schema.md"


def compute_schema_version() -> str:
    """Derive schema version from SHA256 of base-schema.md."""
    if TEMPLATES_SHARED.exists():
        return hashlib.sha256(TEMPLATES_SHARED.read_bytes()).hexdigest()[:8]
    return "00000000"


def scaffold_wiki(root: Path, name: str, template: str = "codebase") -> None:
    """Run scaffold.py to create a fresh wiki skeleton."""
    cmd = [
        sys.executable, str(SCRIPTS_DIR / "scaffold.py"),
        str(root), name,
        "--template", template,
        "--force",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"Scaffold failed for {root}: {result.stderr[:500]}")


def write_page(wiki_root: Path, page_cfg: dict, created: str = "2026-01-15") -> None:
    """Write a wiki page with proper frontmatter from seed config."""
    path = wiki_root / page_cfg["path"]
    path.parent.mkdir(parents=True, exist_ok=True)

    title = page_cfg["title"]
    ptype = page_cfg["type"]
    tags = page_cfg.get("tags", ["test"])
    sources = page_cfg.get("sources", [])
    updated = page_cfg.get("updated", date.today().isoformat())
    content = page_cfg["content"]
    confidence = page_cfg.get("confidence", "high")

    fm_lines = [
        "---",
        f"title: {title}",
        f"type: {ptype}",
        f"created: {created}",
        f"updated: {updated}",
        f"sources: [{', '.join(sources)}]" if sources else "sources: []",
        f"tags: [{', '.join(tags)}]",
        f"confidence: {confidence}",
    ]

    # Optional fields
    if page_cfg.get("contested"):
        fm_lines.append("contested: true")
    contradictions = page_cfg.get("contradictions")
    if contradictions:
        if isinstance(contradictions, list):
            fm_lines.append("contradictions:")
            for c in contradictions:
                fm_lines.append(f"  - \"{c}\"")
        else:
            fm_lines.append(f"contradictions: {contradictions}")

    fm_lines.append("---")
    fm_lines.append("")

    full_text = "\n".join(fm_lines) + content + "\n"
    path.write_text(full_text, encoding="utf-8")


def write_source(wiki_root: Path, source_cfg: dict) -> None:
    """Write a raw source file from seed config."""
    path = wiki_root / source_cfg["path"]
    path.parent.mkdir(parents=True, exist_ok=True)

    content = source_cfg["content"]

    # If sha256 is specified, compute and embed it
    sha = source_cfg.get("sha256")
    if sha:
        if sha == "PLACEHOLDER":
            # Compute actual SHA256 of body
            actual_sha = hashlib.sha256(content.encode()).hexdigest()
        else:
            actual_sha = sha

        title = path.stem.replace("-", " ").title()
        fm = f"---\ntitle: {title}\ntype: source\nsha256: {actual_sha}\n---\n\n"
        path.write_text(fm + content, encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")


def update_index(wiki_root: Path, pages: list[dict]) -> None:
    """Append page entries to wiki/index.md."""
    index_path = wiki_root / "wiki" / "index.md"
    if not index_path.exists():
        return

    existing = index_path.read_text(encoding="utf-8")

    # Group pages by type, skipping those marked omit_from_index
    entities = [p for p in pages if p["type"] == "entity" and not p.get("omit_from_index")]
    concepts = [p for p in pages if p["type"] == "concept" and not p.get("omit_from_index")]

    entries = []
    if entities:
        entries.append("\n## Entities")
        for p in entities:
            slug = p["path"].replace("wiki/", "").replace(".md", "")
            entries.append(f"- [[{slug}|{p['title']}]]")

    if concepts:
        entries.append("\n## Concepts")
        for p in concepts:
            slug = p["path"].replace("wiki/", "").replace(".md", "")
            entries.append(f"- [[{slug}|{p['title']}]]")

    if entries:
        index_path.write_text(existing + "\n".join(entries) + "\n", encoding="utf-8")


def write_schema_version_marker(wiki_root: Path) -> None:
    """Write .schema_version marker into the wiki root."""
    version = compute_schema_version()
    (wiki_root / ".schema_version").write_text(version + "\n", encoding="utf-8")


def regenerate_fixture(fixture_name: str) -> Path:
    """Regenerate a single fixture wiki from its seed file."""
    seed_path = SEEDS_DIR / f"{fixture_name}.yaml"
    if not seed_path.exists():
        print(f"✗ Seed file not found: {seed_path}")
        sys.exit(1)

    with open(seed_path, encoding="utf-8") as f:
        seed = yaml.safe_load(f)

    wiki_root = WIKIS_DIR / fixture_name
    wiki_name = seed.get("wiki_name", f"{fixture_name.title()} Test Wiki")
    template = seed.get("template", "codebase")

    # Clear existing wiki
    if wiki_root.exists():
        shutil.rmtree(wiki_root)

    # Scaffold fresh
    scaffold_wiki(wiki_root, wiki_name, template)

    # Write pages
    pages = seed.get("pages", [])
    for page_cfg in pages:
        write_page(wiki_root, page_cfg)

    # Write sources
    sources = seed.get("sources", [])
    for source_cfg in sources:
        write_source(wiki_root, source_cfg)

    # Update schema version
    write_schema_version_marker(wiki_root)

    # Update index
    update_index(wiki_root, pages)

    # Update the seed file's schema_version field
    current_version = compute_schema_version()
    seed["schema_version"] = current_version
    with open(seed_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(seed, f, default_flow_style=False, allow_unicode=True,
                       sort_keys=False, width=120)

    print(f"  ✓ {fixture_name}: {len(pages)} pages, {len(sources)} sources → {wiki_root}")
    return wiki_root


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild test fixture wikis from seed data."
    )
    parser.add_argument(
        "--fixture", "-f",
        choices=["empty", "minimal", "stale", "populated"],
        help="Regenerate a single fixture (default: all)",
    )
    parser.add_argument(
        "--schema-version",
        action="store_true",
        help="Print current schema version and exit",
    )
    args = parser.parse_args()

    if args.schema_version:
        print(compute_schema_version())
        return

    fixtures = [args.fixture] if args.fixture else ["empty", "minimal", "stale", "populated"]

    current_version = compute_schema_version()
    print(f"Schema version: {current_version}")
    print(f"Regenerating {len(fixtures)} fixture(s)...")

    for name in fixtures:
        regenerate_fixture(name)

    print("\nDone. Run validate_fixtures.py to verify.")
    print(f"  python3 skill/scripts/validate_fixtures.py")


if __name__ == "__main__":
    main()
