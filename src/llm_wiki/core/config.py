#!/usr/bin/env python3
"""config.py — Canonical tuning-config surface (LWM_031). See ADR-0028.

One place for every magic tuning constant that steers precision — relevance
weights, insights thresholds, community detection, RRF/hybrid retrieval, BM25,
and claim-health penalties. Defaults equal today's source literals byte-for-byte,
so nothing changes until a constant is measured and re-tuned on the LWM_022 TUNE
split. Resolution precedence is **CLI > env > file > code-default**; unknown keys
and out-of-range values **fail closed** (raise ``ConfigError`` → CLI exit 2).

The Python ``TuningConfig`` is the single source of truth; the TypeScript
graph-engine consumes ``to_graph_engine_json()`` through its existing
``RelevanceOptions`` / ``InsightsOptions`` / ``LouvainOptions`` interfaces, so the
two languages can never drift (v0.5.0 invariant #4).
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


class ConfigError(ValueError):
    """Raised on an unknown key or an out-of-range value (fail-closed)."""


# ── sections (defaults == today's literals) ──────────────────────────────────

@dataclass(frozen=True)
class RelevanceCfg:
    directLink: float = 3.0
    sourceOverlap: float = 4.0
    commonNeighbor: float = 1.5
    typeAffinity: float = 1.0


@dataclass(frozen=True)
class InsightsCfg:
    surpriseThreshold: int = 3
    sparseCohesionThreshold: float = 0.15
    sparseMinNodes: int = 3
    bridgeCommunityMin: int = 3
    peripheralMaxDegree: int = 2
    peripheralHubRatio: float = 0.5
    isolatedMaxDegree: int = 1


@dataclass(frozen=True)
class CommunityCfg:
    resolution: float = 1.0
    seed: int = 42


@dataclass(frozen=True)
class RetrievalCfg:
    rrfK: int = 60
    simFloor: float = 0.30


@dataclass(frozen=True)
class Bm25Cfg:
    k1: float = 1.5
    b: float = 0.75


@dataclass(frozen=True)
class ClaimsCfg:
    penaltyStale: int = 2
    penaltyOpen: int = 10
    penaltyLowConf: int = 5
    penaltyContested: int = 3
    failBelow: int = 70


@dataclass(frozen=True)
class TuningConfig:
    relevance: RelevanceCfg = field(default_factory=RelevanceCfg)
    insights: InsightsCfg = field(default_factory=InsightsCfg)
    community: CommunityCfg = field(default_factory=CommunityCfg)
    retrieval: RetrievalCfg = field(default_factory=RetrievalCfg)
    bm25: Bm25Cfg = field(default_factory=Bm25Cfg)
    claims: ClaimsCfg = field(default_factory=ClaimsCfg)

    def to_graph_engine_json(self) -> dict:
        """Resolved tuning for the TS graph-engine option interfaces."""
        return {
            "relevance": {"weights": asdict(self.relevance)},
            "insights": asdict(self.insights),
            "community": asdict(self.community),
        }

    def to_flat(self) -> "dict[str, Any]":
        out: dict[str, Any] = {}
        for section in _SECTIONS:
            for k, v in asdict(getattr(self, section)).items():
                out[f"{section}.{k}"] = v
        return out


_SECTIONS = ("relevance", "insights", "community", "retrieval", "bm25", "claims")
_SECTION_CLS = {
    "relevance": RelevanceCfg, "insights": InsightsCfg, "community": CommunityCfg,
    "retrieval": RetrievalCfg, "bm25": Bm25Cfg, "claims": ClaimsCfg,
}

# key -> validator(value) -> bool ; only keys present here are settable.
_nonneg: Callable[[Any], bool] = lambda v: isinstance(v, (int, float)) and v >= 0
_unit: Callable[[Any], bool] = lambda v: isinstance(v, (int, float)) and 0.0 <= v <= 1.0
_pos: Callable[[Any], bool] = lambda v: isinstance(v, (int, float)) and v > 0
_posint: Callable[[Any], bool] = lambda v: isinstance(v, int) and v > 0
_nonnegint: Callable[[Any], bool] = lambda v: isinstance(v, int) and v >= 0
_anyint: Callable[[Any], bool] = lambda v: isinstance(v, int)

_VALIDATORS: "dict[str, Callable[[Any], bool]]" = {
    "relevance.directLink": _nonneg, "relevance.sourceOverlap": _nonneg,
    "relevance.commonNeighbor": _nonneg, "relevance.typeAffinity": _nonneg,
    "insights.surpriseThreshold": _nonnegint, "insights.sparseCohesionThreshold": _unit,
    "insights.sparseMinNodes": _nonnegint, "insights.bridgeCommunityMin": _nonnegint,
    "insights.peripheralMaxDegree": _nonnegint, "insights.peripheralHubRatio": _unit,
    "insights.isolatedMaxDegree": _nonnegint,
    "community.resolution": _pos, "community.seed": _anyint,
    "retrieval.rrfK": _posint, "retrieval.simFloor": _unit,
    "bm25.k1": _nonneg, "bm25.b": _unit,
    "claims.penaltyStale": _nonnegint, "claims.penaltyOpen": _nonnegint,
    "claims.penaltyLowConf": _nonnegint, "claims.penaltyContested": _nonnegint,
    "claims.failBelow": _nonnegint,
}


def _coerce(key: str, raw: Any) -> Any:
    """Coerce a scalar (from env/CLI strings) to the field's declared type."""
    section, _, name = key.partition(".")
    cls = _SECTION_CLS.get(section)
    if cls is None or name not in cls.__dataclass_fields__:
        raise ConfigError(f"unknown tuning key: {key}")
    declared = cls.__dataclass_fields__[name].type
    if isinstance(raw, str):
        # int fields must parse as int (not float); float fields accept both.
        want_int = declared in ("int", int)
        try:
            return int(raw) if want_int else float(raw)
        except ValueError:
            raise ConfigError(f"{key}: cannot parse {raw!r} as {'int' if want_int else 'float'}")
    return raw


def _apply(overrides: "dict[str, Any]", flat: "dict[str, Any]") -> None:
    for key, raw in overrides.items():
        if key not in _VALIDATORS:
            raise ConfigError(f"unknown tuning key: {key}")
        val = _coerce(key, raw)
        if not _VALIDATORS[key](val):
            raise ConfigError(f"{key}: value {val!r} out of range")
        flat[key] = val


def _load_file(path: Path) -> "dict[str, Any]":
    if not path.exists():
        return {}
    try:
        import tomllib
    except ImportError:  # pragma: no cover - py<3.11
        return {}
    with open(path, "rb") as f:
        data = tomllib.load(f)
    flat: dict[str, Any] = {}
    for section, tbl in data.items():
        if isinstance(tbl, dict):
            for k, v in tbl.items():
                flat[f"{section}.{k}"] = v
    return flat


def _load_env(env: "dict[str, str]") -> "dict[str, Any]":
    """Parse ``LLM_WIKI_TUNE__<section>__<key>`` overrides."""
    out: dict[str, Any] = {}
    prefix = "LLM_WIKI_TUNE__"
    for name, val in env.items():
        if not name.startswith(prefix):
            continue
        body = name[len(prefix):]
        if "__" not in body:
            raise ConfigError(f"malformed tuning env var: {name}")
        section, _, key = body.partition("__")
        out[f"{section}.{key}"] = val
    return out


def _parse_cli(pairs: "list[str]") -> "dict[str, Any]":
    """Parse repeatable ``--set section.key=value`` overrides."""
    out: dict[str, Any] = {}
    for p in pairs or []:
        if "=" not in p:
            raise ConfigError(f"malformed --set (expected section.key=value): {p}")
        key, _, val = p.partition("=")
        out[key.strip()] = val.strip()
    return out


def resolve_tuning(
    wiki_root=None,
    cli_overrides: "Optional[list[str]]" = None,
    env: "Optional[dict[str, str]]" = None,
    file_path: "Optional[Path]" = None,
) -> TuningConfig:
    """Resolve the tuning config with precedence CLI > env > file > code-default.

    With no overrides present, the result equals the code defaults byte-for-byte.
    """
    flat = TuningConfig().to_flat()  # code defaults

    if file_path is None and wiki_root is not None:
        cand = Path(wiki_root) / "tuning.toml"
        file_path = cand if cand.exists() else None
    if file_path is not None:
        _apply(_load_file(Path(file_path)), flat)

    _apply(_load_env(env if env is not None else os.environ), flat)
    _apply(_parse_cli(cli_overrides or []), flat)

    # Rebuild frozen sections from the resolved flat map.
    kwargs = {}
    for section in _SECTIONS:
        cls = _SECTION_CLS[section]
        sec_vals = {k.split(".", 1)[1]: v for k, v in flat.items() if k.startswith(section + ".")}
        kwargs[section] = cls(**sec_vals)
    return TuningConfig(**kwargs)
