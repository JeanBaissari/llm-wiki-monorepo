"""test_contradictions.py — LWM_034 contradiction detection + confidence tests.

Evidence Matrix coverage:
  - typed claim extraction deterministic (AC#1)  -> test_claim_extraction_deterministic
  - apply/unapply reversible round-trip (AC#3)   -> test_apply_unapply_roundtrip
  - suggest-only default (detect writes nothing) -> test_suggest_only_default
  - lint pattern compatible ("contradiction signals", AC#5)
    -> test_lint_pattern_compatible
  - unit normalization: "3.2 MB" vs "3.2 MiB" NOT flagged; "3.2" vs "4.0" flagged
  - polarity negation: "is" vs "is not" flagged
  - author override: `confidence_source: author` preserved
  - `--assist llm` degrades gracefully (no provider, base path unchanged)
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from llm_wiki.quality.contradictions import (
    _analyze,
    _classify_value,
    _conflict_kind,
    _llm_screen,
    apply_contradictions,
    extract_claims,
    run,
    score_confidence,
    unapply_contradictions,
)
from llm_wiki.quality.lint.service import lint
from llm_wiki.core.frontmatter import parse_frontmatter


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════


def _write_page(root: Path, stem: str, title: str, body: str,
                extra_fm: str = "", sources: "list[str] | None" = None,
                updated: str = "2026-07-15") -> Path:
    src = ", ".join(f'"{s}"' for s in (sources or []))
    path = root / "wiki" / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"title: {title}\n"
        "type: concept\n"
        f"sources: [{src}]\n"
        f"updated: {updated}\n"
        "created: 2026-01-15\n"
        "tags: [test]\n"
        f"{extra_fm}"
        "---\n\n"
        f"# {title}\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def _contradiction_wiki(root: Path) -> Path:
    """A wiki whose prose hosts one numeric contradiction + one negative."""
    _write_page(root, "cache-subject", "Server Cache",
                "Server Cache is the shared in-memory layer.")
    _write_page(root, "server-a", "Server A", "Server Cache has 3.2 MB of cache.")
    _write_page(root, "server-b", "Server B", "Server Cache has 4.0 MB of cache.")
    _write_page(root, "size-subject", "Cache Size", "Cache Size is a deployment attribute.")
    _write_page(root, "size-a", "Deployment A", "Cache Size is 3.2 MB.")
    _write_page(root, "size-b", "Deployment B", "Cache Size is 3.2 MiB.")
    return root


def _snapshot(root: Path) -> dict:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and not any(part.startswith(".") for part in p.parts)
    }


# ══════════════════════════════════════════════════════════════════════════
# AC#1 — typed claim extraction, deterministic
# ══════════════════════════════════════════════════════════════════════════


def test_claim_extraction_deterministic(tmp_path):
    root = _contradiction_wiki(tmp_path)
    a = _analyze(str(root))
    b = _analyze(str(root))
    ser = lambda obj: json.dumps(obj, sort_keys=True, default=str)
    assert ser([c.__dict__ for c in a[2]]) == ser([c.__dict__ for c in b[2]]), \
        "claim extraction must be byte-stable"
    assert ser(a[3]) == ser(b[3]), "detection must be byte-stable"
    assert a[2], "expected typed claims"
    row = a[2][0]
    for field in ("subject", "predicate", "object", "polarity", "page", "span"):
        assert field in row.__dict__, f"ClaimRow missing {field}"


def test_claim_extraction_grounds_subjects(tmp_path):
    """Claims whose subject is not a wiki entity are not emitted."""
    root = _contradiction_wiki(tmp_path)
    _write_page(root, "ghost", "Ghost", "The Unregistered Thing is a mystery.")
    _layout, _pages, claims, _det = _analyze(str(root))
    assert all(c.subject != "unregistered thing" for c in claims)


# ══════════════════════════════════════════════════════════════════════════
# Unit normalization (resolution Q(b))
# ══════════════════════════════════════════════════════════════════════════

def test_unit_normalization_no_false_flag(tmp_path):
    """'3.2 MB' vs '3.2 MiB' are equal after normalization — NOT flagged."""
    root = _contradiction_wiki(tmp_path)  # size-a/size-b = MB vs MiB negative
    _l, _p, _c, detections = _analyze(str(root))
    pairs = {(d["claim_a"]["page"], d["claim_b"]["page"]) for d in detections}
    assert ("size-a", "size-b") not in pairs
    assert ("server-a", "server-b") in pairs  # the real 3.2 vs 4.0 conflict


def test_unit_normalization_direct():
    kind, num, unit, key = _classify_value("3.2 MB")
    assert kind == "numeric" and num == 3.2 and unit == "MiB"
    kind2, num2, unit2, key2 = _classify_value("3.2 MiB")
    assert (num2, unit2) == (num, unit)
    k3, n3, u3, _ = _classify_value("500 ms")
    assert n3 == 0.5 and u3 == "s"
    k4, n4, u4, _ = _classify_value("2 s")
    assert n4 == 2.0 and u4 == "s"


def test_value_and_polarity_conflicts_direct():
    from llm_wiki.quality.contradictions import ClaimRow
    a = ClaimRow("server cache", "has", "3.2 MB of cache", "pos", "a", "s",
                 value_kind="numeric", numeric_value=3.2, unit="MiB", object_key="3.200000|MiB")
    b = ClaimRow("server cache", "has", "4.0 MB of cache", "pos", "b", "s",
                 value_kind="numeric", numeric_value=4.0, unit="MiB", object_key="4.000000|MiB")
    assert _conflict_kind(a, b) == "value"
    p1 = ClaimRow("apollo 11", "is", "the first crewed mission", "pos", "x", "s",
                  object_key="the first crewed mission")
    p2 = ClaimRow("apollo 11", "is", "the first crewed mission", "neg", "y", "s",
                  object_key="the first crewed mission")
    assert _conflict_kind(p1, p2) == "polarity"


def test_polarity_negation_different_object_not_flagged(tmp_path):
    """'is X' vs 'is not Y' (different objects) is NOT a contradiction."""
    _write_page(tmp_path, "subj", "Apollo 11", "Apollo 11 was a crewed lunar mission.")
    _write_page(tmp_path, "a", "Timeline", "Apollo 11 is the first crewed mission to land on the Moon.")
    _write_page(tmp_path, "b", "Record", "Apollo 11 is not the first crewed mission to land on the Moon.")
    _l, _p, _c, detections = _analyze(str(tmp_path))
    assert len(detections) == 1  # only the same-object polarity pair


# ══════════════════════════════════════════════════════════════════════════
# AC#3 / invariant 5 — suggest-only default, apply/unapply round-trip
# ══════════════════════════════════════════════════════════════════════════


def test_suggest_only_default(tmp_path, capsys):
    root = _contradiction_wiki(tmp_path)
    before = _snapshot(root)
    rc = run(["detect", str(root), "--json"])
    assert rc == 0
    assert not (root / ".llm-wiki").exists(), "detect must write NOTHING"
    assert _snapshot(root) == before, "detect must not modify the wiki"


def test_apply_writes_contradictions_field(tmp_path):
    root = _contradiction_wiki(tmp_path)
    modified = apply_contradictions(str(root))
    assert modified >= 2
    fm = parse_frontmatter((root / "wiki" / "server-a.md").read_text(encoding="utf-8"))
    assert fm.get("contradictions"), "server-a must carry the contradictions field"
    assert any(str(e).startswith("ctr_") for e in fm["contradictions"])


def test_apply_is_idempotent(tmp_path):
    root = _contradiction_wiki(tmp_path)
    apply_contradictions(str(root))
    first = (root / "wiki" / "server-a.md").read_bytes()
    apply_contradictions(str(root))
    assert (root / "wiki" / "server-a.md").read_bytes() == first


def test_apply_unapply_roundtrip(tmp_path):
    """apply then unapply restores every page byte-identically + sidecar gone."""
    root = _contradiction_wiki(tmp_path)
    before = _snapshot(root)
    apply_contradictions(str(root), with_confidence=True)
    assert _snapshot(root) != before
    unapply_contradictions(str(root))
    assert _snapshot(root) == before, "unapply must restore pages byte-identically"
    assert not (root / ".llm-wiki" / "claims").exists(), "sidecar must be cleaned up"


def test_cli_apply_unapply_roundtrip(tmp_path, capsys):
    root = _contradiction_wiki(tmp_path)
    before = _snapshot(root)
    assert run(["apply", str(root), "--confidence"]) == 0
    assert run(["list", str(root)]) == 0
    assert run(["unapply", str(root)]) == 0
    assert _snapshot(root) == before
    assert run(["list", str(root)]) == 0


def test_confidence_fields_written_on_apply(tmp_path):
    root = _contradiction_wiki(tmp_path)
    apply_contradictions(str(root), with_confidence=True)
    fm = parse_frontmatter((root / "wiki" / "server-a.md").read_text(encoding="utf-8"))
    assert fm.get("confidence") in ("high", "medium", "low")
    assert fm.get("confidence_source") == "evidence"
    assert "evidence_score" in fm


# ══════════════════════════════════════════════════════════════════════════
# AC#5 — lint pattern compatible ("contradiction signals")
# ══════════════════════════════════════════════════════════════════════════


def test_lint_pattern_compatible(tmp_path, capsys):
    """Detected prose contradictions report through the existing lint block."""
    root = _contradiction_wiki(tmp_path)
    rc = lint(str(root))
    out = capsys.readouterr().out
    assert "Pages with contradictions" in out, "detector findings must use the existing header"
    assert "wiki/server-a.md" in out and "wiki/server-b.md" in out
    assert rc == 1


def test_lint_reports_author_set_contradictions(tmp_path, capsys):
    """Author-set `contested: true` still triggers the same existing block."""
    root = _contradiction_wiki(tmp_path)
    _write_page(tmp_path, "contested", "Contested Entity", "This entity has contradictions.",
                extra_fm="contested: true\n")
    rc = lint(str(root))
    out = capsys.readouterr().out
    assert "Pages with contradictions" in out
    assert "wiki/contested.md" in out
    assert rc == 1


# ══════════════════════════════════════════════════════════════════════════
# AC#4 / resolution Q(a) — confidence scorer + author override
# ══════════════════════════════════════════════════════════════════════════


def test_no_evidence_scores_low_never_high(tmp_path):
    _write_page(tmp_path, "bare", "Bare Page", "Bare Page is an unsupported assertion.",
                sources=[], updated="")
    scores = score_confidence(str(tmp_path))
    res = scores["bare"]
    assert res["label"] == "low"
    assert res["evidence_score"] < 0.4


def test_author_override_preserved(tmp_path):
    root = tmp_path
    _write_page(root, "authored", "Authored Page",
                "Authored Page is a documented claim.",
                extra_fm="confidence: low\nconfidence_source: author\n",
                sources=["src-a"], updated="2026-08-01")
    (root / "raw").mkdir(exist_ok=True)
    (root / "raw" / "src-a.md").write_text("# Src\n", encoding="utf-8")
    scores = score_confidence(str(root))
    res = scores["authored"]
    assert res["confidence_source"] == "author"
    assert res["write_confidence"] is False
    # even a strong evidence signal must not overwrite the author value
    assert res["label"] in ("high", "medium", "low")


def test_author_confidence_not_overwritten_on_apply(tmp_path):
    root = tmp_path
    _write_page(root, "subj", "Server Cache", "Server Cache is a shared layer.",
                extra_fm="confidence: high\nconfidence_source: author\n",
                sources=["src-a"], updated="2026-08-01")
    _write_page(root, "a", "Server A", "Server Cache has 3.2 MB of cache.",
                sources=["src-a"], updated="2026-08-01")
    _write_page(root, "b", "Server B", "Server Cache has 4.0 MB of cache.",
                sources=["src-a"], updated="2026-08-01")
    (root / "raw").mkdir(exist_ok=True)
    (root / "raw" / "src-a.md").write_text("# Src\n", encoding="utf-8")
    apply_contradictions(str(root), with_confidence=True)
    fm = parse_frontmatter((root / "wiki" / "subj.md").read_text(encoding="utf-8"))
    assert fm.get("confidence") == "high"
    assert fm.get("confidence_source") == "author"
    fm_a = parse_frontmatter((root / "wiki" / "a.md").read_text(encoding="utf-8"))
    assert fm_a.get("confidence_source") == "evidence"


def test_confidence_labels_match_gold(tmp_path):
    """The scorer separates high/medium/low on the gold wiki."""
    from llm_wiki.eval.contradiction_baseline import build_contradiction_gold_wiki
    root = build_contradiction_gold_wiki(tmp_path)
    scores = score_confidence(str(root))
    assert scores["well-evidenced"]["label"] == "high"
    assert scores["moderately-evidenced"]["label"] == "medium"
    assert scores["thinly-evidenced"]["label"] == "low"
    assert scores["no-evidence"]["label"] == "low"


# ══════════════════════════════════════════════════════════════════════════
# --assist llm degrades gracefully (invariant 8)
# ══════════════════════════════════════════════════════════════════════════


def test_assist_llm_degrades_gracefully(tmp_path, capsys):
    root = _contradiction_wiki(tmp_path)
    _l, _p, _c, detections = _analyze(str(root))
    before = json.dumps(detections, sort_keys=True, default=str)
    out = _llm_screen(detections, "llm")
    assert json.dumps(out, sort_keys=True, default=str) == before
    err = capsys.readouterr().err
    assert "hint:" in err, "absent provider must emit a clear hint"
    assert "base path unchanged" in err


def test_assist_unknown_backend_hints(tmp_path, capsys):
    _l, _p, _c, detections = _analyze(str(_contradiction_wiki(tmp_path)))
    out = _llm_screen(detections, "gemini")
    assert out == detections
    assert "unknown --assist backend" in capsys.readouterr().err


def test_assist_screen_fn_filters(tmp_path):
    _l, _p, _c, detections = _analyze(str(_contradiction_wiki(tmp_path)))
    keep = detections[:1]
    out = _llm_screen(detections, "llm", screen_fn=lambda d: keep)
    assert out == keep


# ══════════════════════════════════════════════════════════════════════════
# Sidecar records reuse the ClaimsManager surface
# ══════════════════════════════════════════════════════════════════════════


def test_apply_persists_claims_and_contradictions(tmp_path):
    root = _contradiction_wiki(tmp_path)
    apply_contradictions(str(root))
    from llm_wiki.quality.claims.storage import ClaimsManager, has_sidecar
    assert has_sidecar(str(root))
    mgr = ClaimsManager(str(root))
    claims = mgr.get_all_claims()
    ctrs = mgr.get_all_contradictions()
    assert claims, "detected claims must persist to the claims sidecar"
    assert all(c.get("operation") == "contradictions-apply" for c in claims)
    assert ctrs and all(c.get("operation") == "contradictions-apply" for c in ctrs)
    assert any(c.get("claim_id", "").startswith("clm_") for c in claims)
