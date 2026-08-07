#!/usr/bin/env python3
"""alias_store.py — Reversible canonical↔alias store for entity resolution (LWM_025).

Two layers, mirroring how the FTS5 index and graph-data.json already relate to
the markdown files:

  * ``.llm-wiki/entities/aliases.jsonl`` — the durable, git-diffable **source of
    truth**: one append-only JSON event per line
    (``{event: merge|unmerge, canonical_id, alias, ...}``). Reversibility is a
    file operation (append an ``unmerge``), never a schema migration.
  * ``.index/wiki.db`` derived tables (``entity_aliases``, ``entity_canonical``,
    ``alias_meta``) — a regenerable cache. ``CREATE TABLE IF NOT EXISTS`` only;
    the FTS5 / vector tables are never touched. An ``alias_meta`` guard (resolver
    id + threshold + schema version) is asserted by every reader; on
    mismatch/absence the reader rebuilds from the JSONL rather than serving stale
    merges (the ``embed_meta`` pattern, LWM_013 invariant #5).

Stdlib-only (json, sqlite3, pathlib) so the base path needs no extra. Keeps the
"no DB, files are canonical" moat intact.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterable, Optional

ALIAS_SCHEMA_VERSION = 1
_ENTITIES_DIR = ".llm-wiki/entities"
_ALIASES_FILE = "aliases.jsonl"


# ── JSONL source of truth ────────────────────────────────────────────────────

def aliases_path(wiki_root) -> Path:
    return Path(wiki_root) / _ENTITIES_DIR / _ALIASES_FILE


def append_event(wiki_root, event: dict) -> None:
    """Append one resolution event to the JSONL source of truth."""
    p = aliases_path(wiki_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **event}
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def read_events(wiki_root) -> "list[dict]":
    """Read all valid events; silently skip any corrupt/partial line."""
    p = aliases_path(wiki_root)
    if not p.exists():
        return []
    events: "list[dict]" = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip corrupt line; derived state rebuilt from valid events
    return events


def resolve_state(events: Iterable[dict]) -> "dict[str, str]":
    """Replay events into an ``{alias -> canonical_id}`` map.

    ``merge`` sets the mapping; ``unmerge`` removes it — so reversing a merge is
    just appending an ``unmerge`` event (append-only, fully auditable).
    """
    state: "dict[str, str]" = {}
    for e in events:
        kind = e.get("event")
        alias = e.get("alias")
        if not alias:
            continue
        if kind == "merge":
            cid = e.get("canonical_id")
            if cid:
                state[alias] = cid
        elif kind == "unmerge":
            state.pop(alias, None)
    return state


def canonical_labels(events: Iterable[dict]) -> "dict[str, str]":
    """``{canonical_id -> label}`` from the latest merge event per canonical."""
    labels: "dict[str, str]" = {}
    for e in events:
        if e.get("event") == "merge" and e.get("canonical_id"):
            labels[e["canonical_id"]] = e.get("canonical_label", e["canonical_id"])
    return labels


# ── derived cache in .index/wiki.db (additive) ───────────────────────────────

def init_alias_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS entity_aliases "
        "(alias TEXT PRIMARY KEY, canonical_id TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS entity_canonical "
        "(canonical_id TEXT PRIMARY KEY, canonical_label TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS alias_meta "
        "(id INTEGER PRIMARY KEY CHECK (id = 1), schema_version INTEGER NOT NULL, "
        "resolver_id TEXT NOT NULL, threshold REAL NOT NULL)"
    )
    conn.commit()


def alias_meta_matches(conn: sqlite3.Connection, resolver_id: str, threshold: float) -> bool:
    try:
        row = conn.execute(
            "SELECT schema_version, resolver_id, threshold FROM alias_meta WHERE id = 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    if not row:
        return False
    return (
        row[0] == ALIAS_SCHEMA_VERSION
        and row[1] == resolver_id
        and abs(row[2] - threshold) < 1e-9
    )


def rebuild_derived(
    conn: sqlite3.Connection, wiki_root, resolver_id: str, threshold: float
) -> int:
    """Rebuild the derived tables from the JSONL source of truth. Returns #aliases."""
    init_alias_schema(conn)
    events = read_events(wiki_root)
    state = resolve_state(events)
    labels = canonical_labels(events)

    conn.execute("DELETE FROM entity_aliases")
    conn.execute("DELETE FROM entity_canonical")
    for alias, cid in state.items():
        conn.execute(
            "INSERT OR REPLACE INTO entity_aliases (alias, canonical_id) VALUES (?, ?)",
            (alias, cid),
        )
    for cid in set(state.values()):
        conn.execute(
            "INSERT OR REPLACE INTO entity_canonical (canonical_id, canonical_label) VALUES (?, ?)",
            (cid, labels.get(cid, cid)),
        )
    conn.execute("DELETE FROM alias_meta")
    conn.execute(
        "INSERT INTO alias_meta (id, schema_version, resolver_id, threshold) VALUES (1, ?, ?, ?)",
        (ALIAS_SCHEMA_VERSION, resolver_id, threshold),
    )
    conn.commit()
    return len(state)


def canonical_for(conn: sqlite3.Connection, alias: str) -> Optional[str]:
    """Canonical id for an alias, or ``None`` (readers degrade to identity)."""
    try:
        row = conn.execute(
            "SELECT canonical_id FROM entity_aliases WHERE alias = ?", (alias,)
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row else None


def alias_count(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) FROM entity_aliases").fetchone()
    except sqlite3.OperationalError:
        return 0
    return row[0] if row else 0
