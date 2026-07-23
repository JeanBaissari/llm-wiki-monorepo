"""test_claims.py — Tests for the claims module.

Covers:
  - Claim creation and serialization
  - EpistemicEvent creation with valid event types
  - Contradiction creation and relationship tracking
  - ClaimsManager JSONL sidecar write and read
  - health report generation (JSON output)
  - diff between two sidecar states
  - Sidecar-free wiki still works (no errors when no claims exist)
  - Claim ID uniqueness
  - Confidence values in valid range
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from llm_wiki.quality.claims import (
    Claim,
    EpistemicEvent,
    Contradiction,
    ClaimsManager,
    has_sidecar,
)
from llm_wiki.quality.claims.storage import _ensure_sidecar_dir, _jsonl_append, _jsonl_read_all, SIDECAR_DIR
from llm_wiki.quality.claims.cli import cmd_health, cmd_diff


# ── Claim ──────────────────────────────────────────────────────────────────


class TestClaim:
    def test_creation_basic(self):
        c = Claim(
            claim_id="claim_001",
            statement="The Earth is round.",
            confidence="high",
            status="active",
        )
        assert c.claim_id == "claim_001"
        assert c.statement == "The Earth is round."
        assert c.confidence == "high"
        assert c.status == "active"
        assert c.sources == []
        assert c.pages == []
        assert c.claim_type == "fact"
        assert c.schema_version == "v0.2.1"
        assert c.depends_on == []
        assert c.contradicted_by == []

    def test_creation_with_timestamps(self):
        ts = "2026-01-15T12:00:00+00:00"
        c = Claim(
            claim_id="claim_002",
            statement="Test.",
            confidence="medium",
            status="active",
            created_at=ts,
            updated_at=ts,
        )
        assert c.created_at == ts
        assert c.updated_at == ts

    def test_auto_timestamps(self):
        c = Claim(
            claim_id="claim_003",
            statement="Auto timestamps.",
            confidence="low",
            status="active",
        )
        assert c.created_at != ""
        assert c.updated_at != ""
        assert "T" in c.created_at

    def test_serialization_via_asdict(self):
        c = Claim(
            claim_id="claim_004",
            statement="Serializable claim.",
            confidence="high",
            status="active",
            sources=["source1.md"],
            pages=["page1.md"],
            depends_on=["claim_001"],
            contradicted_by=["claim_005"],
        )
        d = c.__dict__
        assert d["claim_id"] == "claim_004"
        assert d["sources"] == ["source1.md"]
        assert d["pages"] == ["page1.md"]
        assert d["depends_on"] == ["claim_001"]
        assert d["contradicted_by"] == ["claim_005"]

    def test_confidence_valid_values(self):
        for conf in ["high", "medium", "low"]:
            c = Claim(
                claim_id=f"conf_{conf}",
                statement=f"{conf} confidence.",
                confidence=conf,
                status="active",
            )
            assert c.confidence == conf

    def test_status_valid_values(self):
        for status in ["active", "contested", "superseded", "resolved", "retracted", "stale"]:
            c = Claim(
                claim_id=f"status_{status}",
                statement=f"{status} claim.",
                confidence="medium",
                status=status,
            )
            assert c.status == status

    def test_claim_id_uniqueness_via_uuid(self):
        ids = set()
        for _ in range(100):
            cid = f"claim_{uuid.uuid4().hex[:12]}"
            assert cid not in ids
            ids.add(cid)
        assert len(ids) == 100

    def test_full_claim_types(self):
        for ct in ["fact", "interpretation", "definition", "decision", "metric", "hypothesis", "citation", "other"]:
            c = Claim(
                claim_id=f"ct_{ct}",
                statement=f"{ct} type claim.",
                confidence="medium",
                status="active",
                claim_type=ct,
            )
            assert c.claim_type == ct


# ── EpistemicEvent ─────────────────────────────────────────────────────────


class TestEpistemicEvent:
    VALID_EVENT_TYPES = [
        "created",
        "reinforced",
        "challenged",
        "weakened",
        "superseded",
        "resolved",
        "retracted",
    ]

    def test_creation_basic(self):
        evt = EpistemicEvent(
            claim_id="claim_001",
            event_type="created",
            source="source1.md",
        )
        assert evt.claim_id == "claim_001"
        assert evt.event_type == "created"
        assert evt.source == "source1.md"
        assert evt.event_id.startswith("evt_")
        assert len(evt.event_id) > 4
        assert evt.timestamp != ""

    def test_all_event_types(self):
        for et in self.VALID_EVENT_TYPES:
            evt = EpistemicEvent(
                claim_id="claim_001",
                event_type=et,
                source="test.md",
            )
            assert evt.event_type == et

    def test_event_id_uniqueness(self):
        ids = set()
        for _ in range(100):
            evt = EpistemicEvent(
                claim_id="claim_001",
                event_type="created",
                source="test.md",
            )
            assert evt.event_id not in ids
            ids.add(evt.event_id)
        assert len(ids) == 100

    def test_custom_timestamp(self):
        ts = "2026-06-15T08:00:00+00:00"
        evt = EpistemicEvent(
            claim_id="claim_001",
            event_type="reinforced",
            source="source2.md",
            timestamp=ts,
        )
        assert evt.timestamp == ts

    def test_custom_event_id(self):
        custom_id = "evt_custom123"
        evt = EpistemicEvent(
            claim_id="claim_001",
            event_type="challenged",
            source="audit.md",
            event_id=custom_id,
        )
        assert evt.event_id == custom_id

    def test_serialization(self):
        evt = EpistemicEvent(
            claim_id="claim_001",
            event_type="reinforced",
            source="new_source.md",
            operation_id="op_abc123",
        )
        d = evt.__dict__
        assert d["claim_id"] == "claim_001"
        assert d["event_type"] == "reinforced"
        assert d["source"] == "new_source.md"
        assert d["operation_id"] == "op_abc123"


# ── Contradiction ──────────────────────────────────────────────────────────


class TestContradiction:
    def test_creation_basic(self):
        ctr = Contradiction(
            contradiction_id="ctr_001",
            claim_ids=["claim_001", "claim_002"],
            status="open",
            severity="high",
        )
        assert ctr.contradiction_id == "ctr_001"
        assert ctr.claim_ids == ["claim_001", "claim_002"]
        assert ctr.status == "open"
        assert ctr.severity == "high"
        assert ctr.evidence == []
        assert ctr.resolution == ""

    def test_auto_generated_id(self):
        ctr = Contradiction(
            contradiction_id="",
            claim_ids=["claim_a"],
            status="open",
            severity="low",
        )
        assert ctr.contradiction_id.startswith("ctr_")
        assert len(ctr.contradiction_id) > 4

    def test_timestamps(self):
        ts = "2026-07-01T00:00:00+00:00"
        ctr = Contradiction(
            contradiction_id="ctr_002",
            claim_ids=["claim_001", "claim_003"],
            status="investigating",
            severity="medium",
            created_at=ts,
        )
        assert ctr.created_at == ts

    def test_all_statuses(self):
        for status in ["open", "investigating", "resolved", "false_positive", "wont_fix"]:
            ctr = Contradiction(
                contradiction_id=f"ctr_{status}",
                claim_ids=["claim_001", "claim_002"],
                status=status,
                severity="medium",
            )
            assert ctr.status == status

    def test_all_severities(self):
        for sev in ["low", "medium", "high", "blocking"]:
            ctr = Contradiction(
                contradiction_id=f"ctr_sev_{sev}",
                claim_ids=["claim_001"],
                status="open",
                severity=sev,
            )
            assert ctr.severity == sev

    def test_evidence_and_resolution(self):
        ctr = Contradiction(
            contradiction_id="ctr_003",
            claim_ids=["claim_a", "claim_b"],
            status="resolved",
            severity="high",
            evidence=["audit/2026/review.md", "reports/source_check.json"],
            resolution="Claim B was based on outdated data; superseded by claim C.",
        )
        assert len(ctr.evidence) == 2
        assert "outdated data" in ctr.resolution

    def test_serialization(self):
        ctr = Contradiction(
            contradiction_id="ctr_004",
            claim_ids=["claim_x", "claim_y"],
            status="open",
            severity="blocking",
            evidence=["src1.md"],
            resolution="Pending investigation.",
        )
        d = ctr.__dict__
        assert d["claim_ids"] == ["claim_x", "claim_y"]
        assert d["severity"] == "blocking"


# ── Jsonl helpers ──────────────────────────────────────────────────────────


class TestJsonlHelpers:
    def test_append_and_read(self, tmp_path):
        path = tmp_path / "test.jsonl"
        _jsonl_append(str(path), {"a": 1})
        _jsonl_append(str(path), {"b": 2})
        records = _jsonl_read_all(str(path))
        assert len(records) == 2
        assert records[0] == {"a": 1}
        assert records[1] == {"b": 2}

    def test_read_empty(self, tmp_path):
        path = tmp_path / "nonexistent.jsonl"
        records = _jsonl_read_all(str(path))
        assert records == []

    def test_read_skips_malformed(self, tmp_path):
        path = tmp_path / "malformed.jsonl"
        path.write_text('{"valid": 1}\nnot json at all\n{"also": 2}\n')
        records = _jsonl_read_all(str(path))
        assert len(records) == 2
        assert records[0] == {"valid": 1}
        assert records[1] == {"also": 2}


# ── Sidecar directory ─────────────────────────────────────────────────────


class TestSidecarDir:
    def test_ensure_creates(self, tmp_path):
        wiki = tmp_path / "test-wiki"
        d = _ensure_sidecar_dir(str(wiki))
        assert os.path.isdir(d)
        assert SIDECAR_DIR in d
        assert "claims" in d

    def test_ensure_idempotent(self, tmp_path):
        wiki = tmp_path / "test-wiki"
        d1 = _ensure_sidecar_dir(str(wiki))
        d2 = _ensure_sidecar_dir(str(wiki))
        assert d1 == d2
        assert os.path.isdir(d1)


# ── ClaimsManager ──────────────────────────────────────────────────────────


class TestClaimsManager:
    @pytest.fixture
    def mgr(self, tmp_path):
        wiki = tmp_path / "test-wiki"
        wiki.mkdir(parents=True)
        return ClaimsManager(str(wiki))

    def test_paths_exist(self, mgr):
        assert mgr.claims_path.endswith("claims.jsonl")
        assert mgr.events_path.endswith("events.jsonl")
        assert mgr.contradictions_path.endswith("contradictions.jsonl")

    def test_create_claim(self, mgr):
        c = Claim(
            claim_id="c001",
            statement="Test claim.",
            confidence="high",
            status="active",
            sources=["source1.pdf"],
            pages=["page1.md"],
            first_seen_operation_id="op_001",
        )
        mgr.create_claim(c)
        claims = mgr.get_all_claims()
        assert len(claims) == 1
        assert claims[0]["claim_id"] == "c001"
        assert claims[0]["confidence"] == "high"

    def test_create_claim_emits_event(self, mgr):
        c = Claim(
            claim_id="c002",
            statement="Emits event.",
            confidence="medium",
            status="active",
            sources=["src.md"],
            first_seen_operation_id="op_002",
        )
        mgr.create_claim(c)
        events = mgr.get_all_events()
        assert len(events) >= 1
        created_event = events[0]
        assert created_event["claim_id"] == "c002"
        assert created_event["event_type"] == "created"

    def test_emit_event(self, mgr):
        evt = EpistemicEvent(
            claim_id="c001",
            event_type="reinforced",
            source="new_source.md",
            operation_id="op_003",
        )
        mgr.emit_event(evt)
        events = mgr.get_all_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "reinforced"

    def test_create_contradiction(self, mgr):
        ctr = Contradiction(
            contradiction_id="ctr_001",
            claim_ids=["c001", "c002"],
            status="open",
            severity="high",
        )
        mgr.create_contradiction(ctr)
        contradictions = mgr.get_all_contradictions()
        assert len(contradictions) == 1
        assert contradictions[0]["contradiction_id"] == "ctr_001"

    def test_get_active_claims(self, mgr):
        mgr.create_claim(Claim(
            claim_id="active_1", statement="Active.", confidence="high", status="active",
        ))
        mgr.create_claim(Claim(
            claim_id="resolved_1", statement="Resolved.", confidence="high", status="resolved",
        ))
        active = mgr.get_active_claims()
        assert len(active) == 1
        assert active[0]["claim_id"] == "active_1"

    def test_get_open_contradictions(self, mgr):
        mgr.create_contradiction(Contradiction(
            contradiction_id="ctr_op", claim_ids=["c_a"], status="open", severity="medium",
        ))
        mgr.create_contradiction(Contradiction(
            contradiction_id="ctr_resolved", claim_ids=["c_b"], status="resolved", severity="low",
        ))
        mgr.create_contradiction(Contradiction(
            contradiction_id="ctr_investigating", claim_ids=["c_c"], status="investigating", severity="high",
        ))
        open_ctrs = mgr.get_open_contradictions()
        assert len(open_ctrs) == 2
        ids = {c["contradiction_id"] for c in open_ctrs}
        assert "ctr_op" in ids
        assert "ctr_investigating" in ids
        assert "ctr_resolved" not in ids

    def test_get_claims_by_page(self, mgr):
        mgr.create_claim(Claim(
            claim_id="c_p1", statement="On page1.", confidence="medium", status="active",
            pages=["page1.md"],
        ))
        mgr.create_claim(Claim(
            claim_id="c_p2", statement="On page2.", confidence="medium", status="active",
            pages=["page2.md"],
        ))
        p1_claims = mgr.get_claims_by_page("page1.md")
        assert len(p1_claims) == 1
        assert p1_claims[0]["claim_id"] == "c_p1"

    def test_get_claims_by_status(self, mgr):
        mgr.create_claim(Claim(
            claim_id="s_stale", statement="Stale.", confidence="low", status="stale",
        ))
        stale = mgr.get_claims_by_status("stale")
        assert len(stale) == 1
        assert stale[0]["claim_id"] == "s_stale"

    def test_get_stale_claims(self, mgr):
        old_ts = "2023-01-01T00:00:00+00:00"
        mgr.create_claim(Claim(
            claim_id="stale_1", statement="Old claim.", confidence="medium",
            status="active", updated_at=old_ts,
        ))
        mgr.create_claim(Claim(
            claim_id="fresh_1", statement="Fresh claim.", confidence="high",
            status="active",
        ))
        stale = mgr.get_stale_claims(staleness_days=180)
        assert len(stale) == 1
        assert stale[0]["claim_id"] == "stale_1"

    def test_multiple_claims(self, mgr):
        for i in range(10):
            mgr.create_claim(Claim(
                claim_id=f"multi_{i}", statement=f"Claim {i}.",
                confidence="medium", status="active",
            ))
        assert len(mgr.get_all_claims()) == 10


# ── Health report ──────────────────────────────────────────────────────────


class TestHealthReport:
    def test_empty_health_report(self, tmp_path):
        wiki = tmp_path / "empty-wiki"
        wiki.mkdir(parents=True)
        mgr = ClaimsManager(str(wiki))
        report = mgr.health_report()
        assert report["total_claims"] == 0
        assert report["total_events"] == 0
        assert report["total_contradictions"] == 0
        assert report["open_contradictions"] == 0
        assert report["stale_claims"] == 0
        assert report["pages_with_claims"] == 0
        assert report["active_claims"] == 0

    def test_report_with_data(self, tmp_path):
        wiki = tmp_path / "populated-wiki"
        wiki.mkdir(parents=True)
        mgr = ClaimsManager(str(wiki))

        mgr.create_claim(Claim(
            claim_id="c_a", statement="Claim A.", confidence="high",
            status="active", pages=["page1.md", "page2.md"],
        ))
        mgr.create_claim(Claim(
            claim_id="c_b", statement="Claim B.", confidence="medium",
            status="contested", pages=["page1.md"],
        ))
        mgr.create_contradiction(Contradiction(
            contradiction_id="ctr_1", claim_ids=["c_a", "c_b"],
            status="open", severity="high",
        ))

        report = mgr.health_report()
        assert report["total_claims"] == 2
        assert report["total_events"] == 2  # both create_claim emits events
        assert report["total_contradictions"] == 1
        assert report["open_contradictions"] == 1
        assert report["pages_with_claims"] == 2
        assert report["active_claims"] == 1

    def test_report_is_json_serializable(self, tmp_path):
        wiki = tmp_path / "json-wiki"
        wiki.mkdir(parents=True)
        mgr = ClaimsManager(str(wiki))
        mgr.create_claim(Claim(
            claim_id="json_test", statement="JSON test.", confidence="low",
            status="active",
        ))
        report = mgr.health_report()
        serialized = json.dumps(report)
        parsed = json.loads(serialized)
        assert parsed["total_claims"] == 1


# ── Diff ───────────────────────────────────────────────────────────────────


class TestDiff:
    def test_empty_diff(self, tmp_path):
        wiki_a = tmp_path / "wiki-a"
        wiki_b = tmp_path / "wiki-b"
        mgr_a = ClaimsManager(str(wiki_a))
        mgr_b = ClaimsManager(str(wiki_b))
        diff = mgr_a.diff(mgr_b)
        assert diff["added"] == 0
        assert diff["removed"] == 0
        assert diff["changed"] == 0

    def test_added_claims(self, tmp_path):
        wiki_a = tmp_path / "wiki-a"
        wiki_b = tmp_path / "wiki-b"
        mgr_a = ClaimsManager(str(wiki_a))
        mgr_b = ClaimsManager(str(wiki_b))

        mgr_a.create_claim(Claim(
            claim_id="new_1", statement="A new claim in A.", confidence="high", status="active",
        ))

        diff = mgr_a.diff(mgr_b)
        assert diff["added"] == 1
        assert len(diff["added_details"]) == 1
        assert diff["added_details"][0]["claim_id"] == "new_1"

    def test_removed_claims(self, tmp_path):
        wiki_a = tmp_path / "wiki-a"
        wiki_b = tmp_path / "wiki-b"
        mgr_a = ClaimsManager(str(wiki_a))
        mgr_b = ClaimsManager(str(wiki_b))

        mgr_b.create_claim(Claim(
            claim_id="only_in_b", statement="Only in B.", confidence="medium", status="active",
        ))

        diff = mgr_a.diff(mgr_b)
        assert diff["removed"] == 1
        assert len(diff["removed_details"]) == 1
        assert diff["removed_details"][0]["claim_id"] == "only_in_b"

    def test_changed_status(self, tmp_path):
        wiki_a = tmp_path / "wiki-a"
        wiki_b = tmp_path / "wiki-b"
        mgr_a = ClaimsManager(str(wiki_a))
        mgr_b = ClaimsManager(str(wiki_b))

        mgr_a.create_claim(Claim(
            claim_id="shared", statement="Shared claim.", confidence="high",
            status="resolved",
        ))
        mgr_b.create_claim(Claim(
            claim_id="shared", statement="Shared claim.", confidence="medium",
            status="active",
        ))

        diff = mgr_a.diff(mgr_b)
        assert diff["changed"] == 1
        assert diff["changed_details"][0]["claim_id"] == "shared"


# ── Sidecar-free behavior ──────────────────────────────────────────────────


class TestSidecarFree:
    def test_no_sidecar_on_empty_wiki(self, tmp_path):
        wiki = tmp_path / "no-sidecar-wiki"
        wiki.mkdir(parents=True)
        assert not has_sidecar(str(wiki))

    def test_claims_manager_no_sidecar_creates(self, tmp_path):
        wiki = tmp_path / "fresh-wiki"
        wiki.mkdir(parents=True)
        mgr = ClaimsManager(str(wiki))
        assert os.path.isdir(mgr.sidecar_dir)

    def test_get_all_claims_empty_without_sidecar(self, tmp_path):
        wiki = tmp_path / "no-claims-wiki"
        wiki.mkdir(parents=True)
        mgr = ClaimsManager(str(wiki))
        claims = mgr.get_all_claims()
        assert claims == []

    def test_health_report_no_errors(self, tmp_path):
        wiki = tmp_path / "health-wiki"
        wiki.mkdir(parents=True)
        mgr = ClaimsManager(str(wiki))
        report = mgr.health_report()
        assert isinstance(report, dict)
        assert report["total_claims"] == 0


# ── CLI commands ───────────────────────────────────────────────────────────


class TestCmdHealth:
    def test_health_no_sidecar(self, tmp_path, capsys):
        wiki = tmp_path / "no-sidecar"
        wiki.mkdir(parents=True)
        rc = cmd_health(str(wiki))
        assert rc == 0
        captured = capsys.readouterr()
        assert "No claim sidecar found" in captured.out

    def test_health_with_claims(self, tmp_path, capsys):
        wiki = tmp_path / "with-claims"
        wiki.mkdir(parents=True)
        mgr = ClaimsManager(str(wiki))
        mgr.create_claim(Claim(
            claim_id="h_c1", statement="Health test claim.", confidence="high",
            status="active",
        ))
        mgr.create_claim(Claim(
            claim_id="h_c2", statement="Health test claim 2.", confidence="medium",
            status="active",
        ))
        rc = cmd_health(str(wiki))
        assert rc == 0
        captured = capsys.readouterr()
        assert "Total claims:" in captured.out
        assert "2" in captured.out


class TestCmdDiff:
    def test_diff_no_changes(self, tmp_path, capsys):
        wiki_a = tmp_path / "diff-a"
        wiki_b = tmp_path / "diff-b"
        rc = cmd_diff(str(wiki_a), str(wiki_b))
        assert rc == 0
        captured = capsys.readouterr()
        assert "Added:" in captured.out
        assert "0" in captured.out

    def test_diff_with_changes(self, tmp_path, capsys):
        wiki_a = tmp_path / "diff-a"
        wiki_b = tmp_path / "diff-b"
        mgr_a = ClaimsManager(str(wiki_a))
        mgr_a.create_claim(Claim(
            claim_id="diff_c1", statement="New claim for diff.", confidence="low",
            status="active",
        ))
        rc = cmd_diff(str(wiki_a), str(wiki_b))
        assert rc == 1
        captured = capsys.readouterr()
        assert "Added:" in captured.out
        assert "1" in captured.out
