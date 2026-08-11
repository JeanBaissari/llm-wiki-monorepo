"""Standing per-minor gold-set curation loop tests (LWM_039 §A / Lane-G).

Covers ``scripts/curate_gold_set.py`` (check / freeze / rebaseline /
growth-record) and the ``gate_search_goldset_fresh`` release-certify gate.
The frozen committed files (search_goldset.json, split_manifest.json,
search_eval_baseline.json) are never rewritten here — fixtures are copies in
tmp dirs and the check/gate functions accept an explicit repo root.
"""

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import curate_gold_set  # noqa: E402
import release_certify  # noqa: E402

GOLD_DIR = REPO_ROOT / "tests" / "eval" / "gold"
GOLDSET = GOLD_DIR / "search_goldset.json"
MANIFEST = GOLD_DIR / "split_manifest.json"
GROWTH_META = GOLD_DIR / "growth_meta.json"
BASELINE = REPO_ROOT / "tests" / "eval" / "baseline" / "search_eval_baseline.json"

_MIN_FLOOR = 16


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_gold_fixture(tmp_path: Path) -> Path:
    """Copy the real gold dir into a tmp fixture repo root (tests/eval/gold/)."""
    fixture = tmp_path / "fixture"
    dst = fixture / "tests" / "eval" / "gold"
    dst.mkdir(parents=True)
    (dst / "search_goldset.json").write_text(GOLDSET.read_text(encoding="utf-8"),
                                             encoding="utf-8")
    (dst / "split_manifest.json").write_text(MANIFEST.read_text(encoding="utf-8"),
                                             encoding="utf-8")
    (dst / "growth_meta.json").write_text(GROWTH_META.read_text(encoding="utf-8"),
                                          encoding="utf-8")
    return fixture


def _write_goldset(fixture: Path, data: dict) -> None:
    p = fixture / "tests" / "eval" / "gold" / "search_goldset.json"
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _load(fixture: Path, name: str) -> dict:
    p = fixture / "tests" / "eval" / "gold" / name
    return json.loads(p.read_text(encoding="utf-8"))


# ── check: current frozen state ──────────────────────────────────────────────

def test_check_passes_on_current_frozen_state():
    assert curate_gold_set.run_check(REPO_ROOT) == 0


def test_check_floor_matches_manifest_gate_count():
    """The committed floor (16) is below the frozen manifest gate count (17)."""
    meta = json.loads(GROWTH_META.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert meta["min_gate_queries"] <= len(manifest["gate"])
    assert meta["min_gate_queries"] == _MIN_FLOOR


# ── check: seeded violations fail closed (exit 1) ────────────────────────────

def test_check_fails_on_tune_gate_overlap(tmp_path, capsys):
    fixture = _copy_gold_fixture(tmp_path)
    data = _load(fixture, "search_goldset.json")
    data["items"].append({"query": "leaked query", "relevant": ["coffee"],
                          "split": "tune", "kind": "positive"})
    data["items"].append({"query": "leaked query", "relevant": ["coffee"],
                          "split": "gate", "kind": "positive"})
    _write_goldset(fixture, data)

    assert curate_gold_set.run_check(fixture) == 1
    out = capsys.readouterr().out
    assert "[FAIL] tune_gate_disjoint" in out


def test_check_fails_when_gate_negative_dropped(tmp_path, capsys):
    fixture = _copy_gold_fixture(tmp_path)
    data = _load(fixture, "search_goldset.json")
    data["items"] = [i for i in data["items"] if i.get("kind") != "negative"]
    _write_goldset(fixture, data)

    assert curate_gold_set.run_check(fixture) == 1
    out = capsys.readouterr().out
    assert "[FAIL] gibberish_negative" in out


def test_check_fails_on_sha_mismatch(tmp_path, capsys):
    fixture = _copy_gold_fixture(tmp_path)
    goldset = fixture / "tests" / "eval" / "gold" / "search_goldset.json"
    data = json.loads(goldset.read_text(encoding="utf-8"))
    data["note"] = "tampered bytes — manifest not re-frozen"
    _write_goldset(fixture, data)  # split_manifest.json sha256 left stale

    assert curate_gold_set.run_check(fixture) == 1
    out = capsys.readouterr().out
    assert "[FAIL] manifest_sha256" in out
    assert "sha256" in out


# ── --freeze round-trip ──────────────────────────────────────────────────────

def test_freeze_updates_manifest_sha_after_goldset_edit(tmp_path):
    fixture = _copy_gold_fixture(tmp_path)
    goldset = fixture / "tests" / "eval" / "gold" / "search_goldset.json"
    manifest = fixture / "tests" / "eval" / "gold" / "split_manifest.json"
    before = json.loads(manifest.read_text(encoding="utf-8"))

    data = json.loads(goldset.read_text(encoding="utf-8"))
    data["items"].append({
        "query": "gradient descent optimizer gate", "relevant": ["gradient_descent"],
        "split": "gate", "kind": "positive",
    })
    _write_goldset(fixture, data)
    assert _file_sha256(goldset) != before["sha256"]  # the edit broke the freeze

    assert curate_gold_set.freeze_manifest(fixture) == 0
    after = json.loads(manifest.read_text(encoding="utf-8"))
    assert after["sha256"] == _file_sha256(goldset)
    assert "gradient descent optimizer gate" in after["gate"]
    assert after["task"] == before["task"]  # metadata preserved

    # the frozen fixture now validates clean
    assert curate_gold_set.run_check(fixture) == 0


def test_freeze_is_idempotent_noop(tmp_path):
    fixture = _copy_gold_fixture(tmp_path)
    manifest = fixture / "tests" / "eval" / "gold" / "split_manifest.json"
    assert curate_gold_set.freeze_manifest(fixture) == 0  # in-sync -> no-op
    assert curate_gold_set.freeze_manifest(fixture) == 0
    assert manifest.read_bytes() == MANIFEST.read_bytes()


# ── --growth-record ──────────────────────────────────────────────────────────

def test_growth_record_updates_meta(tmp_path):
    fixture = _copy_gold_fixture(tmp_path)
    assert curate_gold_set.growth_record(fixture, "v0.6.0", "added 2 gate queries") == 0
    meta = _load(fixture, "growth_meta.json")
    assert meta["last_grown_minor"] == "v0.6.0"
    assert meta["last_grown_at"] == date.today().isoformat()
    assert meta["notes"] == "added 2 gate queries"
    assert meta["min_gate_queries"] == _MIN_FLOOR  # floor preserved


def test_growth_record_creates_meta_when_missing(tmp_path):
    fixture = tmp_path / "bare"
    fixture.mkdir()
    assert curate_gold_set.growth_record(fixture, "v0.6.0", "justification") == 0
    meta = json.loads((fixture / "tests" / "eval" / "gold" / "growth_meta.json").read_text())
    assert meta["last_grown_minor"] == "v0.6.0"
    assert meta["version"] == 1


# ── gate_search_goldset_fresh (release-certify) ──────────────────────────────

def test_gate_passes_on_real_repo_state():
    res = release_certify.gate_search_goldset_fresh(repo_root=REPO_ROOT)
    assert res["status"] == "PASS", res
    assert res["gate"] == "search_goldset_fresh"
    assert res["checks"]["integrity"]["status"] == "PASS"
    assert res["checks"]["gate_floor"]["status"] == "PASS"
    assert res["checks"]["grow_or_justify"]["status"] == "PASS"


def test_gate_fails_closed_on_low_gate_count(tmp_path, monkeypatch):
    fixture = _copy_gold_fixture(tmp_path)
    goldset = fixture / "tests" / "eval" / "gold" / "search_goldset.json"
    data = json.loads(goldset.read_text(encoding="utf-8"))
    # keep only 3 gate queries — below the committed floor of 16
    gate_items = [i for i in data["items"] if i.get("split") == "gate"][:3]
    tune_items = [i for i in data["items"] if i.get("split") == "tune"]
    data["items"] = tune_items + gate_items
    _write_goldset(fixture, data)
    assert curate_gold_set.freeze_manifest(fixture) == 0  # consistent fixture

    monkeypatch.setattr(release_certify, "REPO_ROOT", fixture)
    res = release_certify.gate_search_goldset_fresh()  # defaults to REPO_ROOT
    assert res["status"] == "FAIL"
    assert res["checks"]["gate_floor"]["status"] == "FAIL"
    assert "gate_floor" in res["reason"]


def test_gate_fails_closed_on_sha_drift(tmp_path, monkeypatch):
    fixture = _copy_gold_fixture(tmp_path)
    data = _load(fixture, "search_goldset.json")
    data["note"] = "edited without re-freeze"
    _write_goldset(fixture, data)

    monkeypatch.setattr(release_certify, "REPO_ROOT", fixture)
    res = release_certify.gate_search_goldset_fresh()
    assert res["status"] == "FAIL"
    assert res["checks"]["integrity"]["status"] == "FAIL"


def test_gate_fails_when_growth_meta_absent(tmp_path, monkeypatch):
    fixture = tmp_path / "no-meta"
    dst = fixture / "tests" / "eval" / "gold"
    dst.mkdir(parents=True)
    (dst / "search_goldset.json").write_text(GOLDSET.read_text(encoding="utf-8"),
                                             encoding="utf-8")
    (dst / "split_manifest.json").write_text(MANIFEST.read_text(encoding="utf-8"),
                                             encoding="utf-8")

    monkeypatch.setattr(release_certify, "REPO_ROOT", fixture)
    res = release_certify.gate_search_goldset_fresh()
    assert res["status"] == "FAIL"
    assert "grow_or_justify" in res["reason"]


def test_gate_registered_in_release_certify():
    assert "search_goldset_fresh" in release_certify.GATES
    assert len(release_certify.GATES) == 9
    assert release_certify.GATES[-1] == "search_goldset_fresh"
