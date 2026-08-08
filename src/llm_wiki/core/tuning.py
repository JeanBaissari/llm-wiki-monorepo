#!/usr/bin/env python3
"""tuning.py — ``llm-wiki tuning``: resolve + emit the canonical tuning config (LWM_031).

The emit surface for the resolved ``TuningConfig``: applies the full
CLI > env > file > code-default resolution (a wiki's ``tuning.toml`` when a root
is given, ``LLM_WIKI_TUNE__*`` env vars, ``--set`` overrides) and prints either a
human-readable flat map or the graph-engine JSON profile (``--json`` /
``--emit <path>``) that ``graph-engine --tuning-json`` consumes — so a tuned
profile travels from Python to TypeScript without re-derivation.

Exit codes: 0 = emitted, 2 = fail-closed config error (unknown key / out of range).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def emit_profile(wiki_root: "Optional[str]" = None,
                 overrides: "Optional[list[str]]" = None,
                 env: "Optional[dict[str, str]]" = None) -> dict:
    """Resolve the tuning profile (CLI > env > file > default) as graph-engine JSON.

    Raises ``ConfigError`` (fail-closed) on unknown keys / out-of-range values.
    """
    from llm_wiki.core.config import resolve_tuning
    tuning = resolve_tuning(wiki_root, cli_overrides=overrides, env=env)
    return tuning.to_graph_engine_json()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve and emit the canonical tuning config (LWM_031). "
                    "Precedence: --set > LLM_WIKI_TUNE__* env > <wiki>/tuning.toml > code defaults.",
    )
    parser.add_argument("wiki_root", nargs="?", default=None,
                        help="Path to the wiki project root (reads tuning.toml from it, if present)")
    parser.add_argument("--set", action="append", default=[], dest="overrides",
                        metavar="section.key=value",
                        help="Tuning override (repeatable, highest precedence), "
                             "e.g. --set relevance.directLink=5")
    parser.add_argument("--json", action="store_true",
                        help="Emit the resolved profile as graph-engine JSON (to_graph_engine_json())")
    parser.add_argument("--emit", metavar="PATH",
                        help="Write the JSON profile to PATH (implies --json)")
    args = parser.parse_args()

    from llm_wiki.core.config import ConfigError
    try:
        profile = emit_profile(args.wiki_root, args.overrides)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    if args.emit:
        target = Path(args.emit)
        target.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
        print(f"tuning profile written to {target}", file=sys.stderr)
        return 0

    if args.json:
        print(json.dumps(profile, indent=2))
        return 0

    from llm_wiki.core.config import TuningConfig
    defaults = profile_to_flat(TuningConfig().to_graph_engine_json())
    flat = {k: v for k, v in sorted(profile_to_flat(profile).items())}
    over = {k: v for k, v in flat.items() if v != defaults.get(k)}
    for k, v in flat.items():
        marker = "  (default)" if k not in over else ""
        print(f"{k} = {v!r}{marker}")
    if over:
        print(f"\n{len(over)} override(s) active: {', '.join(sorted(over))}", file=sys.stderr)
    return 0


def profile_to_flat(profile: dict) -> dict:
    """Flatten a to_graph_engine_json() profile back into dotted keys (for display)."""
    out: dict = {}
    for section, tbl in profile.items():
        for k, v in tbl.items():
            _flatten(section + "." + k, v, out)
    return out


def _flatten(prefix: str, value, out: dict) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}.{k}", v, out)
    else:
        out[prefix] = value


if __name__ == "__main__":
    sys.exit(main())
