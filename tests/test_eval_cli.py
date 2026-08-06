"""test_eval_cli.py — Tests for the link-suggestion eval baseline + CLI (LWM_022).

Deterministic and offline (no network, no LLM). Runs the CURRENT lexical
link-suggester over the `populated` fixture wiki, scores it against the committed
seed gold set, and checks:
  - the seed loads and its tune/gate splits are disjoint by query;
  - predictions_for() is grounded in the real fixture pages;
  - the EvalReport has sane, in-range fields (and the exact seed values);
  - the split filter is respected (gate scores only gate items);
  - the gibberish negative is scored by negative_pass;
  - `llm-wiki eval` emits valid JSON and writes the baseline artifact, exit 0.
"""

import json
from pathlib import Path

import pytest

from llm_wiki.eval import EvalReport, evaluate, load_goldset
from llm_wiki.eval.baseline import predictions_for, run_link_suggest_baseline
from llm_wiki.eval.cli import main as eval_main

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_WIKI = REPO_ROOT / "tests" / "fixtures" / "wikis" / "populated"
SEED_GOLDSET = REPO_ROOT / "tests" / "eval" / "fixtures" / "goldset_seed.json"


@pytest.fixture
def goldset():
    return load_goldset(SEED_GOLDSET)


# ── gold set: loads + disjoint splits ───────────────────────────────────────

def test_seed_goldset_loads_and_splits_disjoint(goldset):
    tune_q = {it.query for it in goldset.tune}
    gate_q = {it.query for it in goldset.gate}
    assert tune_q and gate_q
    assert tune_q.isdisjoint(gate_q)  # ADR-0022: tune ∩ gate = ∅
    # At least one gibberish negative lives in the gate split.
    assert any(it.is_negative for it in goldset.gate)


def test_seed_targets_are_real_fixture_pages(goldset):
    stems = {p.stem for p in (FIXTURE_WIKI / "wiki").rglob("*.md")}
    for it in goldset.items:
        for target in it.relevant:
            assert target in stems, f"gold target {target!r} is not a real page"


# ── predictions grounded in the fixture ─────────────────────────────────────

def test_predictions_for_is_deterministic_and_grounded():
    preds = predictions_for(FIXTURE_WIKI)
    # The lexical suggester surfaces exactly these missing-link candidates.
    assert preds["cnn"] == ["neural_network"]
    assert preds["pytorch"] == ["deep_learning"]
    assert preds["tensorflow"] == ["deep_learning"]
    # deep_learning mentions "Neural Network" only inside an existing wikilink,
    # so the suggester surfaces nothing — a genuine recall miss.
    assert "deep_learning" not in preds
    # Fully deterministic across repeated runs.
    assert predictions_for(FIXTURE_WIKI) == preds


# ── EvalReport: sane fields + exact seed baseline ───────────────────────────

def test_baseline_report_fields_are_sane(goldset):
    report = run_link_suggest_baseline(FIXTURE_WIKI, goldset, k=5)
    assert isinstance(report, EvalReport)
    for value in (
        report.precision_at_k,
        report.recall_at_k,
        report.f1,
        report.negative_pass_rate,
    ):
        assert 0.0 <= value <= 1.0
    assert report.k == 5
    assert report.split == "gate"
    assert report.n_positive == 4
    assert report.n_negative == 1


def test_baseline_report_matches_seed_values(goldset):
    report = run_link_suggest_baseline(FIXTURE_WIKI, goldset, k=5)
    # 3 of 4 gate positives hit (cnn, pytorch, tensorflow); deep_learning missed.
    assert report.precision_at_k == 0.75
    assert report.recall_at_k == 0.75
    assert report.f1 == 0.75
    assert report.negative_pass_rate == 1.0


# ── split filter is respected ───────────────────────────────────────────────

def test_split_filter_scores_only_that_split(goldset):
    gate = run_link_suggest_baseline(FIXTURE_WIKI, goldset, k=5, split="gate")
    tune = run_link_suggest_baseline(FIXTURE_WIKI, goldset, k=5, split="tune")
    all_ = run_link_suggest_baseline(FIXTURE_WIKI, goldset, k=5, split=None)

    assert gate.n_positive + gate.n_negative == len(goldset.gate)
    assert tune.n_positive + tune.n_negative == len(goldset.tune)
    assert all_.n_positive + all_.n_negative == len(goldset.items)
    # Gate scoring never sees a tune item (4 gate positives + 1 gate negative).
    assert gate.n_positive == 4 and gate.n_negative == 1
    assert tune.n_positive == 3 and tune.n_negative == 1


# ── negative is scored by negative_pass ─────────────────────────────────────

def test_gibberish_negative_scored_by_negative_pass(goldset):
    # Real run: the gibberish gate query yields no prediction → pass.
    report = run_link_suggest_baseline(FIXTURE_WIKI, goldset, k=5)
    assert report.n_negative == 1
    assert report.negative_pass_rate == 1.0

    # Direct proof it is negative_pass (not recall) doing the scoring: force the
    # gibberish query to "return" something and the negative pass rate collapses.
    neg_query = next(it.query for it in goldset.gate if it.is_negative)
    doctored = dict(predictions_for(FIXTURE_WIKI))
    doctored[neg_query] = ["neural_network"]  # a non-empty (wrong) result
    bad = evaluate(doctored, goldset, k=5, split="gate")
    assert bad.negative_pass_rate == 0.0


# ── CLI ──────────────────────────────────────────────────────────────────────

def test_cli_json_is_valid_and_exit_zero(capsys):
    rc = eval_main([str(FIXTURE_WIKI), "--goldset", str(SEED_GOLDSET), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["split"] == "gate"
    assert payload["k"] == 5
    assert payload["precision_at_k"] == 0.75
    assert 0.0 <= payload["negative_pass_rate"] <= 1.0
    assert set(payload) >= {
        "k",
        "split",
        "n_positive",
        "n_negative",
        "precision_at_k",
        "recall_at_k",
        "f1",
        "negative_pass_rate",
    }


def test_cli_human_output_exit_zero(capsys):
    rc = eval_main([str(FIXTURE_WIKI), "--goldset", str(SEED_GOLDSET)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "precision@5" in out
    assert "Split:" in out


def test_cli_baseline_out_writes_valid_artifact(tmp_path, capsys):
    out_path = tmp_path / "baseline" / "eval_baseline.json"
    rc = eval_main(
        [
            str(FIXTURE_WIKI),
            "--goldset",
            str(SEED_GOLDSET),
            "--baseline-out",
            str(out_path),
        ]
    )
    assert rc == 0
    assert out_path.is_file()
    artifact = json.loads(out_path.read_text(encoding="utf-8"))
    assert artifact["precision_at_k"] == 0.75
    assert artifact["split"] == "gate"


def test_cli_missing_goldset_is_usage_error(capsys):
    rc = eval_main([str(FIXTURE_WIKI), "--goldset", str(tmp_missing())])
    assert rc == 2


def tmp_missing() -> Path:
    return REPO_ROOT / "tests" / "eval" / "fixtures" / "does_not_exist.json"
