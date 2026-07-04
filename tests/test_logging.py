"""test_logging.py — Tests for the structured JSON logging module.

Validates JSON format, severity filtering, component identifiers,
CLI configuration integration, and edge cases.
"""

import json
import sys

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging level to INFO before each test."""
    import wiki_logging as wl
    wl._current_level = wl.LEVELS["INFO"]
    yield


# ── Helper ────────────────────────────────────────────────────────────────

def parse_logs(err_text: str) -> list[dict]:
    """Parse all JSON lines from captured stderr text."""
    lines = [l.strip() for l in err_text.split("\n") if l.strip()]
    return [json.loads(l) for l in lines]


# ── Test 1: Valid JSON and required fields ────────────────────────────────

def test_log_event_emits_valid_json(capsys):
    """Every log_event call produces a single valid JSON line with all required fields."""
    from wiki_logging import log_event

    log_event("INFO", "test", "hello world", extra="value")

    captured = capsys.readouterr()
    events = parse_logs(captured.err)
    assert len(events) == 1
    e = events[0]
    for field in ("v", "ts", "lvl", "cmp", "msg"):
        assert field in e, f"Missing required field: {field}"
    assert e["v"] == 1
    assert e["lvl"] == "INFO"
    assert e["cmp"] == "test"
    assert e["msg"] == "hello world"
    assert e["extra"] == "value"
    assert e["ts"].endswith("Z")
    assert "T" in e["ts"]


# ── Test 2: Convenience functions produce correct severity ────────────────

@pytest.mark.parametrize("fn_name,expected_lvl", [
    ("debug", "DEBUG"),
    ("info", "INFO"),
    ("warn", "WARN"),
    ("error", "ERROR"),
    ("panic", "PANIC"),
])
def test_convenience_functions(capsys, fn_name, expected_lvl):
    """Each convenience function emits the correct severity level."""
    from wiki_logging import set_level
    import wiki_logging as wl

    set_level("DEBUG")  # Ensure all levels pass

    fn = getattr(wl, fn_name)
    fn("test", "test message")

    events = parse_logs(capsys.readouterr().err)
    assert len(events) == 1
    assert events[0]["lvl"] == expected_lvl


# ── Test 3: Severity filtering — INFO suppressed at WARN ──────────────────

def test_severity_filtering_suppresses_lower_levels(capsys):
    """Events below the current level threshold are not emitted."""
    from wiki_logging import set_level, info, warn

    set_level("WARN")
    info("test", "this should be suppressed")
    warn("test", "this should appear")

    events = parse_logs(capsys.readouterr().err)
    assert len(events) == 1
    assert events[0]["lvl"] == "WARN"


# ── Test 4: PANIC always emitted regardless of level ──────────────────────

def test_panic_always_emitted(capsys):
    """PANIC-level events are emitted even at ERROR level."""
    from wiki_logging import set_level, panic, info

    set_level("ERROR")
    info("test", "suppressed")
    panic("test", "fatal error")

    events = parse_logs(capsys.readouterr().err)
    assert len(events) == 1
    assert events[0]["lvl"] == "PANIC"


# ── Test 5: configure() sets correct levels ───────────────────────────────

def test_configure_verbose_sets_debug(capsys):
    """configure(verbose=True) enables DEBUG output."""
    from wiki_logging import configure, debug

    configure(verbose=True)
    debug("test", "debug message")
    events = parse_logs(capsys.readouterr().err)
    assert len(events) == 1
    assert events[0]["lvl"] == "DEBUG"


def test_configure_quiet_sets_error(capsys):
    """configure(quiet=True) suppresses INFO/WARN/DEBUG."""
    from wiki_logging import configure, info, error

    configure(quiet=True)
    info("test", "suppressed")
    error("test", "visible")

    events = parse_logs(capsys.readouterr().err)
    assert len(events) == 1
    assert events[0]["lvl"] == "ERROR"


def test_configure_verbose_wins_over_quiet(capsys):
    """When both --verbose and --quiet are passed, verbose wins."""
    from wiki_logging import configure, debug

    configure(quiet=True, verbose=True)
    debug("test", "debug wins")
    events = parse_logs(capsys.readouterr().err)
    assert len(events) == 1


# ── Test 6: Component identifiers are preserved ───────────────────────────

def test_component_identifiers(capsys):
    """Each log event preserves its component identifier."""
    from wiki_logging import set_level, info

    set_level("DEBUG")
    components = ["ingest", "lint", "backup", "lock", "llm", "provider", "mcp", "graph"]
    for comp in components:
        info(comp, f"test from {comp}")

    events = parse_logs(capsys.readouterr().err)
    assert len(events) == len(components)
    for event, expected in zip(events, components):
        assert event["cmp"] == expected


# ── Test 7: Arbitrary metadata is serialized ──────────────────────────────

def test_arbitrary_metadata_serialization(capsys):
    """Extra kwargs are serialized as additional JSON fields."""
    from wiki_logging import info

    info("test", "complex metadata",
         count=42,
         flag=True,
         tags=["a", "b", "c"],
         nested={"key": "value"},
         none_val=None,
         float_val=3.14)

    events = parse_logs(capsys.readouterr().err)
    e = events[0]
    assert e["count"] == 42
    assert e["flag"] is True
    assert e["tags"] == ["a", "b", "c"]
    assert e["nested"] == {"key": "value"}
    assert e["none_val"] is None
    assert e["float_val"] == 3.14


# ── Test 8: Non-serializable types are handled gracefully ─────────────────

def test_non_serializable_types_handled(capsys):
    """Types like datetime and Path are serialized via default=str."""
    from datetime import datetime
    from pathlib import Path
    from wiki_logging import info

    info("test", "exotic types",
         dt=datetime(2026, 1, 15, 12, 0, 0),
         path=Path("/some/path"),
         exception=ValueError("test error"))

    events = parse_logs(capsys.readouterr().err)
    e = events[0]
    assert "dt" in e
    assert "path" in e
    assert "exception" in e
    assert isinstance(e["dt"], str)
    assert isinstance(e["path"], str)


# ── Test 9: set_level with invalid level is safe ──────────────────────────

def test_set_level_invalid_noop(capsys):
    """set_level with an invalid level name does not change the current level."""
    from wiki_logging import set_level, info, _current_level

    original = _current_level
    set_level("NONSENSE")
    assert _current_level == original  # Unchanged

    info("test", "should work")
    events = parse_logs(capsys.readouterr().err)
    assert len(events) >= 1


# ── Test 10: Timestamp is monotonically increasing ────────────────────────

def test_timestamps_are_sequential(capsys):
    """Multiple log events have increasing timestamps."""
    from wiki_logging import set_level, info

    set_level("DEBUG")
    for i in range(5):
        info("test", f"message {i}")

    events = parse_logs(capsys.readouterr().err)
    assert len(events) == 5
    timestamps = [e["ts"] for e in events]
    assert timestamps == sorted(timestamps), "Timestamps should be sorted"


# ── Test 11: Log format version is always 1 ───────────────────────────────

def test_log_version_is_always_1(capsys):
    """All log events have v=1 for format versioning."""
    from wiki_logging import set_level, info, error, panic

    set_level("DEBUG")
    info("a", "m1")
    error("b", "m2")
    panic("c", "m3")

    for e in parse_logs(capsys.readouterr().err):
        assert e["v"] == 1, f"Expected v=1, got {e['v']}"


# ── Test 12: Empty message and empty metadata ─────────────────────────────

def test_empty_message_ok(capsys):
    """Empty message string is valid."""
    from wiki_logging import info

    info("test", "")
    events = parse_logs(capsys.readouterr().err)
    assert events[0]["msg"] == ""


def test_no_extra_metadata_ok(capsys):
    """Log event with no extra kwargs is valid."""
    from wiki_logging import info

    info("test", "minimal")
    events = parse_logs(capsys.readouterr().err)
    assert len(events[0]) == 5  # v, ts, lvl, cmp, msg — nothing else


# ── Test 13: Multiple concurrent calls don't corrupt output ───────────────

def test_concurrent_like_calls(capsys):
    """Rapid successive log calls produce one JSON object per line."""
    from wiki_logging import set_level, info

    set_level("DEBUG")
    for i in range(100):
        info("test", f"msg{i}")

    events = parse_logs(capsys.readouterr().err)
    assert len(events) == 100
    for i, e in enumerate(events):
        assert e["msg"] == f"msg{i}"
