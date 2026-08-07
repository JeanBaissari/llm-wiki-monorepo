"""Search gold-set integrity (LWM_032) — disjointness + SHA256 freeze.

The search gold set lives in ``tests/eval/gold/search_goldset.json`` (labels
are ``query -> relevant page-ids``, distinct from the link-suggestion set in
``tests/eval/fixtures/goldset_seed.json``). ``split_manifest.json`` freezes the
tune/gate split by SHA256: editing the goldset without updating the manifest
fails closed here. See GOLD_SET.md in this directory for the methodology.
"""

import hashlib
import json
from pathlib import Path

import pytest

from llm_wiki.eval.search_baseline import load_search_goldset

GOLD_DIR = Path(__file__).parent / "gold"
GOLDSET = GOLD_DIR / "search_goldset.json"
MANIFEST = GOLD_DIR / "split_manifest.json"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_sha256_matches_goldset():
    """Editing the goldset without re-freezing the manifest fails the gate."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["task"] == "search-retrieval"
    assert manifest["sha256"] == _file_sha256(GOLDSET), (
        "split_manifest.json sha256 does not match search_goldset.json — "
        "recompute and update the manifest (see tests/eval/gold/GOLD_SET.md)"
    )


def test_tune_gate_disjoint():
    """tune ∩ gate = ∅, enforced at load and re-asserted here."""
    data = load_search_goldset(GOLDSET)  # raises ValueError on overlap
    tune = {i["query"] for i in data["items"] if i.get("split") == "tune"}
    gate = {i["query"] for i in data["items"] if i.get("split") == "gate"}
    assert tune and gate, "gold set must have both splits"
    assert tune.isdisjoint(gate)


def test_manifest_lists_match_goldset_split():
    """The manifest's tune/gate query lists are exactly the goldset's."""
    data = load_search_goldset(GOLDSET)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_split: dict[str, list[str]] = {"tune": [], "gate": []}
    for i in data["items"]:
        by_split[i["split"]].append(i["query"])
    assert sorted(by_split["tune"]) == sorted(manifest["tune"])
    assert sorted(by_split["gate"]) == sorted(manifest["gate"])


def test_every_positive_query_has_relevant_pages():
    data = load_search_goldset(GOLDSET)
    for item in data["items"]:
        if item.get("kind") == "negative":
            assert item["relevant"] == [], (
                f"negative query must have empty relevant: {item['query']}"
            )
        else:
            assert isinstance(item["relevant"], list) and item["relevant"], (
                f"positive query must label >=1 relevant page: {item['query']}"
            )
            assert item["split"] in ("tune", "gate")


def test_gibberish_negatives_present():
    """Adversarial negatives exist and are split appropriately."""
    data = load_search_goldset(GOLDSET)
    negatives = [i for i in data["items"] if i.get("kind") == "negative"]
    assert negatives, "gold set must contain gibberish negatives (relevant: [])"
    for item in negatives:
        assert item["relevant"] == []
        assert item["split"] == "gate"


def test_search_labels_are_query_to_pages():
    """Distinct from the link-suggestion set: labels are free-text queries."""
    data = load_search_goldset(GOLDSET)
    for item in data["items"]:
        assert "query" in item and "relevant" in item
        assert isinstance(item["query"], str) and item["query"].strip()


def test_goldset_files_committed():
    assert GOLDSET.exists() and MANIFEST.exists()
    baseline = Path(__file__).resolve().parents[1] / "eval" / "baseline" / "search_eval_baseline.json"
    assert baseline.exists(), "committed search baseline missing (LWM_032)"
    baseline_data = json.loads(baseline.read_text(encoding="utf-8"))
    assert baseline_data["split"] == "gate"


def test_leaked_query_rejected(tmp_path):
    """A query present in both splits must be rejected at load."""
    bad = {
        "items": [
            {"query": "dup", "split": "tune", "relevant": ["p1"]},
            {"query": "dup", "split": "gate", "relevant": ["p2"]},
        ]
    }
    p = tmp_path / "leak_probe.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_search_goldset(p)
