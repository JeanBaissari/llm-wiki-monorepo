"""Tests for the canonical tuning-config surface (LWM_031).

Covers defaults == today's literals, every constant settable via file/env/CLI,
the CLI > env > file > default precedence, fail-closed rejection of unknown
keys + out-of-range values, the full 22-constant + matrix + signal-score
inventory, and the BM25 k1/b shared scoring path.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from llm_wiki.core.config import (
    ConfigError,
    TuningConfig,
    resolve_tuning,
    TYPE_TYPES,
    SIGNAL_KEYS,
)


def test_defaults_equal_todays_literals():
    c = resolve_tuning()  # nothing present → code defaults
    assert (c.relevance.directLink, c.relevance.sourceOverlap,
            c.relevance.commonNeighbor, c.relevance.typeAffinity) == (3.0, 4.0, 1.5, 1.0)
    assert c.insights.surpriseThreshold == 3
    assert c.insights.sparseCohesionThreshold == 0.15
    assert c.insights.sparseMinNodes == 3
    assert c.insights.bridgeCommunityMin == 3
    assert (c.insights.peripheralMaxDegree, c.insights.peripheralHubRatio) == (2, 0.5)
    assert c.insights.isolatedMaxDegree == 1
    assert (c.community.resolution, c.community.seed) == (1.0, 42)
    assert (c.retrieval.rrfK, c.retrieval.simFloor) == (60, 0.30)
    assert (c.bm25.k1, c.bm25.b) == (1.5, 0.75)
    assert (c.claims.penaltyStale, c.claims.penaltyOpen,
            c.claims.penaltyLowConf, c.claims.penaltyContested,
            c.claims.failBelow) == (2, 10, 5, 3, 70)


def test_matrix_and_signal_defaults_match_ts_literals():
    c = resolve_tuning()
    # The 5×5 matrix mirrors graph-engine/src/relevance.ts TYPE_AFFINITY.
    assert c.relevance.typeAffinityMatrix["entity"]["concept"] == 1.2
    assert c.relevance.typeAffinityMatrix["source"]["source"] == 0.5
    assert c.relevance.typeAffinityMatrix["synthesis"]["concept"] == 1.2
    assert c.insights.signalScores == {
        "crossCommunity": 3, "crossTypeStrong": 2, "crossTypeWeak": 1,
        "peripheralToHub": 2, "lowWeight": 1,
    }


def test_no_config_matches_default_dataclass():
    assert resolve_tuning().to_flat() == TuningConfig().to_flat()


def test_cli_override_effective():
    c = resolve_tuning(cli_overrides=["retrieval.simFloor=0.5", "community.resolution=2"])
    assert c.retrieval.simFloor == 0.5
    assert c.community.resolution == 2.0


def test_env_override_effective():
    c = resolve_tuning(env={"LLM_WIKI_TUNE__retrieval__rrfK": "80",
                            "LLM_WIKI_TUNE__bm25__k1": "1.2"})
    assert c.retrieval.rrfK == 80
    assert c.bm25.k1 == 1.2


def test_file_override_effective(tmp_path):
    (tmp_path / "tuning.toml").write_text(
        "[relevance]\ndirectLink = 5.0\n\n[retrieval]\nsimFloor = 0.4\n",
        encoding="utf-8",
    )
    c = resolve_tuning(wiki_root=tmp_path)
    assert c.relevance.directLink == 5.0
    assert c.retrieval.simFloor == 0.4


def test_nested_overrides_through_all_surfaces(tmp_path):
    # Matrix cell + signal score via CLI, env and TOML (nested tables).
    c = resolve_tuning(cli_overrides=[
        "relevance.typeAffinityMatrix.concept.entity=2.5",
        "insights.signalScores.crossTypeWeak=3",
    ])
    assert c.relevance.typeAffinityMatrix["concept"]["entity"] == 2.5
    assert c.insights.signalScores["crossTypeWeak"] == 3.0

    c = resolve_tuning(env={
        "LLM_WIKI_TUNE__relevance__typeAffinityMatrix__entity__concept": "1.7",
        "LLM_WIKI_TUNE__insights__signalScores__peripheralToHub": "1.5",
    })
    assert c.relevance.typeAffinityMatrix["entity"]["concept"] == 1.7
    assert c.insights.signalScores["peripheralToHub"] == 1.5

    (tmp_path / "tuning.toml").write_text(
        "[relevance.typeAffinityMatrix.entity]\nconcept = 1.9\n"
        "[insights.signalScores]\ncrossCommunity = 4\n",
        encoding="utf-8",
    )
    c = resolve_tuning(wiki_root=tmp_path)
    assert c.relevance.typeAffinityMatrix["entity"]["concept"] == 1.9
    assert c.insights.signalScores["crossCommunity"] == 4.0
    # untouched cells keep their defaults (override merges, never replaces)
    assert c.relevance.typeAffinityMatrix["source"]["source"] == 0.5
    assert c.insights.signalScores["lowWeight"] == 1.0


def test_precedence_cli_over_env_over_file(tmp_path):
    (tmp_path / "tuning.toml").write_text("[retrieval]\nsimFloor = 0.1\n", encoding="utf-8")
    c = resolve_tuning(
        wiki_root=tmp_path,
        env={"LLM_WIKI_TUNE__retrieval__simFloor": "0.2"},
        cli_overrides=["retrieval.simFloor=0.3"],
    )
    assert c.retrieval.simFloor == 0.3  # CLI wins
    # env beats file when no CLI:
    c2 = resolve_tuning(wiki_root=tmp_path, env={"LLM_WIKI_TUNE__retrieval__simFloor": "0.2"})
    assert c2.retrieval.simFloor == 0.2
    # file beats default when no env/CLI:
    c3 = resolve_tuning(wiki_root=tmp_path)
    assert c3.retrieval.simFloor == 0.1


def test_unknown_key_fails_closed():
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["retrieval.notAKey=1"])
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["bogus.section=1"])
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["relevance.typeAffinityMatrix.bogus.concept=1"])
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["insights.signalScores.bogus=1"])


def test_out_of_range_rejected():
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["retrieval.simFloor=1.5"])  # >1
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["community.resolution=0"])  # must be > 0
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["relevance.directLink=-1"])  # negative
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["relevance.typeAffinityMatrix.entity.concept=-1"])
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["insights.signalScores.crossCommunity=-2"])


def test_community_engine_validated_fail_closed():
    """BKD-003: community.engine is enum-validated — unknown engines exit 2."""
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["community.engine=spectral"])
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["community.engine=42"])
    # Valid values resolve; default is louvain (byte-identical behavior).
    assert resolve_tuning().community.engine == "louvain"
    assert resolve_tuning(cli_overrides=["community.engine=leiden"]).community.engine == "leiden"
    assert resolve_tuning(cli_overrides=["community.engine=LOUVAIN"]).community.engine == "louvain"


def test_malformed_overrides_rejected():
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["retrieval.simFloor"])  # no '='
    with pytest.raises(ConfigError):
        resolve_tuning(env={"LLM_WIKI_TUNE__retrievalsimFloor": "0.2"})  # no '__'
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["retrieval.rrfK=notanint"])  # bad int


def test_graph_engine_json_shape():
    j = resolve_tuning().to_graph_engine_json()
    assert j["relevance"]["weights"]["directLink"] == 3.0
    assert j["insights"]["surpriseThreshold"] == 3
    assert j["community"]["resolution"] == 1.0


# ── LWM_031 AC#2: every constant reachable + effective ─────────────────────

def _json_dig(profile: dict, parts: "tuple[str, ...]"):
    node = profile
    for p in parts:
        node = node[p]
    return node


# key → (non-default test value, path into to_graph_engine_json())
_ALL_CONSTANTS: "list[tuple[str, str, tuple[str, ...]]]" = [
    ("relevance.directLink", "4.5", ("relevance", "weights", "directLink")),
    ("relevance.sourceOverlap", "2.5", ("relevance", "weights", "sourceOverlap")),
    ("relevance.commonNeighbor", "0.75", ("relevance", "weights", "commonNeighbor")),
    ("relevance.typeAffinity", "1.25", ("relevance", "weights", "typeAffinity")),
    ("insights.surpriseThreshold", "7", ("insights", "surpriseThreshold")),
    ("insights.sparseCohesionThreshold", "0.05", ("insights", "sparseCohesionThreshold")),
    ("insights.sparseMinNodes", "5", ("insights", "sparseMinNodes")),
    ("insights.bridgeCommunityMin", "2", ("insights", "bridgeCommunityMin")),
    ("insights.peripheralMaxDegree", "3", ("insights", "peripheralMaxDegree")),
    ("insights.peripheralHubRatio", "0.35", ("insights", "peripheralHubRatio")),
    ("insights.isolatedMaxDegree", "2", ("insights", "isolatedMaxDegree")),
    ("community.resolution", "1.5", ("community", "resolution")),
    ("community.seed", "7", ("community", "seed")),
    ("retrieval.rrfK", "80", ("retrieval", "rrfK")),
    ("retrieval.simFloor", "0.45", ("retrieval", "simFloor")),
    ("bm25.k1", "2.0", ("bm25", "k1")),
    ("bm25.b", "0.5", ("bm25", "b")),
    ("claims.penaltyStale", "4", ("claims", "penaltyStale")),
    ("claims.penaltyOpen", "12", ("claims", "penaltyOpen")),
    ("claims.penaltyLowConf", "6", ("claims", "penaltyLowConf")),
    ("claims.penaltyContested", "5", ("claims", "penaltyContested")),
    ("claims.failBelow", "60", ("claims", "failBelow")),
] + [
    (f"relevance.typeAffinityMatrix.{r}.{c}", "9.9",
     ("relevance", "typeAffinityMatrix", r, c))
    for r in TYPE_TYPES for c in TYPE_TYPES
] + [
    (f"insights.signalScores.{s}", "7.7", ("insights", "signalScores", s))
    for s in SIGNAL_KEYS
]


def test_all_constants_configurable():
    """Every inventory constant is reachable via CLI override, changes the
    resolved value, and is visible in the graph-engine emit surface (the TS
    consumer boundary — LWM_031 AC#2)."""
    defaults = TuningConfig().to_flat()
    assert len(_ALL_CONSTANTS) == 22 + 25 + 5  # 22 scalars + 5×5 matrix + 5 signals
    for key, test_val, json_path in _ALL_CONSTANTS:
        resolved = resolve_tuning(cli_overrides=[f"{key}={test_val}"])
        flat = resolved.to_flat()
        assert flat[key] != defaults[key], f"{key} did not change"
        emitted = _json_dig(resolved.to_graph_engine_json(), json_path)
        assert emitted != defaults[key], f"{key} not visible in the emit boundary"
        assert isinstance(emitted, (int, float))


def test_all_constants_reachable_via_file(tmp_path):
    """Every matrix cell + signal score + the 22 scalars are settable from a
    tuning.toml (sparse sample of each section; full coverage via CLI test)."""
    (tmp_path / "tuning.toml").write_text(
        "[relevance.typeAffinityMatrix.entity]\nconcept = 2.5\n"
        "[insights.signalScores]\nlowWeight = 4\n"
        "[insights]\nsurpriseThreshold = 6\n"
        "[community]\nseed = 99\n",
        encoding="utf-8",
    )
    c = resolve_tuning(wiki_root=tmp_path)
    assert c.relevance.typeAffinityMatrix["entity"]["concept"] == 2.5
    assert c.insights.signalScores["lowWeight"] == 4.0
    assert c.insights.surpriseThreshold == 6
    assert c.community.seed == 99


# ── Consumer wiring (the constants are effective, not just representable) ──

def test_louvain_consumer_threaded():
    """community.resolution/seed flow into detect_communities; defaults are
    byte-identical; a high resolution visibly splits communities."""
    import warnings
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
        base, _ = detect_communities(nodes, edges)
        explicit, _ = detect_communities(nodes, edges, resolution=1.0, seed=42)
        tuned = resolve_tuning(cli_overrides=["community.resolution=1.0", "community.seed=42"])
        tuned_partition, _ = detect_communities(nodes, edges,
                                                resolution=tuned.community.resolution,
                                                seed=tuned.community.seed)
        high_res, _ = detect_communities(nodes, edges, resolution=100.0)
    assert explicit == base                      # no-break: explicit defaults == default
    assert tuned_partition == base               # resolved defaults == default
    assert len(set(base.values())) == 2          # two triangles
    assert len(set(high_res.values())) >= len(set(base.values()))  # higher resolution splits


def test_insights_consumer_threaded():
    """insights.* thresholds + signal scores + community params flow through
    compute_insights; no-tuning == default-tuning (byte-identical)."""
    from llm_wiki.graph.insights import compute_insights

    root = Path(__file__).resolve().parent / "fixtures" / "wikis" / "populated"
    if not root.is_dir():
        pytest.skip("populated fixture not present")

    base = compute_insights(str(root), fmt="json")
    defaults = compute_insights(str(root), fmt="json", tuning=TuningConfig())
    assert base == defaults  # no-break guard

    # sparseCohesionThreshold: higher threshold admits more sparse communities,
    # lower admits fewer (0.001 admits none unless cohesion is ~0).
    out_high = compute_insights(str(root), fmt="json", tuning=resolve_tuning(
        cli_overrides=["insights.sparseCohesionThreshold=0.99"]))
    out_low = compute_insights(str(root), fmt="json", tuning=resolve_tuning(
        cli_overrides=["insights.sparseCohesionThreshold=0.001"]))
    assert (len(out_high["knowledgeGaps"]["sparseCommunities"])
            >= len(base["knowledgeGaps"]["sparseCommunities"]))
    assert len(out_low["knowledgeGaps"]["sparseCommunities"]) <= len(base["knowledgeGaps"]["sparseCommunities"])

    # bridgeCommunityMin=99 → nothing can be a bridge; isolatedMaxDegree=0
    # excludes degree-1 nodes → fewer isolated than the default cut.
    out2 = compute_insights(str(root), fmt="json", tuning=resolve_tuning(
        cli_overrides=["insights.bridgeCommunityMin=99", "insights.isolatedMaxDegree=0"]))
    assert out2["knowledgeGaps"]["bridgeNodes"] == []
    assert len(out2["knowledgeGaps"]["isolatedNodes"]) <= len(base["knowledgeGaps"]["isolatedNodes"])

    # signalScores: a larger cross-community base moves every cross-community
    # connection score (the fixture has several).
    sig = resolve_tuning(cli_overrides=["insights.signalScores.crossCommunity=5"])
    out3 = compute_insights(str(root), fmt="json", tuning=sig)
    assert out3["surprisingConnections"] != base["surprisingConnections"]


def test_claims_consumer_threaded(tmp_path):
    """claims.penalty* + failBelow flow into the red-team health score."""
    from llm_wiki.core.config import TuningConfig
    from llm_wiki.quality.claims.models import Claim, Contradiction
    from llm_wiki.quality.claims.storage import ClaimsManager

    wiki = tmp_path / "claims-wiki"
    wiki.mkdir()
    mgr = ClaimsManager(str(wiki))
    mgr.create_claim(Claim(claim_id="c1", statement="low conf", confidence="low",
                           status="active", sources=["s"], pages=["p.md"],
                           first_seen_operation_id="op"))
    mgr.create_contradiction(Contradiction(
        contradiction_id="x1", claim_ids=["c1"], status="open", severity="high",
        evidence=["e"]))

    base = mgr.redteam_report()
    # default penalties: 1 low-conf × 5 + 1 open × 10 + 1 contested × 3 → score 82
    assert base["health_score"] == 82

    tuned = resolve_tuning(cli_overrides=[
        "claims.penaltyLowConf=100", "claims.penaltyOpen=100",
    ])
    assert mgr.redteam_report(tuning=tuned)["health_score"] == 0  # 203 ≥ 100 cap

    # failBelow: default 70 → 82 ≥ 70 → exit 0; failBelow=99 → exit 1
    default_tuning = TuningConfig()
    assert mgr.redteam_report(tuning=default_tuning)["health_score"] >= default_tuning.claims.failBelow
    high_bar = resolve_tuning(cli_overrides=["claims.failBelow=99"])
    report = mgr.redteam_report(tuning=high_bar)
    assert report["health_score"] < high_bar.claims.failBelow


def _make_bm25_wiki(wiki_root: Path) -> None:
    """3 pages: a.md + z.md share one term set (z has a huge tf), m.md is a
    single-term page. With tf-saturation (default FTS5-native) z.md ranks
    first; with k1=0 the tf boost collapses and the tie-break flips."""
    (wiki_root / "wiki").mkdir(parents=True)
    (wiki_root / "wiki" / "a.md").write_text(
        "---\ntitle: Alpha\n---\n# Alpha\n\nzebra attention\n", encoding="utf-8")
    (wiki_root / "wiki" / "z.md").write_text(
        "---\ntitle: Zulu\n---\n# Zulu\n\n" + "zebra " * 10 + "attention\n", encoding="utf-8")
    (wiki_root / "wiki" / "m.md").write_text(
        "---\ntitle: Mike\n---\n# Mike\n\nzebra\n", encoding="utf-8")
    from llm_wiki.search.index import index_wiki
    stats = index_wiki(wiki_root, rebuild=True)
    assert stats["files_indexed"] == 3


def test_bm25_shared():
    """bm25.k1/b flow into the Python keyword path: an override changes the
    ranking; the default path stays on FTS5's native bm25() byte-identical."""
    from llm_wiki.search.query import keyword_search

    import tempfile
    wiki = Path(tempfile.mkdtemp(prefix="bm25-shared-")) / "w"
    _make_bm25_wiki(wiki)

    query = "zebra attention"
    default = keyword_search(str(wiki), query)
    native = keyword_search(str(wiki), query, k1=None, b=None)
    assert default == native          # default path untouched
    assert [r["path"] for r in default] == ["wiki/z.md", "wiki/a.md", "wiki/m.md"]

    # k1=0 collapses the tf boost: z.md (tf=10) ties a.md (tf=1) on the same
    # term set → the path tie-break flips the ranking (constants flow).
    flat = keyword_search(str(wiki), query, k1=0.0, b=0.75)
    assert [r["path"] for r in flat] != [r["path"] for r in default]
    assert [r["path"] for r in flat] == ["wiki/a.md", "wiki/z.md", "wiki/m.md"]

    # a strong k1 with length normalization off (b=0) re-amplifies tf: z.md back
    # on top — proving both k1 AND b flow into the scorer.
    strong = keyword_search(str(wiki), query, k1=3.0, b=0.0)
    assert [r["path"] for r in strong] == ["wiki/z.md", "wiki/a.md", "wiki/m.md"]
    assert [r["path"] for r in strong] != [r["path"] for r in flat]

    # deterministic rescore path (same params twice → same order)
    again = keyword_search(str(wiki), query, k1=0.0, b=0.75)
    assert [r["path"] for r in again] == [r["path"] for r in flat]


def test_hybrid_search_resolves_wiki_tuning(tmp_path):
    """The sidecar/MCP path: hybrid_search auto-resolves tuning.toml for the
    BM25 override + retrieval keys when the caller passes nothing."""
    from llm_wiki.search.query import hybrid_search

    _make_bm25_wiki(tmp_path)
    base = hybrid_search(str(tmp_path), "zebra attention")
    assert base  # keyword-only fallback (no [semantic] extra)

    (tmp_path / "tuning.toml").write_text("[bm25]\nk1 = 0.0\n", encoding="utf-8")
    tuned = hybrid_search(str(tmp_path), "zebra attention")
    assert [r["path"] for r in tuned] != [r["path"] for r in base]
