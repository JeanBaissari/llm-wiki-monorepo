# ADR 0032: Recommended-Extras Profile + GLiNER `[ner]` Torch-Free Local Path

- **Status:** accepted
- **Date:** 2026-08-11
- **Context:** LWM_037 (v0.6.0, absorbs backlog BKD-007) — five optional extras (`semantic`, `leiden`, `entity-resolution`, `ner`, `eval`) existed but users had to know each one by name. Worse, the GLiNER `[ner]` success path (LWM_026) was CI-enforced only: `import gliner` pulls torch at package import, so a local typed-`EntitySpan` install was impractical on small disks and the "success path" was unreachable locally.

## Decision

**A `[recommended]` extras profile + a documented torch-free `[ner]` local path:**

- **`[project.optional-dependencies].recommended = ["semantic", "leiden", "entity-resolution"]`** — deliberately excludes `ner` (torch/native weight) and `eval`/`dev`/`test`. Purely additive; the base install stays lexical-only (invariant 3/8) and base-install-purity CI stays green.
- **Torch-free `[ner]`:** `import gliner` pulls torch (verified against the 0.2.13 wheel: `gliner/__init__` → `.model` → module-top `import torch`), so the torch-free path never imports `gliner`. It runs an `onnxruntime`-direct runner (`src/llm_wiki/semantic/ner_onnx.py`) against a documented end-to-end artifact contract, routed via `get_extractor("gliner[-onnx]")` / `LLM_WIKI_NER` when the env `LLM_WIKI_GLINER_MODEL` points at a prepared ONNX model.
- **Model-cache convention:** `~/.cache/llm-wiki/models/<pinned-key>/` (user-global), pinned key `gliner_small-v2.1` so CI (`ner-verification`) and local runs use identical weights; `LLM_WIKI_GLINER_MODEL` overrides the dir (also lets torch-present installs avoid re-download).
- **Graceful degradation + skip-gating unchanged:** no model/runner/torch → `is_available()` False → regex fallback byte-identical; local tests skip (never fail) when the artifact is absent; base install never imports the stack; the one-time ONNX export is a documented command under the full `[ner]` extra.
- **Measured disk budget** recorded in AGENTS.md (model ~582 MiB, onnxruntime ~12.7 MiB) — documentation, not CI-asserted.

## Delivered State

`pyproject.toml` (`recommended` extra), `src/llm_wiki/semantic/ner_onnx.py`, additive `LLM_WIKI_GLINER_MODEL` routing in `src/llm_wiki/graph/extract.py`, `tests/test_recommended_extra.py` (resolution + no-import probe), `tests/test_gliner_local_path.py` (skip-gated local success path), AGENTS.md disk-budget + recipe.

## Consequences

**Easier:** one `.[recommended]` install gives the semantic + graph-precision extras; the `[ner]` success path is locally runnable on a small disk via onnxruntime + a cached model. **Harder:** the torch-free path is partially closed — inference is implemented + tested, but the one-time ONNX export of the pinned model still requires a torch run under `[ner]` (a follow-up `[ner]`-side export command + CI artifact pinning would fully close it); the model cache is ~582 MiB, not tens-of-MB.
