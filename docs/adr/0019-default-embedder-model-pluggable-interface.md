# ADR 0019: Default Embedding Model (model2vec) + Pluggable Embedder Interface

- **Status:** accepted
- **Date:** 2026-08-06
- **Context:** LWM_015 (v0.4.0 embeddings) needed a default embedding model and a pluggable interface. The constraint set: file-first, cross-platform, offline-at-inference (no torch, no network), install-size-bounded, and gated behind the `[semantic]` optional extra — with an always-safe import when the extra is absent (LWM_013 invariant #3, ADR-0015).

## Decision

A **dimension-agnostic `Embedder` interface plus a small registry**, mirroring the LLM provider-registry pattern (`src/llm_wiki/semantic/embedder.py`):

- **Interface:** `Embedder` (ABC) with `embed(texts)`, `embed_meta()`, and identity fields; `EmbedMeta` carries `model_id`, `revision`, `dimension`, `normalization`, `quantization`. `EmbedMeta` is persisted alongside the vectors and asserted by every vector reader (LWM_014 / ADR-0018) — a mismatch forces keyword fallback, never a corrupt KNN result.
- **Default model:** **model2vec `minishlab/potion-retrieval-32M`** — a *static* embedder whose inference dependency is numpy only (no torch, no network at inference), ideal for a file-first cross-platform install. `DEFAULT_MODEL_ID` is the numpy-only static default; overridable via `LLM_WIKI_EMBEDDER` (env) or the registry.
- **Registry:** `EMBEDDER_MAP` + `detect_default_embedder()` + `get_embedder()`. Heavy imports (`model2vec`, `numpy`) are deferred to call sites, never at module import.
- **§upgrade-path:** optional upgrade providers (bge-small transformer runtime, embedding APIs) remain opt-in extras, so the base install is unaffected.
- **Boundary:** this is the instantiation of the embedder facet of the semantic-layer boundary (ADR-0015 / LWM_013); the interface contract itself is documented on the protocol, not re-essayed in code.

## Delivered State (defe7e0)

Fully implemented: `embedder.py` exposes `Embedder`, `EmbedMeta`, `Model2VecEmbedder`, `DEFAULT_MODEL_ID`, `EMBEDDER_MAP`, `detect_default_embedder`, `get_embedder`, `is_semantic_available`; `semantic/__init__.py` wires the boundary (interface: LWM_015 / ADR-0019). Consumers: `vectorstore.py`, `query.py`, `linking.py`, `resolve.py`, `derived_edges.py`. No remediation batch is outstanding for this ADR.

## Consequences

**Easier:** swapping the embedder is a registry entry — no caller changes; the numpy-only default keeps inference offline and portable; embedding-space identity travels with the vectors so mixed-space KNN is impossible. **Harder:** static embeddings are similarity-only by nature — they may never be the sole basis for auto-applying merges or links (ADR-0021), and any future model upgrade invalidates stored vectors until re-embedding (`embed_meta` mismatch → keyword fallback).
