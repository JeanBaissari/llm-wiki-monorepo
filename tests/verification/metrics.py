"""
tests/verification/metrics.py

Community detection verification metrics:
  - NMI (Normalized Mutual Information) — sklearn variant
  - ARI (Adjusted Rand Index)
  - Modularity Q

Canonical implementation lives in ``src/llm_wiki/eval/cluster_metrics.py``
(ADR-0012 machinery, reused by the derived-edge NMI gate); this module re-exports
it so the verification suite and production share one implementation.
"""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SRC = os.path.join(_REPO_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from llm_wiki.eval.cluster_metrics import (  # noqa: E402,F401
    HAVE_SKLEARN,
    ari,
    modularity_q,
    nmi,
    pure_ari,
    pure_nmi,
)
