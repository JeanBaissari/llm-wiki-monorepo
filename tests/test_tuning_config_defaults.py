"""Defaults-snapshot golden + no-break guards for the tuning surface (LWM_031).

Pins the full resolved default profile (23 scalars + 5×5 matrix + 5 signal
scores) to a committed golden file so any default change fails CI (PRD §Defaults
Freeze), and proves the Python consumers behave byte-identically when threaded
with the resolved-default config vs nothing at all.
"""

import json
import warnings
from pathlib import Path

import pytest

from llm_wiki.core.config import TuningConfig, resolve_tuning

BASELINE = Path(__file__).resolve().parent / "eval" / "baseline" / "tuning_defaults.json"


def test_defaults_snapshot_golden():
    """No config present → the resolved flat map equals the committed golden
    (byte-for-byte: the snapshot is the "defaults unchanged" evidence)."""
    golden = json.loads(BASELINE.read_text(encoding="utf-8"))
    resolved = resolve_tuning().to_flat()
    assert resolved == golden
    assert len(resolved) == 23 + 25 + 5  # 23 scalars + 5×5 matrix + 5 signals
    assert len(golden) == len(resolved)


def test_emit_surface_matches_golden():
    """`llm-wiki tuning` (emit surface) with no overrides emits the canonical
    profile, which test_defaults_snapshot_golden pins to the committed golden."""
    from llm_wiki.core.tuning import emit_profile
    profile = emit_profile()
    assert profile == resolve_tuning().to_graph_engine_json()
    # spot-check the golden values through the JSON shape
    assert profile["relevance"]["weights"]["directLink"] == 3.0
    assert profile["relevance"]["typeAffinityMatrix"]["entity"]["concept"] == 1.2
    assert profile["insights"]["signalScores"]["crossCommunity"] == 3
    assert profile["community"]["resolution"] == 1.0
    assert profile["retrieval"]["rrfK"] == 60
    assert profile["bm25"]["k1"] == 1.5
    assert profile["claims"]["failBelow"] == 70


def test_emit_surface_applies_resolution(tmp_path):
    """The emit surface applies CLI > env > file so a non-default profile can
    be emitted (and then fed to graph-engine --tuning-json)."""
    from llm_wiki.core.tuning import emit_profile

    (tmp_path / "tuning.toml").write_text(
        "[retrieval]\nsimFloor = 0.42\n[community]\nresolution = 1.5\n",
        encoding="utf-8",
    )
    profile = emit_profile(str(tmp_path), overrides=["relevance.directLink=5.0"])
    assert profile["retrieval"]["simFloor"] == 0.42          # file
    assert profile["community"]["resolution"] == 1.5         # file
    assert profile["relevance"]["weights"]["directLink"] == 5.0  # CLI wins

    env_profile = emit_profile(str(tmp_path), overrides=["relevance.directLink=5.0"],
                               env={"LLM_WIKI_TUNE__retrieval__simFloor": "0.5"})
    assert env_profile["retrieval"]["simFloor"] == 0.5       # env beats file
    assert env_profile["community"]["resolution"] == 1.5


def test_emit_surface_fails_closed():
    from llm_wiki.core.config import ConfigError
    from llm_wiki.core.tuning import emit_profile
    with pytest.raises(ConfigError):
        emit_profile(overrides=["bogus.key=1"])


# ── No-break guards: resolved defaults == today's literals in consumers ─────

def test_louvain_defaults_no_break():
    """detect_communities with explicit default resolution/seed == with none,
    and == the resolved-default config values (NMI/ARI identity)."""
    from llm_wiki.graph.louvain import detect_communities

    nodes = [{"id": f"n{i}", "label": f"N{i}", "linkCount": 2} for i in range(6)]
    edges = [
        {"source": "n0", "target": "n1", "weight": 1},
        {"source": "n1", "target": "n2", "weight": 1},
        {"source": "n0", "target": "n2", "weight": 1},
        {"source": "n3", "target": "n4", "weight": 1},
        {"source": "n4", "target": "n5", "weight": 1},
        {"source": "n3", "target": "n5", "weight": 1},
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        a, _ = detect_communities(nodes, edges)
        b, _ = detect_communities(nodes, edges, seed=42, resolution=1.0)
        cfg = resolve_tuning()
        c, _ = detect_communities(nodes, edges,
                                  seed=cfg.community.seed,
                                  resolution=cfg.community.resolution)
    assert a == b == c


def test_insights_defaults_no_break_on_fixture():
    """compute_insights with the resolved-default config == with no tuning
    (the CLI now always resolves+threads; output must not move)."""
    from llm_wiki.graph.insights import compute_insights

    root = Path(__file__).resolve().parent / "fixtures" / "wikis" / "populated"
    if not root.is_dir():
        pytest.skip("populated fixture not present")
    plain = compute_insights(str(root), fmt="json")
    threaded = compute_insights(str(root), fmt="json", tuning=resolve_tuning(str(root)))
    assert plain == threaded


def test_louvain_consumers_identical_partitions_on_fixture_graphs():
    """detect_communities (no args) == detect_communities (resolved defaults)
    on every committed graph fixture — the pre/post partition identity guard."""
    from llm_wiki.graph.louvain import detect_communities

    graphs = Path(__file__).resolve().parent / "fixtures" / "graphs"
    seen = 0
    for fixture in sorted(graphs.glob("*.json")):
        if fixture.name == "README.md":
            continue
        data = json.loads(fixture.read_text(encoding="utf-8"))
        if not data:
            continue
        edges = data if isinstance(data, list) else data.get("edges", data.get("links", []))
        norm = [{"source": str(e.get("source")), "target": str(e.get("target")),
                 "weight": e.get("weight", 1)} for e in edges]
        node_ids = sorted({e["source"] for e in norm} | {e["target"] for e in norm})
        nodes = [{"id": n, "label": n, "linkCount": 1} for n in node_ids]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            cfg = resolve_tuning()
            a, _ = detect_communities(nodes, norm)
            b, _ = detect_communities(nodes, norm, seed=cfg.community.seed,
                                      resolution=cfg.community.resolution)
        assert a == b, f"partition drift on {fixture.name}"
        seen += 1
    assert seen > 0
