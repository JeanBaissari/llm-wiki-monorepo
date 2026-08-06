#!/usr/bin/env python3
"""goldset.py — Gold-set schema, loader, and the disjoint tune/gate split.

The eval harness is only trustworthy if the set used to *tune* constants is
disjoint from the set used to *gate* releases (ADR-0022). This module enforces
that: every gold item declares a ``split`` of "tune" or "gate", the gate split
is never returned to a tuning caller, and ``load_goldset`` fails closed if any
query appears in both splits.

Gold-set file format (JSON), stdlib-only::

    {
      "version": 1,
      "items": [
        {"query": "andrej karpathy",
         "relevant": ["entities/andrej-karpathy"], "split": "gate"},
        {"query": "neural network",
         "relevant": ["concepts/neural-network"], "split": "tune"},
        {"query": "zzzznonexistentterm",
         "relevant": [], "split": "gate", "kind": "negative"}
      ]
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Split = Literal["tune", "gate"]


@dataclass(frozen=True)
class GoldItem:
    query: str
    relevant: tuple[str, ...]
    split: Split
    kind: str = "positive"  # "positive" | "negative"

    @property
    def is_negative(self) -> bool:
        return self.kind == "negative" or len(self.relevant) == 0


@dataclass
class GoldSet:
    items: list[GoldItem] = field(default_factory=list)
    version: int = 1

    def by_split(self, split: Split) -> list[GoldItem]:
        return [it for it in self.items if it.split == split]

    @property
    def tune(self) -> list[GoldItem]:
        return self.by_split("tune")

    @property
    def gate(self) -> list[GoldItem]:
        return self.by_split("gate")


def tune_only(goldset: GoldSet) -> GoldSet:
    """A view with ONLY the tune split.

    Hand this (never the full ``GoldSet``) to any constant-tuning code so it
    structurally cannot read gate labels — the tuning/gating isolation half of
    ADR-0022 (the other half, disjointness, is enforced at load time).
    """
    return GoldSet(items=list(goldset.tune), version=goldset.version)


def gate_only(goldset: GoldSet) -> GoldSet:
    """A view with ONLY the gate split — used exclusively by the release gate."""
    return GoldSet(items=list(goldset.gate), version=goldset.version)


class GoldSetError(ValueError):
    """Raised when a gold set is malformed or violates the disjoint invariant."""


def _validate_disjoint(items: list[GoldItem]) -> None:
    tune_q = {it.query for it in items if it.split == "tune"}
    gate_q = {it.query for it in items if it.split == "gate"}
    overlap = tune_q & gate_q
    if overlap:
        raise GoldSetError(
            "tune/gate splits must be disjoint; queries in both: "
            + ", ".join(sorted(overlap))
        )


def parse_goldset(data: dict) -> GoldSet:
    version = int(data.get("version", 1))
    raw_items = data.get("items", [])
    items: list[GoldItem] = []
    for i, raw in enumerate(raw_items):
        split = raw.get("split")
        if split not in ("tune", "gate"):
            raise GoldSetError(
                f"item {i}: split must be 'tune' or 'gate', got {split!r}"
            )
        query = raw.get("query")
        if not isinstance(query, str) or not query:
            raise GoldSetError(f"item {i}: 'query' must be a non-empty string")
        relevant = tuple(raw.get("relevant", []) or [])
        kind = raw.get("kind", "positive")
        items.append(GoldItem(query=query, relevant=relevant, split=split, kind=kind))
    _validate_disjoint(items)
    return GoldSet(items=items, version=version)


def load_goldset(path: str | Path) -> GoldSet:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return parse_goldset(data)
