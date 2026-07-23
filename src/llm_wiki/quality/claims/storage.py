"""JSONL sidecar storage for claims."""
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from llm_wiki.quality.claims.models import Claim, EpistemicEvent, Contradiction


SIDECAR_DIR = ".llm-wiki"


def _ensure_sidecar_dir(wiki_root: str) -> str:
    d = Path(wiki_root) / SIDECAR_DIR / "claims"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def _jsonl_append(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except IOError as e:
        print(f"  ⚠  Failed to write {path}: {e}", file=sys.stderr)


def _jsonl_read_all(path: str) -> list[dict]:
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
    d = Path(wiki_root) / SIDECAR_DIR / "claims"
    return d.exists() and any(d.iterdir())


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
        _jsonl_append(self.claims_path, asdict(claim))
        self.emit_event(EpistemicEvent(
            claim_id=claim.claim_id,
            event_type="created",
            source=claim.sources[0] if claim.sources else "unknown",
            operation_id=claim.first_seen_operation_id,
        ))

    def emit_event(self, event: EpistemicEvent) -> None:
        _jsonl_append(self.events_path, asdict(event))

    def create_contradiction(self, contradiction: Contradiction) -> None:
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
