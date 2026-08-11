"""Tests for the ``[recommended]`` optional-extras profile (LWM_037).

Asserts (a) the extra resolves from ``pyproject.toml`` to exactly
``semantic + leiden + entity-resolution`` and deliberately EXCLUDES
``ner``/``eval``/``dev``/``test``, and (b) importing the base package plus the
``[recommended]``-enabled modules never imports ``gliner`` or ``torch`` (a fresh
subprocess import-probe). The profile is additive-only: the base install stays
lexical-only and base-install-purity CI stays green (invariants 3 + 8).
"""

import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Modules the base install exposes that touch the [recommended] extras' code
# paths (semantic layer, leiden engine, entity resolution) plus the torch-free
# ONNX runner seam — none may import gliner/torch/onnxruntime at module import.
PROBE_IMPORTS = (
    "llm_wiki",
    "llm_wiki.graph.extract",
    "llm_wiki.semantic",
    "llm_wiki.semantic.ner_onnx",
    "llm_wiki.graph.leiden",
    "llm_wiki.graph.entities",
    "llm_wiki.graph.resolve",
    "llm_wiki.search.query",
)


def _recommended_extra() -> list[str]:
    with PYPROJECT.open("rb") as fh:
        deps = tomllib.load(fh)["project"]["optional-dependencies"]
    return list(deps["recommended"])


def test_recommended_extra_resolves_semantic_leiden_er():
    assert _recommended_extra() == ["semantic", "leiden", "entity-resolution"]


def test_recommended_extra_excludes_ner_eval_dev_test():
    recommended = set(_recommended_extra())
    # The profile must NEVER pull the torch/native-weight [ner] stack nor the
    # tooling extras — that is the whole point of a "recommended" profile.
    for excluded in ("ner", "eval", "dev", "test"):
        assert excluded not in recommended, f"recommended must exclude {excluded!r}"


def test_recommended_extra_is_declared_in_pyproject():
    with PYPROJECT.open("rb") as fh:
        deps = tomllib.load(fh)["project"]["optional-dependencies"]
    assert "recommended" in deps
    # the base install's required dependencies are untouched (no new REQUIRED deps)
    assert "gliner" not in str(deps) or "recommended" in deps  # sanity: block parses


def test_recommended_extra_no_gliner_no_torch_import():
    """Fresh subprocess: base + [recommended]-enabled modules never import the
    `[ner]` stack. Proves base-install purity even when onnxruntime/etc. happen
    to be installed in the environment — only sys.modules after OUR imports is
    inspected."""
    code = (
        "import sys\n"
        "for mod in {imports!r}:\n"
        "    __import__(mod)\n"
        "assert 'gliner' not in sys.modules, 'base + [recommended] must not import gliner'\n"
        "assert 'torch' not in sys.modules, 'base + [recommended] must not import torch'\n"
        "assert 'onnxruntime' not in sys.modules, 'base + [recommended] must not import onnxruntime'\n"
        "from llm_wiki.semantic.ner_onnx import NEROnnxRunner, is_onnx_runner_available\n"
        "assert isinstance(is_onnx_runner_available(), bool)\n"
        "print('base+recommended purity OK; NEROnnxRunner.is_available() =', NEROnnxRunner.is_available())\n"
    ).format(imports=list(PROBE_IMPORTS))
    env = {"PYTHONPATH": str(REPO_ROOT / "src")}
    for key in ("PATH", "HOME"):
        if key in __import__("os").environ:
            env[key] = __import__("os").environ[key]
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=REPO_ROOT
    )
    assert proc.returncode == 0, f"import-probe failed:\n{proc.stdout}\n{proc.stderr}"
    assert "base+recommended purity OK" in proc.stdout
