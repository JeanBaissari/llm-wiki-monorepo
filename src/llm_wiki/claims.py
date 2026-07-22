"""
claims.py — Optional claim/event/contradiction sidecar model for LLM Wiki.

Provides:
  - Claim, EpistemicEvent, Contradiction dataclasses
  - SidecarStorage for append-only JSONL records in wiki/.llm-wiki/
  - ClaimsManager for high-level operations
  - CLI commands: claims health, claims diff
"""

import json
import os
import re
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ── Dataclasses ───────────────────────────────────────────────────────────

@dataclass
class Claim:
    claim_id: str
    statement: str
    confidence: str  # high, medium, low
    status: str  # active, contested, superseded, resolved, retracted, stale
    sources: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    claim_type: str = "fact"
    schema_version: str = "v0.2.1"
    created_at: str = ""
    updated_at: str = ""
    first_seen_operation_id: str = ""
    last_seen_operation_id: str = ""
    depends_on: list[str] = field(default_factory=list)
    contradicted_by: list[str] = field(default_factory=list)

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class EpistemicEvent:
    claim_id: str
    event_type: str  # created, reinforced, challenged, weakened, superseded, resolved, retracted
    source: str
    timestamp: str = ""
    event_id: str = ""
    operation_id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.event_id:
            self.event_id = f"evt_{uuid.uuid4().hex[:12]}"


@dataclass
class Contradiction:
    contradiction_id: str
    claim_ids: list[str]
    status: str  # open, investigating, resolved, false_positive, wont_fix
    severity: str  # low, medium, high, blocking
    evidence: list[str] = field(default_factory=list)
    resolution: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.contradiction_id:
            self.contradiction_id = f"ctr_{uuid.uuid4().hex[:12]}"


# ── Sidecar Storage ──────────────────────────────────────────────────────

SIDECAR_DIR = ".llm-wiki"


def _ensure_sidecar_dir(wiki_root: str) -> str:
    """Ensure the .llm-wiki/claims/ directory exists."""
    d = Path(wiki_root) / SIDECAR_DIR / "claims"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def _jsonl_append(path: str, record: dict) -> None:
    """Append a JSON record to a JSONL file atomically."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except IOError as e:
        print(f"  ⚠  Failed to write {path}: {e}", file=sys.stderr)


def _jsonl_read_all(path: str) -> list[dict]:
    """Read all JSON records from a JSONL file."""
    if not os.path.exists(path):
        return []
    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except IOError:
        pass
    return records


def has_sidecar(wiki_root: str) -> bool:
    """Check whether a wiki has claim sidecar files."""
    d = Path(wiki_root) / SIDECAR_DIR / "claims"
    return d.exists() and any(d.iterdir())


# ── ClaimsManager ─────────────────────────────────────────────────────────

class ClaimsManager:
    """High-level operations on claim sidecars."""

    def __init__(self, wiki_root: str):
        self.wiki_root = str(Path(wiki_root).resolve())
        self.sidecar_dir = _ensure_sidecar_dir(self.wiki_root)

    @property
    def claims_path(self) -> str:
        return os.path.join(self.sidecar_dir, "claims.jsonl")

    @property
    def events_path(self) -> str:
        return os.path.join(self.sidecar_dir, "events.jsonl")

    @property
    def contradictions_path(self) -> str:
        return os.path.join(self.sidecar_dir, "contradictions.jsonl")

    def create_claim(self, claim: Claim) -> None:
        """Record a new claim and emit a 'created' epistemic event."""
        _jsonl_append(self.claims_path, asdict(claim))
        self.emit_event(EpistemicEvent(
            claim_id=claim.claim_id,
            event_type="created",
            source=claim.sources[0] if claim.sources else "unknown",
            operation_id=claim.first_seen_operation_id,
        ))

    def emit_event(self, event: EpistemicEvent) -> None:
        """Append an epistemic event."""
        _jsonl_append(self.events_path, asdict(event))

    def create_contradiction(self, contradiction: Contradiction) -> None:
        """Record a contradiction."""
        _jsonl_append(self.contradictions_path, asdict(contradiction))

    def get_all_claims(self) -> list[dict]:
        return _jsonl_read_all(self.claims_path)

    def get_all_events(self) -> list[dict]:
        return _jsonl_read_all(self.events_path)

    def get_all_contradictions(self) -> list[dict]:
        return _jsonl_read_all(self.contradictions_path)

    def get_active_claims(self) -> list[dict]:
        return [c for c in self.get_all_claims() if c.get("status") == "active"]

    def get_open_contradictions(self) -> list[dict]:
        return [c for c in self.get_all_contradictions() if c.get("status") in ("open", "investigating")]

    def get_claims_by_page(self, page_slug: str) -> list[dict]:
        return [c for c in self.get_all_claims() if page_slug in c.get("pages", [])]

    def get_claims_by_status(self, status: str) -> list[dict]:
        return [c for c in self.get_all_claims() if c.get("status") == status]

    def get_stale_claims(self, staleness_days: int = 180) -> list[dict]:
        """Find claims not updated within staleness_days."""
        now = datetime.now(timezone.utc)
        stale = []
        for c in self.get_all_claims():
            updated = c.get("updated_at", "")
            if updated:
                try:
                    dt = datetime.fromisoformat(updated)
                    if (now - dt).days > staleness_days:
                        stale.append(c)
                except (ValueError, TypeError):
                    stale.append(c)
        return stale

    def health_report(self) -> dict:
        """Produce a health report summary."""
        all_claims = self.get_all_claims()
        all_events = self.get_all_events()
        all_contradictions = self.get_all_contradictions()
        open_contradictions = self.get_open_contradictions()

        status_counts = defaultdict(int)
        for c in all_claims:
            status_counts[c.get("status", "unknown")] += 1

        severity_counts = defaultdict(int)
        for c in all_contradictions:
            severity_counts[c.get("severity", "unknown")] += 1

        stale = self.get_stale_claims()

        # Page confidence compilation
        pages_with_claims = set()
        for c in all_claims:
            for p in c.get("pages", []):
                pages_with_claims.add(p)

        return {
            "total_claims": len(all_claims),
            "total_events": len(all_events),
            "total_contradictions": len(all_contradictions),
            "open_contradictions": len(open_contradictions),
            "stale_claims": len(stale),
            "pages_with_claims": len(pages_with_claims),
            "status_breakdown": dict(status_counts),
            "severity_breakdown": dict(severity_counts),
            "active_claims": len(self.get_active_claims()),
        }

    def diff(self, other: "ClaimsManager") -> dict:
        """Compare claims between two snapshots."""
        local_claims = {c["claim_id"]: c for c in self.get_all_claims()}
        other_claims = {c["claim_id"]: c for c in other.get_all_claims()}

        added = [c for cid, c in local_claims.items() if cid not in other_claims]
        removed = [c for cid, c in other_claims.items() if cid not in local_claims]
        changed = []
        for cid, lc in local_claims.items():
            if cid in other_claims:
                oc = other_claims[cid]
                if lc.get("status") != oc.get("status") or lc.get("confidence") != oc.get("confidence"):
                    changed.append({
                        "claim_id": cid,
                        "before": oc,
                        "after": lc,
                    })

        return {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "added_details": [{"claim_id": c["claim_id"], "statement": c["statement"][:80]} for c in added],
            "removed_details": [{"claim_id": c["claim_id"], "statement": c["statement"][:80]} for c in removed],
            "changed_details": changed,
        }


# ── CLI Commands ──────────────────────────────────────────────────────────

def cmd_health(wiki_root: str) -> int:
    """Print claim sidecar health report."""
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
    """Compare claims between two wikis (or two snapshots of the same wiki)."""
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
