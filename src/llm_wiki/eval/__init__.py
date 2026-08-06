"""eval — semantic retrieval / link-suggestion evaluation harness (LWM_022).

Stdlib-only core (metrics + gold set + evaluator) so it always runs, regardless
of the ``[semantic]`` / ``[eval]`` extras. The optional ``[eval]`` extra adds
DeepEval for LLM-judged metrics layered on top of these deterministic ones.

Enforces the disjoint tune/gate split (ADR-0022): the set used to tune constants
is never the set used to gate releases.
"""

from llm_wiki.eval.goldset import (
    GoldItem,
    GoldSet,
    GoldSetError,
    gate_only,
    load_goldset,
    parse_goldset,
    tune_only,
)
from llm_wiki.eval.harness import EvalReport, evaluate
from llm_wiki.eval.metrics import (
    f1,
    mean,
    negative_pass,
    precision_at_k,
    recall_at_k,
)

__all__ = [
    "GoldItem",
    "GoldSet",
    "GoldSetError",
    "gate_only",
    "tune_only",
    "load_goldset",
    "parse_goldset",
    "EvalReport",
    "evaluate",
    "precision_at_k",
    "recall_at_k",
    "f1",
    "negative_pass",
    "mean",
]
