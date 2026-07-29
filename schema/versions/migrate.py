#!/usr/bin/env python3
"""
NOTE: This module is currently unreferenced in the codebase (v0.3.0).
It was written as a migration stub for future schema version upgrades.
When a schema migration is needed, wire this into the CLI via `llm_wiki migrate-schema`.

migrate.py — Schema migration runner for LLM Wiki.

Reads a wiki directory, detects the current schema version from a
`.schema_version` file (or infers from page frontmatter), consults
the migration registry (`schema/versions/migrations.json`), and
prints the migration path.

Usage:
    python3 migrate.py <wiki-root>
    python3 migrate.py <wiki-root> --apply  (not yet implemented)
    python3 migrate.py <wiki-root> --dry-run

This is a minimal stub for the LWM_009 migration mechanism.
Full implementation (Phase 4) is deferred to a follow-up.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional


MIGRATIONS_DIR = Path(__file__).resolve().parent
MIGRATIONS_FILE = MIGRATIONS_DIR / "migrations.json"


def load_registry() -> dict:
    if MIGRATIONS_FILE.exists():
        with open(MIGRATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"current_version": "v0.2.1", "migrations": []}


def detect_wiki_version(wiki_root: str) -> Optional[str]:
    """Detect the current schema version of a wiki.

    Checks `.schema_version` file first, then falls back to inferring
    from page frontmatter `schema_version` fields.
    """
    version_file = Path(wiki_root) / ".schema_version"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()

    # Infer from pages
    pages_dir_candidates = ["wiki", "content", "pages", "notes"]
    for name in pages_dir_candidates:
        d = Path(wiki_root) / name
        if d.is_dir():
            for p in sorted(d.rglob("*.md"))[:5]:
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                    for line in text.split("\n")[:20]:
                        if line.strip().startswith("schema_version:"):
                            return line.split(":", 1)[1].strip().strip("\"'")
                except IOError:
                    pass
    return None


def compute_migration_path(current_version: str, target_version: str,
                          registry: dict) -> list[dict]:
    """Compute the ordered list of migrations to apply.

    Stub: returns an empty list since no migrations have implementations yet.
    """
    if current_version == target_version:
        return []
    migrations = registry.get("migrations", [])
    # Find path from current to target
    path = []
    for m in migrations:
        if m.get("from_version") == current_version:
            path.append(m)
            if m.get("to_version") == target_version:
                return path
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Schema migration runner for LLM Wiki."
    )
    parser.add_argument("wiki_root", help="Path to the wiki root directory")
    parser.add_argument("--apply", action="store_true",
                        help="Apply migrations (not yet implemented)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show migrations that would be applied")

    args = parser.parse_args()

    if not os.path.isdir(args.wiki_root):
        print(f"ERROR: wiki root not found: {args.wiki_root}", file=sys.stderr)
        return 1

    registry = load_registry()
    target_version = registry.get("current_version", "v0.2.1")
    current_version = detect_wiki_version(args.wiki_root)

    print(f"Registry version: {target_version}")
    print(f"Detected version: {current_version or 'unknown (pre-schema-version era)'}")

    if current_version is None:
        print("\nNo schema version detected. Wiki predates LWM_009 schema tracking.")
        print("Run `llm-wiki lint` to assess compliance, then add a `.schema_version` file.")
        return 0

    if current_version == target_version:
        print(f"\nWiki is already at {target_version}. No migrations needed.")
        return 0

    path = compute_migration_path(current_version, target_version, registry)
    if not path:
        print(f"\nNo migration path from {current_version} to {target_version}.")
        return 1

    print(f"\nMigration path ({len(path)} step(s)):")
    for m in path:
        print(f"  {m['from_version']} → {m['to_version']}: {m['description']}")

    if args.apply:
        print("\nMigration execution not yet implemented. Use --dry-run to preview.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
