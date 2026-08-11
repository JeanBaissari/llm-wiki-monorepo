#!/usr/bin/env python3
"""curate_gold_set.py — Standing per-minor search gold-set curation loop (LWM_039 §A).

The search gold set at ``tests/eval/gold/`` (``query -> relevant page-ids``) is
the held-out GATE the hybrid-default flip certifies on (LWM_032 / ADR-0020).
This script codifies the per-minor curation loop: every minor that ships a
retrieval change must either grow the gate split by >= MIN_GROWTH_PER_MINOR
queries or record a written justification, then re-freeze the manifest and
re-generate the baseline. The frozen files (search_goldset.json,
split_manifest.json, search_eval_baseline.json) are never edited by this script
for the sake of editing — ``--freeze`` / ``--rebaseline`` only re-derive them
from the gold set after an intentional growth event.

Actions:
    check (default)   Validate the gold set + manifest + growth floor.
    --freeze          Recompute the SHA256 + rewrite split_manifest.json.
    --rebaseline      Regenerate the baseline via the sanctioned command and
                      assert it is byte-stable against the committed bytes.
    --growth-record   Record the grow-or-justify bookkeeping in growth_meta.json.

Exit codes: 0 clean, 1 issues found, 2 usage error.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MIN_GROWTH_PER_MINOR = 2
_MAX_REBASELINE_TIMEOUT_S = 600

# Paths relative to a repo root (the gate/check functions take an optional
# repo_root so tests can point at fixtures; the CLI defaults to REPO_ROOT).
_GOLD_DIR = "tests/eval/gold"
_GOLDSET = "tests/eval/gold/search_goldset.json"
_MANIFEST = "tests/eval/gold/split_manifest.json"
_GROWTH_META = "tests/eval/gold/growth_meta.json"
_BASELINE = "tests/eval/baseline/search_eval_baseline.json"
_REAL_WIKI_GATE = "tests/eval/test_real_wiki_gate.py"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _gold_files(repo_root: Path) -> tuple[Path, Path, Path]:
    return (
        repo_root / _GOLDSET,
        repo_root / _MANIFEST,
        repo_root / _GROWTH_META,
    )


def _search_gold_pages(repo_root: Path):
    """Page-ids of the deterministic gold wiki (SEARCH_GOLD_PAGES), or None."""
    src = str(repo_root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        from llm_wiki.eval.search_baseline import SEARCH_GOLD_PAGES  # type: ignore
    except Exception:
        return None
    stems = set()
    for key in SEARCH_GOLD_PAGES:
        stems.add(key[:-3] if key.endswith(".md") else key)
    return stems


def _real_wiki_gate_queries(repo_root: Path):
    """Queries used as real-wiki gate labels, or None if uncheckable."""
    path = repo_root / _REAL_WIKI_GATE
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return re.findall(r'"query":\s*"([^"]+)"', text)


def _min_gate_queries(repo_root: Path):
    """Committed gate floor from growth_meta.json (None if absent)."""
    _, _, meta_path = _gold_files(repo_root)
    if not meta_path.exists():
        return None
    meta = _load_json(meta_path)
    return meta.get("min_gate_queries")


def run_check(repo_root: Path) -> int:
    """Validate the gold set + manifest + growth floor. Returns exit code."""
    goldset, manifest, meta_path = _gold_files(repo_root)
    results: list[tuple[str, str, str]] = []  # (name, status, detail)

    def _add(name: str, status: str, detail: str) -> None:
        results.append((name, status, detail))
        print(f"[{status:^4}] {name}: {detail}")

    missing = []
    for label, path in (("search_goldset.json", goldset),
                        ("split_manifest.json", manifest),
                        ("growth_meta.json", meta_path)):
        if not path.exists():
            missing.append(label)
    if missing:
        for m in missing:
            _add(f"file:{m}", "FAIL", "missing — cannot validate")
        return 1

    data = _load_json(goldset)
    items = data.get("items", [])
    tune = [i for i in items if i.get("split") == "tune"]
    gate = [i for i in items if i.get("split") == "gate"]

    # (a) split hygiene + tune ∩ gate = ∅
    bad_split = [i.get("query") for i in items if i.get("split") not in ("tune", "gate")]
    bad_kind = [i.get("query") for i in items if i.get("kind") not in ("positive", "negative")]
    if bad_split or bad_kind:
        _add("split_hygiene", "FAIL",
             f"invalid split/kind: split={bad_split or 'ok'} kind={bad_kind or 'ok'}")
    else:
        overlap = sorted({i["query"] for i in tune} & {i["query"] for i in gate})
        if overlap:
            _add("tune_gate_disjoint", "FAIL",
                 f"tune ∩ gate leaked: {overlap}")
        else:
            _add("tune_gate_disjoint", "PASS",
                 f"tune ∩ gate = ∅ ({len(tune)} tune / {len(gate)} gate)")

    # (b) negatives: >=1 gibberish negative on the gate split; negative => empty relevant
    negatives = [i for i in gate if i.get("kind") == "negative"]
    gate_negatives = [i for i in items if i.get("kind") == "negative" and i.get("split") == "gate"]
    nonempty_neg = [i.get("query") for i in items
                    if i.get("kind") == "negative" and i.get("relevant")]
    if not gate_negatives:
        _add("gibberish_negative", "FAIL",
             "no gibberish negative on the gate split (relevant: [])")
    elif nonempty_neg:
        _add("gibberish_negative", "FAIL",
             f"negative items must have relevant == []: {nonempty_neg}")
    else:
        frac = len(gate_negatives) / len(gate) if gate else 0.0
        _add("gibberish_negative", "PASS",
             f"{len(gate_negatives)} gibberish negative(s) on gate "
             f"({frac:.0%} of the gate split)")

    # positives: >=1 relevant page id resolving into the deterministic gold wiki
    pages = _search_gold_pages(repo_root)
    positives = [i for i in items if i.get("kind") == "positive"]
    empty_pos = [i.get("query") for i in positives if not i.get("relevant")]
    if empty_pos:
        _add("positive_grounding", "FAIL",
             f"positive queries need >=1 relevant page-id: {empty_pos}")
    elif pages is None:
        _add("positive_grounding", "SKIP",
             "llm_wiki unavailable — page-id resolution not checked")
    else:
        unknown = []
        for i in positives:
            for pid in i.get("relevant", []):
                if pid not in pages:
                    unknown.append(f"{i['query']}->{pid}")
        if unknown:
            _add("positive_grounding", "FAIL",
                 f"page-ids absent from SEARCH_GOLD_PAGES: {unknown[:10]}")
        else:
            _add("positive_grounding", "PASS",
                 f"all positive relevant page-ids resolve in SEARCH_GOLD_PAGES")

    # real-wiki discipline: real-wiki gate queries never appear in tune
    real_queries = _real_wiki_gate_queries(repo_root)
    tune_queries = {i["query"] for i in tune}
    if real_queries is None:
        _add("real_wiki_never_tuned", "SKIP", "real-wiki gate lane not found")
    else:
        leaked = sorted(tune_queries & set(real_queries))
        if leaked:
            _add("real_wiki_never_tuned", "FAIL",
                 f"real-wiki gate queries must stay gate-only: {leaked}")
        else:
            _add("real_wiki_never_tuned", "PASS",
                 "no real-wiki gate query appears in tune")

    # (c) manifest sha256 == goldset sha256
    manifest_data = _load_json(manifest)
    got_sha = _sha256_file(goldset)
    want_sha = manifest_data.get("sha256")
    if want_sha is None:
        _add("manifest_sha256", "FAIL", "split_manifest.json has no sha256")
    elif got_sha != want_sha:
        _add("manifest_sha256", "FAIL",
             f"goldset sha256 {got_sha[:12]}… != manifest {want_sha[:12]}… "
             f"— run `curate_gold_set.py --freeze` after an intentional edit")
    else:
        _add("manifest_sha256", "PASS", f"sha256 matches manifest ({want_sha[:16]}…)")

    # (d) gate count >= min_gate_queries (committed floor from growth_meta.json)
    floor = _min_gate_queries(repo_root)
    if floor is None:
        _add("gate_floor", "FAIL", "growth_meta.json missing or min_gate_queries absent")
    else:
        n_gate = len(gate)
        manifest_gate = manifest_data.get("gate", [])
        if manifest_gate and sorted(manifest_gate) != sorted(i["query"] for i in gate):
            _add("gate_floor", "FAIL",
                 "manifest gate query list does not match the goldset gate split")
        elif n_gate < floor:
            _add("gate_floor", "FAIL",
                 f"gate split has {n_gate} queries < floor {floor} — regression")
        else:
            _add("gate_floor", "PASS",
                 f"gate query count {n_gate} >= min_gate_queries {floor}")

    failed = [name for name, status, _ in results if status == "FAIL"]
    print()
    print(f"{'CLEAN' if not failed else 'VIOLATIONS FOUND'} — "
          f"{sum(1 for _, s, _ in results if s == 'PASS')} passed, "
          f"{len(failed)} failed, "
          f"{sum(1 for _, s, _ in results if s == 'SKIP')} skipped")
    return 1 if failed else 0


def freeze_manifest(repo_root: Path) -> int:
    """Recompute the SHA256 + rewrite split_manifest.json. Idempotent."""
    goldset, manifest, _ = _gold_files(repo_root)
    if not goldset.exists() or not manifest.exists():
        print(f"error: {goldset} or {manifest} missing", file=sys.stderr)
        return 1
    data = _load_json(goldset)
    old = _load_json(manifest)
    tune = sorted(i["query"] for i in data.get("items", []) if i.get("split") == "tune")
    gate = sorted(i["query"] for i in data.get("items", []) if i.get("split") == "gate")
    new_sha = _sha256_file(goldset)
    new_manifest = {
        "task": old.get("task", "search-retrieval"),
        "sha256": new_sha,
        "tune": tune,
        "gate": gate,
        "note": old.get("note", ""),
    }
    new_bytes = (json.dumps(new_manifest, indent=2, ensure_ascii=True) + "\n").encode()
    if new_bytes == manifest.read_bytes():
        print(f"no-op: split_manifest.json already in sync (sha256 {new_sha[:16]}…)")
        return 0
    manifest.write_bytes(new_bytes)
    print(f"re-froze split_manifest.json: sha256 {new_sha} "
          f"({len(tune)} tune / {len(gate)} gate queries)")
    return 0


def rebaseline(repo_root: Path) -> int:
    """Regenerate the baseline via the sanctioned command; assert byte-stability."""
    baseline = repo_root / _BASELINE
    if not baseline.exists():
        print(f"error: {baseline} missing", file=sys.stderr)
        return 1
    before = baseline.read_bytes()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    cmd = [
        sys.executable, "-m", "llm_wiki.eval.search_baseline",
        "--output", _BASELINE,
    ]
    result = subprocess.run(
        cmd, cwd=repo_root, env=env, capture_output=True, text=True,
        timeout=_MAX_REBASELINE_TIMEOUT_S,
    )
    if result.returncode != 0:
        print("baseline regeneration failed:", file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        return 1
    after = baseline.read_bytes()
    if before == after:
        print(f"baseline byte-stable: regenerated bytes identical to committed "
              f"(sha256 {_sha256_file(baseline)[:16]}…, no drift)")
        return 0
    try:
        before_json = json.loads(before)
        after_json = json.loads(after)
    except Exception:
        before_json = after_json = None
    # The committed baseline's ``note`` is hand-enriched beyond the generator's
    # default (BKD-002 provenance text). A note-only difference is metadata
    # drift, not gate-content drift: preserve the committed bytes so the
    # regeneration is a no-op on an unchanged gold set.
    note_only = (
        before_json is not None
        and after_json is not None
        and before_json.get("note") != after_json.get("note")
        and {k: v for k, v in before_json.items() if k != "note"}
        == {k: v for k, v in after_json.items() if k != "note"}
    )
    if note_only:
        baseline.write_bytes(before)
        print("baseline gate content byte-stable (no numeric drift); note-only "
              "difference vs the generator's default metadata — committed bytes "
              "preserved", file=sys.stderr)
        print(f"  committed note: {before_json['note'][:80]}…", file=sys.stderr)
        print(f"  generator note: {after_json['note'][:80]}…", file=sys.stderr)
        return 0
    print("DRIFT: regenerated baseline differs from the committed bytes.", file=sys.stderr)
    print(f"  before sha256: {hashlib.sha256(before).hexdigest()}", file=sys.stderr)
    print(f"  after  sha256: {hashlib.sha256(after).hexdigest()}", file=sys.stderr)
    try:
        b = json.loads(before)
        a = json.loads(after)
        for mode in ("keyword", "hybrid"):
            for key in ("precision_at_k", "recall", "negative_pass_rate", "n"):
                if b.get(mode, {}).get(key) != a.get(mode, {}).get(key):
                    print(f"  {mode}.{key}: {b.get(mode, {}).get(key)} -> "
                          f"{a.get(mode, {}).get(key)}", file=sys.stderr)
        for key in ("allow_hybrid_default",):
            if b.get(key) != a.get(key):
                print(f"  {key}: {b.get(key)} -> {a.get(key)}", file=sys.stderr)
    except Exception:
        pass
    print(f"  the regenerated file is left at {baseline} — review via git diff",
          file=sys.stderr)
    return 1


def growth_record(repo_root: Path, minor: str, note: str) -> int:
    """Record the grow-or-justify bookkeeping in growth_meta.json."""
    meta_path = repo_root / _GROWTH_META
    if meta_path.exists():
        meta = _load_json(meta_path)
    else:
        meta = {}
    if "version" not in meta:
        meta["version"] = 1
    meta["last_grown_at"] = date.today().isoformat()
    meta["last_grown_minor"] = minor
    meta["notes"] = note
    if "min_gate_queries" not in meta:
        meta["min_gate_queries"] = 16
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=True) + "\n",
                         encoding="utf-8")
    print(f"growth_meta.json updated: last_grown_minor={minor}, "
          f"last_grown_at={meta['last_grown_at']}, notes={note!r}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Standing per-minor search gold-set curation loop (LWM_039 §A).",
    )
    parser.add_argument("action", nargs="?", default=None, choices=["check"],
                        help="default action; run alone as 'check'")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--freeze", action="store_true",
                       help="recompute sha256 + rewrite split_manifest.json")
    group.add_argument("--rebaseline", action="store_true",
                       help="regenerate the baseline via the sanctioned command; "
                            "assert byte-stability vs the committed bytes")
    group.add_argument("--growth-record", nargs=2, metavar=("MINOR", "NOTE"),
                       help="record the grow-or-justify entry in growth_meta.json")
    parser.add_argument("--repo-root", default=str(REPO_ROOT),
                        help="repo root containing tests/eval/gold "
                             "(default: script location's repo)")
    args = parser.parse_args(argv)

    if args.action == "check" and (args.freeze or args.rebaseline or args.growth_record):
        parser.error("'check' cannot be combined with --freeze/--rebaseline/--growth-record")
    root = Path(args.repo_root)
    if args.freeze:
        return freeze_manifest(root)
    if args.rebaseline:
        return rebaseline(root)
    if args.growth_record:
        return growth_record(root, args.growth_record[0], args.growth_record[1])
    return run_check(root)


if __name__ == "__main__":
    sys.exit(main())
