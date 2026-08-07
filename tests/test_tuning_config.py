"""Tests for the canonical tuning-config surface (LWM_031).

Covers defaults == today's literals, every constant settable via file/env/CLI,
the CLI > env > file > default precedence, and fail-closed rejection of unknown
keys + out-of-range values.
"""

import pytest

from llm_wiki.core.config import ConfigError, TuningConfig, resolve_tuning


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


def test_out_of_range_rejected():
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["retrieval.simFloor=1.5"])  # >1
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["community.resolution=0"])  # must be > 0
    with pytest.raises(ConfigError):
        resolve_tuning(cli_overrides=["relevance.directLink=-1"])  # negative


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
