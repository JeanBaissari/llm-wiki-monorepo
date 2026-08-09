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
        self._by_page: dict[str, list[str]] | None = None
        self._by_status: dict[str, list[str]] | None = None

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

    def _build_indexes(self) -> None:
        if self._by_page is not None:
            return
        self._by_page = defaultdict(list)
        self._by_status = defaultdict(list)
        for c in self.get_all_claims():
            for p in c.get("pages", []):
                self._by_page[p].append(c["claim_id"])
            self._by_status[c.get("status", "active")].append(c["claim_id"])

    def get_claims_by_page(self, page_slug: str) -> list[dict]:
        self._build_indexes()
        cids = self._by_page.get(page_slug, []) if self._by_page else []
        all_claims = {c["claim_id"]: c for c in self.get_all_claims()}
        return [all_claims[cid] for cid in cids if cid in all_claims]

    def get_claims_by_status(self, status: str) -> list[dict]:
        self._build_indexes()
        cids = self._by_status.get(status, []) if self._by_status else []
        all_claims = {c["claim_id"]: c for c in self.get_all_claims()}
        return [all_claims[cid] for cid in cids if cid in all_claims]

    def page_confidence(self, page_slug: str) -> str:
        claims = self.get_claims_by_page(page_slug)
        if not claims:
            return "unknown"

        confidence_score = 0
        for c in claims:
            conf = c.get("confidence", "medium")
            if conf == "high":
                confidence_score += 3
            elif conf == "medium":
                confidence_score += 2
            elif conf == "low":
                confidence_score += 1

        open_ctrs = self.get_open_contradictions()
        for ctr in open_ctrs:
            if any(cid in [cl["claim_id"] for cl in claims] for cid in ctr.get("claim_ids", [])):
                confidence_score -= 3

        avg = confidence_score / max(len(claims), 1)
        if avg >= 2.5:
            return "high"
        elif avg >= 1.5:
            return "medium"
        else:
            return "low"

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

        report = {
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
        report["page_confidence"] = {
            page: self.page_confidence(page)
            for page in sorted(pages_with_claims)
        }
        return report

    def redteam_report(self, tuning=None) -> dict:
        """Generate a red-team analysis of claim quality.

        Surfaces: contradictions, stale claims, low-confidence claims,
        contested claims, and provides actionable recommendations.

        LWM_031: ``tuning`` (a resolved ``TuningConfig``; resolved from the
        wiki root when omitted) supplies the penalty schedule
        ``claims.penaltyStale/penaltyOpen/penaltyLowConf/penaltyContested`` —
        defaults equal the literals (2/10/5/3), so behavior is byte-identical
        with no tuning present.
        """
        from llm_wiki.core.config import resolve_tuning
        cfg = (tuning or resolve_tuning(self.wiki_root)).claims
        all_claims = self.get_all_claims()
        open_ctrs = self.get_open_contradictions()
        stale = self.get_stale_claims()

        low_conf_claims = [c for c in all_claims if c.get("confidence") == "low"]
        contested_claim_ids = set()
        for ctr in open_ctrs:
            for cid in ctr.get("claim_ids", []):
                contested_claim_ids.add(cid)

        recommendations = []
        if stale:
            recommendations.append({
                "action": "review_stale",
                "count": len(stale),
                "detail": f"Review {len(stale)} stale claims (>180 days without update)",
                "claim_ids": [c.get("claim_id") for c in stale],
            })
        if open_ctrs:
            recommendations.append({
                "action": "resolve_contradictions",
                "count": len(open_ctrs),
                "detail": f"Resolve {len(open_ctrs)} open contradictions",
                "contradiction_ids": [c.get("contradiction_id") for c in open_ctrs],
            })
        if low_conf_claims:
            recommendations.append({
                "action": "strengthen_claims",
                "count": len(low_conf_claims),
                "detail": f"Strengthen {len(low_conf_claims)} low-confidence claims with additional evidence",
                "claim_ids": [c.get("claim_id") for c in low_conf_claims],
            })

        penalties = 0
        penalties += len(stale) * cfg.penaltyStale
        penalties += len(open_ctrs) * cfg.penaltyOpen
        penalties += len(low_conf_claims) * cfg.penaltyLowConf
        penalties += len(contested_claim_ids) * cfg.penaltyContested

        return {
            "total_claims": len(all_claims),
            "open_contradictions": len(open_ctrs),
            "stale_claims": len(stale),
            "low_confidence_claims": len(low_conf_claims),
            "contested_claims": len(contested_claim_ids),
            "recommendations": recommendations,
            "health_score": max(0, 100 - penalties),
        }

    def reinforce_claim(self, claim_id: str, source: str, operation_id: str = "") -> None:
        self.emit_event(EpistemicEvent(
            claim_id=claim_id,
            event_type="reinforced",
            source=source,
            operation_id=operation_id,
        ))

    def challenge_claim(self, claim_id: str, source: str, evidence: str = "", operation_id: str = "") -> None:
        self.emit_event(EpistemicEvent(
            claim_id=claim_id,
            event_type="challenged",
            source=source,
            operation_id=operation_id,
        ))
        if evidence:
            ctr = Contradiction(
                contradiction_id="",
                claim_ids=[claim_id],
                status="open",
                severity="medium",
                evidence=[evidence],
            )
            self.create_contradiction(ctr)

    def weaken_claim(self, claim_id: str, source: str, operation_id: str = "") -> None:
        self.emit_event(EpistemicEvent(
            claim_id=claim_id,
            event_type="weakened",
            source=source,
            operation_id=operation_id,
        ))

    def supersede_claim(self, claim_id: str, replacement_id: str, source: str, operation_id: str = "") -> None:
        self.emit_event(EpistemicEvent(
            claim_id=claim_id,
            event_type="superseded",
            source=source,
            operation_id=operation_id,
        ))

    def resolve_contradiction(self, contradiction_id: str, resolution_claim_id: str) -> bool:
        all_ctrs = self.get_all_contradictions()
        for ctr in all_ctrs:
            if ctr.get("contradiction_id") == contradiction_id:
                ctr["status"] = "resolved"
                ctr["resolution"] = f"Claim {resolution_claim_id} preferred"
                return True
        return False

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
