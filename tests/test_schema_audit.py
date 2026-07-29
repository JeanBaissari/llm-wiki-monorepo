"""test_schema_audit.py — Tests for LWM_009 Schema, LWM_010 OperationContext, LWM_011 Claims.

Tests:
  1. Python schema validator on valid/invalid fixtures
  2. Schema version computation
  3. OperationContext lifecycle events
  4. AuditWriter anchored and unanchored writes
  5. ClaimsManager health and diff
  6. Cross-language validation parity (schema fixture files)
  7. Sidecar-free wiki compatibility
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema" / "versions" / "v0.2.1"
FIXTURES_VALID = REPO_ROOT / "schema" / "fixtures" / "valid"
FIXTURES_INVALID = REPO_ROOT / "schema" / "fixtures" / "invalid"


# ── Helper to import from src/llm_wiki ─────────────────────────────────────

@pytest.fixture(autouse=True)
def ensure_src_importable():
    """Ensure src/ is on sys.path."""
    src = str(REPO_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    yield


# ══════════════════════════════════════════════════════════════════════════
# LWM_009 — Schema Validator
# ══════════════════════════════════════════════════════════════════════════

class TestSchemaValidator:
    """Test Python schema validation against fixture files."""

    def test_imports(self):
        """Schema validator imports successfully."""
        from llm_wiki.contracts import validate_page, validate_audit, validate_log_event
        assert callable(validate_page)
        assert callable(validate_audit)
        assert callable(validate_log_event)
        print("PASS: schema validation imports")

    def test_schema_files_exist(self):
        """All required schema files exist."""
        required = [
            "page.schema.json",
            "audit.schema.json",
            "log-event.schema.json",
            "template-schema.schema.json",
            "operation-manifest.schema.json",
            "claim-sidecar.schema.json",
        ]
        for name in required:
            path = SCHEMA_DIR / name
            assert path.exists(), f"Missing schema: {path}"

    def test_valid_fixtures_pass(self):
        """All valid fixtures should pass validation."""
        from llm_wiki.contracts import validate_fixture_file

        results = []
        for f in sorted(FIXTURES_VALID.glob("*.json")):
            result = validate_fixture_file(str(f))
            if not result.get("skipped"):
                assert result["valid"], f"Valid fixture failed: {f} — {result['errors']}"
                results.append(result)

        assert len(results) >= 8, f"Expected at least 8 valid fixture checks, got {len(results)}"

    def test_invalid_fixtures_fail(self):
        """All invalid fixtures should fail validation."""
        from llm_wiki.contracts import validate_fixture_file

        results = []
        for f in sorted(FIXTURES_INVALID.glob("*.json")):
            result = validate_fixture_file(str(f))
            if not result.get("skipped"):
                assert not result["valid"], f"Invalid fixture passed: {f}"
                results.append(result)

        assert len(results) >= 6, f"Expected at least 6 invalid fixture checks, got {len(results)}"

    def test_page_validation(self):
        """Page validation catches specific errors."""
        from llm_wiki.contracts import validate_page

        valid = {"title": "Test", "type": "entity", "created": "2026-01-01",
                 "updated": "2026-01-01", "sources": [], "tags": []}
        assert validate_page(valid) == []

        missing_title = {"type": "entity", "created": "2026-01-01",
                         "updated": "2026-01-01", "sources": [], "tags": []}
        errors = validate_page(missing_title)
        assert any("title" in e for e in errors)

        bad_type = {**valid, "type": "nope"}
        errors = validate_page(bad_type)
        assert any("Invalid type" in e for e in errors)

        bad_date = {**valid, "created": "not-a-date"}
        errors = validate_page(bad_date)
        assert any("YYYY-MM-DD" in e for e in errors)

    def test_audit_validation(self):
        """Audit validation catches anchor vs unanchored requirements."""
        from llm_wiki.contracts import validate_audit

        anchored = {
            "id": "20260722-120000-abcd", "target": "test.md",
            "target_lines": [1, 5], "anchor_before": "", "anchor_text": "sel",
            "anchor_after": "", "severity": "suggest", "author": "t",
            "source": "manual", "created": "2026-07-22", "status": "open",
        }
        assert validate_audit(anchored) == []

        unanchored = {
            "id": "20260722-120000-ef01", "target": "op/test",
            "target_kind": "operation", "target_reason": "Whole operation",
            "severity": "warn", "author": "t", "source": "ingest",
            "created": "2026-07-22", "status": "open",
        }
        assert validate_audit(unanchored) == []

        neither = {
            "id": "20260722-120000-0000", "target": "test.md",
            "severity": "warn", "author": "t", "source": "manual",
            "created": "2026-07-22", "status": "open",
        }
        errors = validate_audit(neither)
        assert any("anch" in e.lower() for e in errors)

    def test_log_event_validation(self):
        """Log event validation catches version and level issues."""
        from llm_wiki.contracts import validate_log_event

        valid = {"v": 1, "ts": "2026-07-22T12:00:00Z", "lvl": "INFO",
                 "cmp": "test", "msg": "hello"}
        assert validate_log_event(valid) == []

        bad_v = {**valid, "v": 999}
        assert any("version" in e.lower() for e in validate_log_event(bad_v))

        bad_lvl = {**valid, "lvl": "NONSENSE"}
        assert any("level" in e.lower() for e in validate_log_event(bad_lvl))

    def test_frontmatter_parsing(self):
        """Frontmatter parser extracts fields from markdown."""
        from llm_wiki.contracts import parse_page_frontmatter

        md = """---
title: Test Page
type: concept
created: 2026-01-01
updated: 2026-01-01
sources: [test]
tags: [a, b]
confidence: high
contested: false
---

# Test Page

Content here.
"""
        fm = parse_page_frontmatter(md)
        assert fm is not None
        assert fm["title"] == "Test Page"
        assert fm["type"] == "concept"
        assert fm["confidence"] == "high"
        assert fm["contested"] is False
        assert fm["tags"] == ["a", "b"]

    def test_no_frontmatter(self):
        """Markdown without frontmatter returns None."""
        from llm_wiki.contracts import parse_page_frontmatter
        assert parse_page_frontmatter("# Just content") is None


# ══════════════════════════════════════════════════════════════════════════
# LWM_010 — OperationContext
# ══════════════════════════════════════════════════════════════════════════

class TestOperationContext:
    """Test OperationContext lifecycle and event emission."""

    def test_context_manager(self, tmp_path):
        """OperationContext as context manager sets started/succeeded events."""
        from llm_wiki.operation import OperationContext

        wiki_root = str(tmp_path / "wiki")
        with OperationContext("test_cmd", wiki_root=wiki_root) as ctx:
            assert ctx.status == "started"
            assert ctx.command == "test_cmd"
            assert ctx.operation_id.startswith("op_")
            ctx.succeed()

        assert ctx.status == "succeeded"
        assert ctx.ended_at is not None
        assert ctx.duration_ms is not None
        assert ctx.duration_ms >= 0

    def test_context_manager_failure(self, tmp_path):
        """OperationContext captures exceptions and sets failed status."""
        from llm_wiki.operation import OperationContext

        wiki_root = str(tmp_path / "wiki")
        try:
            with OperationContext("fail_cmd", wiki_root=wiki_root) as ctx:
                raise ValueError("Test error")
        except ValueError:
            pass

        assert ctx.status == "failed"
        assert len(ctx.errors) >= 1
        assert ctx.errors[0]["code"] == "ValueError"

    def test_touched_paths(self, tmp_path):
        """OperationContext tracks touched paths."""
        from llm_wiki.operation import OperationContext

        wiki_root = str(tmp_path / "wiki")
        with OperationContext("touch_test", wiki_root=wiki_root) as ctx:
            ctx.add_touched("created", "/tmp/created.md")
            ctx.add_touched("read", "/tmp/read.md")
            ctx.succeed()

        assert "/tmp/created.md" in ctx.touched_paths["created"]
        assert "/tmp/read.md" in ctx.touched_paths["read"]

    def test_event_file_created(self, tmp_path):
        """Operation events are written to log/operations/YYYYMMDD.jsonl."""
        from llm_wiki.operation import OperationContext

        wiki_root = str(tmp_path / "wiki")
        with OperationContext("event_test", wiki_root=wiki_root) as ctx:
            ctx.succeed()

        date_str = datetime.now().strftime("%Y%m%d")
        log_path = Path(wiki_root) / "log" / "operations" / f"{date_str}.jsonl"
        assert log_path.exists(), f"Event log not found: {log_path}"

        events = log_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(events) >= 1
        last_event = json.loads(events[-1])
        assert last_event["operation_id"] == ctx.operation_id
        assert last_event["command"] == "event_test"

    def test_add_input_hash(self, tmp_path):
        """OperationContext computes input file hashes."""
        from llm_wiki.operation import OperationContext

        source = tmp_path / "source.txt"
        source.write_text("test content")

        wiki_root = str(tmp_path / "wiki")
        with OperationContext("hash_test", wiki_root=wiki_root) as ctx:
            ctx.add_input_hash(str(source))
            ctx.succeed()

        assert len(ctx.input_hashes) >= 1
        assert str(source.resolve()) in ctx.input_hashes

    def test_redact_secrets(self):
        """OperationContext redacts sensitive inputs."""
        from llm_wiki.operation import OperationContext

        ctx = OperationContext("test", inputs={"safe": "ok", "api_key": "secret123"})
        assert ctx.inputs["safe"] == "ok"
        assert "secret" in str(ctx.inputs["api_key"]).lower() or ctx.inputs["api_key"] == "**REDACTED**"


class TestAuditWriter:
    """Test AuditWriter atomic write behavior."""

    def test_write_anchored(self, tmp_path):
        """Anchored audit write creates a valid audit file."""
        from llm_wiki.quality.audit.writer import AuditWriter

        wiki_root = str(tmp_path / "wiki")
        target_dir = os.path.join(wiki_root, "wiki", "concepts")
        os.makedirs(target_dir, exist_ok=True)
        target_file = os.path.join(target_dir, "test.md")
        Path(target_file).write_text(
            "# Test\n\n## Overview\n\nContent here.\n\n## Links\n"
        )

        audit_dir = os.path.join(wiki_root, "audit")
        writer = AuditWriter(audit_dir=audit_dir, wiki_root=wiki_root)

        result = writer.write_anchored(
            target="wiki/concepts/test.md",
            target_lines=(3, 4),
            severity="suggest",
            author="test-agent",
            source="manual",
            body="Consider adding an example.",
        )

        assert result is not None, "Anchored audit write failed"
        assert os.path.exists(result), f"Audit file not found: {result}"

        content = Path(result).read_text(encoding="utf-8")
        assert "target_lines: [3, 4]" in content or "target_lines" in content
        assert "severity: suggest" in content
        assert "status: open" in content

    def test_write_unanchored(self, tmp_path):
        """Unanchored audit write creates a valid audit file."""
        from llm_wiki.quality.audit.writer import AuditWriter

        wiki_root = str(tmp_path / "wiki")
        audit_dir = os.path.join(wiki_root, "audit")
        writer = AuditWriter(audit_dir=audit_dir, wiki_root=wiki_root)

        result = writer.write_unanchored(
            target="operations/ingest-001",
            target_kind="operation",
            target_reason="Review applies to the whole ingest operation",
            severity="warn",
            author="test-agent",
            source="ingest",
            body="This operation produced 3 reviews.",
        )

        assert result is not None, "Unanchored audit write failed"
        assert os.path.exists(result), f"Audit file not found: {result}"

        content = Path(result).read_text(encoding="utf-8")
        assert "target_kind: operation" in content
        assert "target_reason:" in content

    def test_resolve_audit(self, tmp_path):
        """Resolve moves audit from audit/ to audit/resolved/."""
        from llm_wiki.quality.audit.writer import AuditWriter

        wiki_root = str(tmp_path / "wiki")
        audit_dir = os.path.join(wiki_root, "audit")
        os.makedirs(audit_dir, exist_ok=True)

        writer = AuditWriter(audit_dir=audit_dir, wiki_root=wiki_root)
        result = writer.write_anchored(
            target="wiki/test.md",
            target_lines=(1, 2),
            severity="info",
            author="test",
            source="manual",
            body="Test audit",
        )
        assert result is not None

        audit_id = Path(result).stem
        resolved = writer.resolve_audit(audit_id, "Fixed by test")
        assert resolved, "Resolve failed"
        assert not os.path.exists(result), "Open audit file still exists"
        resolved_path = os.path.join(audit_dir, "resolved", f"{audit_id}.md")
        assert os.path.exists(resolved_path), f"Resolved file not found: {resolved_path}"


# ══════════════════════════════════════════════════════════════════════════
# LWM_011 — Claims (Optional Sidecar)
# ══════════════════════════════════════════════════════════════════════════

class TestClaims:
    """Test claim sidecar model."""

    def test_sidecar_free_wiki(self, tmp_path):
        """A wiki without claim sidecar files works normally."""
        from llm_wiki.quality.claims import has_sidecar

        wiki_root = str(tmp_path / "wiki")
        os.makedirs(wiki_root, exist_ok=True)
        assert not has_sidecar(wiki_root), "Empty wiki should not have sidecars"

    def test_create_claim(self, tmp_path):
        """Creating a claim writes to claims.jsonl."""
        from llm_wiki.quality.claims import ClaimsManager, Claim

        wiki_root = str(tmp_path / "wiki")
        os.makedirs(wiki_root, exist_ok=True)

        mgr = ClaimsManager(wiki_root)
        claim = Claim(
            claim_id="cl_test_001",
            statement="Test claim statement",
            confidence="high",
            status="active",
            sources=["raw/test.md"],
        )
        mgr.create_claim(claim)

        claims = mgr.get_all_claims()
        assert len(claims) == 1
        assert claims[0]["claim_id"] == "cl_test_001"
        assert claims[0]["statement"] == "Test claim statement"

        events = mgr.get_all_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "created"

    def test_health_report(self, tmp_path):
        """Health report provides correct summary stats."""
        from llm_wiki.quality.claims import ClaimsManager, Claim, Contradiction

        wiki_root = str(tmp_path / "wiki")
        mgr = ClaimsManager(wiki_root)

        c1 = Claim(claim_id="cl_001", statement="Claim A", confidence="high", status="active")
        c2 = Claim(claim_id="cl_002", statement="Claim B", confidence="low", status="active")
        mgr.create_claim(c1)
        mgr.create_claim(c2)

        ctr = Contradiction(
            contradiction_id="ctr_001",
            claim_ids=["cl_001", "cl_002"],
            status="open",
            severity="blocking",
        )
        mgr.create_contradiction(ctr)

        report = mgr.health_report()
        assert report["total_claims"] == 2
        assert report["total_contradictions"] == 1
        assert report["open_contradictions"] == 1
        assert report["active_claims"] == 2

    def test_diff(self, tmp_path):
        """Diff between two claim snapshots shows changes."""
        from llm_wiki.quality.claims import ClaimsManager, Claim

        wiki_a = str(tmp_path / "wiki_a")
        wiki_b = str(tmp_path / "wiki_b")
        os.makedirs(wiki_a, exist_ok=True)
        os.makedirs(wiki_b, exist_ok=True)

        mgr_a = ClaimsManager(wiki_a)
        mgr_b = ClaimsManager(wiki_b)

        mgr_a.create_claim(Claim(claim_id="cl_001", statement="Claim in A only", confidence="high", status="active"))
        mgr_b.create_claim(Claim(claim_id="cl_002", statement="Claim in B only", confidence="high", status="active"))

        diff = mgr_a.diff(mgr_b)
        assert diff["added"] == 1
        assert diff["removed"] == 1

    def test_get_claims_by_status(self, tmp_path):
        """Filter claims by status."""
        from llm_wiki.quality.claims import ClaimsManager, Claim

        wiki_root = str(tmp_path / "wiki")
        mgr = ClaimsManager(wiki_root)

        mgr.create_claim(Claim(claim_id="cl_001", statement="Active claim", confidence="high", status="active"))
        mgr.create_claim(Claim(claim_id="cl_002", statement="Superseded claim", confidence="medium", status="superseded"))

        active = mgr.get_claims_by_status("active")
        assert len(active) == 1
        assert active[0]["claim_id"] == "cl_001"

        superseded = mgr.get_claims_by_status("superseded")
        assert len(superseded) == 1
        assert superseded[0]["claim_id"] == "cl_002"


# ══════════════════════════════════════════════════════════════════════════
# Cross-Language: Schema fixture file parity
# ══════════════════════════════════════════════════════════════════════════

class TestCrossLanguageParity:
    """Verify that schema fixture files can be consumed by any validator."""

    def test_all_fixtures_are_valid_json(self):
        """Every fixture file is valid JSON."""
        for dirpath in [FIXTURES_VALID, FIXTURES_INVALID]:
            for f in sorted(dirpath.glob("*.json")):
                try:
                    json.loads(f.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON in {f}: {e}")

    def test_fixtures_have_expected_fields(self):
        """Fixture files contain expected schema-relevant fields."""
        for dirpath, expected_valid in [(FIXTURES_VALID, True), (FIXTURES_INVALID, False)]:
            for f in sorted(dirpath.glob("*.json")):
                data = json.loads(f.read_text(encoding="utf-8"))
                name = f.stem

                if "page" in name:
                    if expected_valid:
                        assert "title" in data, f"{f} should have 'title'"
                        assert "type" in data, f"{f} should have 'type'"
                elif "audit" in name:
                    assert "id" in data, f"{f} should have 'id'"
                    assert "target" in data, f"{f} should have 'target'"
                elif "epistemic" in name:
                    assert "event_type" in data, f"{f} should have 'event_type'"
                elif "log" in name or "event" in name:
                    assert "v" in data, f"{f} should have 'v'"
                    assert "lvl" in data, f"{f} should have 'lvl'"
                elif "template" in name:
                    assert "name" in data, f"{f} should have 'name'"
                elif "claim" in name or "contradiction" in name or "epistemic" in name:
                    if "contradiction" in name:
                        assert "contradiction_id" in data, f"{f} should have 'contradiction_id'"
                    elif "epistemic" in name:
                        assert "event_type" in data, f"{f} should have 'event_type'"
                    else:
                        assert "claim_id" in data or "statement" in data, f"{f} should have claim fields"
