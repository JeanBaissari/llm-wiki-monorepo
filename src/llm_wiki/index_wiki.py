#!/usr/bin/env python3
"""
index_wiki.py — Build and maintain a disk-backed SQLite FTS5 search index.

Creates <wiki-root>/.index/wiki.db with:
  - FTS5 virtual table `pages` for full-text search (storage/retrieval only)
  - `index_meta` table for SHA256 freshness tracking

BM25 scoring uses the current regex-based tokenizer against FTS5-stored
term frequencies. FTS5's built-in tokenizer (unicode61) handles basic
Unicode normalization; the current tokenizer handles BM25 scoring.

Usage:
    llm-wiki index <wiki-root>               # incremental update
    llm-wiki index <wiki-root> --rebuild     # full rebuild
    llm-wiki index <wiki-root> --json        # JSON output

Exit codes:
    0 — success (index up to date)
    1 — no pages found (empty wiki)
    2 — database error
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

# ── Import discover.py from sibling package directory ────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from discover import discover_layout  # type: ignore


# ── Constants ───────────────────────────────────────────────────────────

INDEX_DIR_NAME = ".index"
DB_FILENAME = "wiki.db"

# Frontmatter regex (matches discover.py's implementation)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

# Stop words (mirrors mcp-server/src/search.ts)
STOP_WORDS: set[str] = {
    "the", "is", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "as", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall", "it",
    "its", "this", "that", "these", "those", "not", "no", "nor",
}


# ── Tokenizer (mirrors mcp-server/src/search.ts tokenize()) ─────────────

def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase terms, filtering stop words."""
    return [
        t for t in re.split(r'[\s,.;:!?()\[\]{}"\'`~@#$%^&*+=<>/\\|_-]+', text.lower())
        if len(t) > 1 and t not in STOP_WORDS
    ]


# ── Title extraction ────────────────────────────────────────────────────

def extract_title(content: str, filepath: Path) -> str:
    """Extract title: frontmatter title → H1 heading → filename stem."""
    # 1. Try frontmatter title
    fm_match = FRONTMATTER_RE.match(content)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            m = re.match(r'^title:\s*["\']?(.+?)["\']?\s*$', line.strip())
            if m:
                return m.group(1).strip()

    # 2. Try first H1 heading
    h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()

    # 3. Fall back to filename stem
    stem = filepath.stem
    return stem.replace("-", " ").replace("_", " ")


# ── SHA256 hash ─────────────────────────────────────────────────────────

def sha256_hex(filepath: Path) -> str:
    """Compute hex-encoded SHA256 of file content."""
    return hashlib.sha256(filepath.read_bytes()).hexdigest()


# ── Database setup ──────────────────────────────────────────────────────

def _open_db(db_path: Path) -> sqlite3.Connection:
    """Open the SQLite database, creating it if necessary."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_schema(conn: sqlite3.Connection, rebuild: bool = False) -> None:
    """Create FTS5, index_meta, and index_stats tables. If rebuild=True, drop first."""
    if rebuild:
        conn.execute("DROP TABLE IF EXISTS pages")
        conn.execute("DROP TABLE IF EXISTS index_meta")
        conn.execute("DROP TABLE IF EXISTS index_stats")

    # FTS5 virtual table — storage and retrieval only.
    # Tokenization uses unicode61 (basic Unicode normalization);
    # BM25 scoring uses the current regex-based tokenizer.
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5(
            path,
            title,
            content,
            tokenize='unicode61'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS index_meta (
            file_path   TEXT PRIMARY KEY,
            sha256      TEXT NOT NULL,
            indexed_at  TEXT NOT NULL,
            file_size   INTEGER NOT NULL
        )
    """)

    # Aggregate stats for BM25 scoring — computed after indexing
    conn.execute("""
        CREATE TABLE IF NOT EXISTS index_stats (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    conn.commit()


def _update_aggregate_stats(conn: sqlite3.Connection, stats: dict) -> None:
    """Compute and store aggregate BM25 stats (doc_count, avg_length).

    Uses the pre-tokenized FTS5 content column: counts spaces to
    determine token count per document, which matches the current
    regex-based tokenizer's output.
    """
    # Count documents
    row = conn.execute("SELECT COUNT(*) FROM pages").fetchone()
    doc_count = row[0] if row else 0

    if doc_count == 0:
        conn.execute(
            "INSERT OR REPLACE INTO index_stats (key, value) VALUES (?, ?)",
            ("doc_count", "0"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_stats (key, value) VALUES (?, ?)",
            ("avg_length", "0"),
        )
        conn.commit()
        return

    # Compute average token count from pre-tokenized content.
    # content is space-separated pre-tokenized terms.
    # Number of tokens = number of spaces + 1 (for non-empty content)
    # For empty content: 0 tokens.
    row = conn.execute(
        """SELECT AVG(
            CASE WHEN content = ''
                 THEN 0
                 ELSE LENGTH(content) - LENGTH(REPLACE(content, ' ', '')) + 1
            END
        ) FROM pages"""
    ).fetchone()
    avg_length = row[0] if row and row[0] is not None else 0.0

    conn.execute(
        "INSERT OR REPLACE INTO index_stats (key, value) VALUES (?, ?)",
        ("doc_count", str(doc_count)),
    )
    conn.execute(
        "INSERT OR REPLACE INTO index_stats (key, value) VALUES (?, ?)",
        ("avg_length", str(avg_length)),
    )
    conn.commit()

    stats["doc_count"] = doc_count
    stats["avg_length"] = round(avg_length, 4)


# ── Content preparation ─────────────────────────────────────────────────

def prepare_content(filepath: Path, wiki_root: Path) -> tuple[str, str, str]:
    """Read file and return (relative_path, title, tokenized_content).

    relative_path is the file path relative to wiki_root (not pages_dir),
    so it can be resolved at search time from layout.root.

    tokenized_content is space-separated pre-tokenized terms — this is
    what gets stored in FTS5. The current regex-based tokenizer handles
    BM25 scoring using these stored term frequencies.
    """
    content = filepath.read_text(encoding="utf-8", errors="replace")
    title = extract_title(content, filepath)
    rel_path = str(filepath.relative_to(wiki_root))
    tokens = tokenize(content)
    tokenized = " ".join(tokens)
    return rel_path, title, tokenized


# ── Incremental index update ────────────────────────────────────────────

def index_wiki(wiki_root: Path, rebuild: bool = False) -> dict:
    """Build or update the SQLite FTS5 index for a wiki.

    Returns a dict with indexing statistics.
    """
    start_time = time.time()
    stats: dict = {
        "files_indexed": 0,
        "files_skipped": 0,
        "files_deleted": 0,
        "total_indexed": 0,
        "elapsed_ms": 0,
    }

    # Discover wiki layout
    try:
        layout = discover_layout(str(wiki_root))
    except Exception as e:
        print(f"ERROR: Failed to discover wiki layout: {e}", file=sys.stderr)
        sys.exit(2)

    pages_dir = Path(layout.pages_dir)
    if not pages_dir.is_dir():
        print(f"ERROR: Pages directory not found: {pages_dir}", file=sys.stderr)
        sys.exit(2)

    # Find all .md files
    md_files = list(pages_dir.rglob("*.md"))
    # Filter out dot-prefixed directories (handled by rglob, but be safe)
    md_files = [f for f in md_files if not any(p.startswith(".") for p in f.parts)]

    if not md_files:
        if rebuild:
            # Empty wiki is fine for rebuild — just create empty tables
            pass
        else:
            print("No .md files found in pages directory.", file=sys.stderr)
            sys.exit(1)

    # Open database
    db_path = wiki_root / INDEX_DIR_NAME / DB_FILENAME
    conn = _open_db(db_path)

    try:
        init_schema(conn, rebuild=rebuild)

        if rebuild:
            # Full rebuild: index everything from scratch
            for filepath in md_files:
                try:
                    rel_path, title, tokenized = prepare_content(filepath, wiki_root)
                    file_size = filepath.stat().st_size
                    file_hash = sha256_hex(filepath)
                    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

                    # Insert into FTS5
                    conn.execute(
                        "INSERT INTO pages (path, title, content) VALUES (?, ?, ?)",
                        (rel_path, title, tokenized),
                    )
                    # Insert into index_meta
                    conn.execute(
                        "INSERT OR REPLACE INTO index_meta "
                        "(file_path, sha256, indexed_at, file_size) VALUES (?, ?, ?, ?)",
                        (str(filepath), file_hash, timestamp, file_size),
                    )
                    stats["files_indexed"] += 1
                except Exception as e:
                    print(f"WARNING: Skipping {filepath}: {e}", file=sys.stderr)

            conn.commit()
            stats["total_indexed"] = stats["files_indexed"]

        else:
            # Incremental mode: check each file for changes
            current_files: set[str] = set()

            for filepath in md_files:
                abs_path = str(filepath)
                current_files.add(abs_path)

                try:
                    file_hash = sha256_hex(filepath)
                    file_size = filepath.stat().st_size

                    # Check if file is already indexed
                    row = conn.execute(
                        "SELECT sha256 FROM index_meta WHERE file_path = ?",
                        (abs_path,),
                    ).fetchone()

                    if row is None:
                        # New file — insert
                        rel_path, title, tokenized = prepare_content(filepath, wiki_root)
                        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

                        conn.execute(
                            "INSERT INTO pages (path, title, content) VALUES (?, ?, ?)",
                            (rel_path, title, tokenized),
                        )
                        conn.execute(
                            "INSERT INTO index_meta "
                            "(file_path, sha256, indexed_at, file_size) VALUES (?, ?, ?, ?)",
                            (abs_path, file_hash, timestamp, file_size),
                        )
                        stats["files_indexed"] += 1

                    elif row[0] != file_hash:
                        # Content changed — delete old entry and re-insert
                        rel_path, title, tokenized = prepare_content(filepath, wiki_root)
                        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

                        # Delete old FTS5 entry by path
                        conn.execute(
                            "DELETE FROM pages WHERE path = ?",
                            (rel_path,),
                        )
                        # Insert new
                        conn.execute(
                            "INSERT INTO pages (path, title, content) VALUES (?, ?, ?)",
                            (rel_path, title, tokenized),
                        )
                        # Update meta
                        conn.execute(
                            "UPDATE index_meta SET sha256 = ?, indexed_at = ?, file_size = ? "
                            "WHERE file_path = ?",
                            (file_hash, timestamp, file_size, abs_path),
                        )
                        stats["files_indexed"] += 1

                    else:
                        # Unchanged — skip
                        stats["files_skipped"] += 1

                except Exception as e:
                    print(f"WARNING: Skipping {filepath}: {e}", file=sys.stderr)

            # Delete entries for files that no longer exist on disk
            all_indexed = conn.execute("SELECT file_path FROM index_meta").fetchall()
            for (indexed_path,) in all_indexed:
                if indexed_path not in current_files:
                    # Find relative path for FTS5 deletion
                    try:
                        indexed_file = Path(indexed_path)
                        rel_path = str(indexed_file.relative_to(wiki_root))
                    except ValueError:
                        # File path isn't under wiki_root — skip
                        continue

                    conn.execute("DELETE FROM pages WHERE path = ?", (rel_path,))
                    conn.execute("DELETE FROM index_meta WHERE file_path = ?", (indexed_path,))
                    stats["files_deleted"] += 1

            conn.commit()

            # Get total count
            total_row = conn.execute("SELECT COUNT(*) FROM pages").fetchone()
            stats["total_indexed"] = total_row[0] if total_row else 0

        # ── Update aggregate stats (doc_count, avg_length) for BM25 ────
        _update_aggregate_stats(conn, stats)

    finally:
        conn.close()

    stats["elapsed_ms"] = int((time.time() - start_time) * 1000)
    return stats


# ── CLI ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and maintain a disk-backed SQLite FTS5 search index "
                    "for a wiki."
    )
    parser.add_argument(
        "wiki_root",
        help="Path to the wiki project root",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Drop and recreate the FTS5 index from scratch",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output indexing statistics as JSON",
    )

    args = parser.parse_args()
    wiki_root = Path(args.wiki_root).resolve()

    if not wiki_root.is_dir():
        print(f"ERROR: '{wiki_root}' is not a directory", file=sys.stderr)
        return 2

    try:
        stats = index_wiki(wiki_root, rebuild=args.rebuild)
    except SystemExit:
        raise  # Propagate exit code
    except Exception as e:
        print(f"ERROR: Database error: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(f"Indexed: {stats['files_indexed']} new/updated")
        print(f"Skipped: {stats['files_skipped']} unchanged")
        if stats["files_deleted"] > 0:
            print(f"Deleted: {stats['files_deleted']} removed")
        print(f"Total in index: {stats['total_indexed']}")
        print(f"Elapsed: {stats['elapsed_ms']}ms")

    # Exit 1 if no pages found
    if stats["files_indexed"] == 0 and stats["files_skipped"] == 0 and stats["total_indexed"] == 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
