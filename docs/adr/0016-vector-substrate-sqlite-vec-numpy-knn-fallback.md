# ADR 0016: Vector Substrate — sqlite-vec + Mandatory NumPy KNN Fallback

- **Status:** accepted
- **Date:** 2026-08-06
- **Context:** LWM_017 (v0.4.0 vector store) needed a vector retrieval substrate for the `[semantic]` optional extra. The base install must stay pure-stdlib/lexical-only, and any native extension (sqlite-vec) may be absent or unloadable on a given Python build — so the substrate had to be chosen with a mandatory fallback, and the routing between paths had to be fail-open by contract.

## Decision

The vector substrate is **sqlite-vec (`vec0`) when it loads, with a mandatory pure-numpy cosine KNN as the always-available fallback** (`src/llm_wiki/semantic/vectorstore.py`):

- **Storage** (ADR-0018 / LWM_014): both paths read from the additive `page_vectors` float32 BLOB table in the shared `.index/wiki.db`; `vec_pages` is an optional `vec0` virtual table created only when the extension actually loads.
- **Routing contract (§fallback):** `knn()` routes `vec0`-fast-path → numpy-blob scan → (caller) keyword fallback. The router is **fail-open** — it never issues a `vec0` query on a backend that cannot load the extension (`try_load_sqlite_vec` probes with `enable_load_extension`, never raises), so it never raises `no such module: vec0`. Routing to `vec0` additionally requires the table to be **populated** (`vec0_available` returns False on an empty table — an empty MATCH result is not an exception and would silently lose real neighbors).
- **Byte-identical backends:** the `vec0` path is an exact prefilter + numpy rerank over an over-sized candidate window; both paths select with the same threshold + `(-score, rel_path)` tie-break, so the two backends return identical results including score ties.
- **Degrade, never corrupt:** `semantic_retrieve` returns `None` (caller uses keyword search) when the embedder is absent, no vectors are persisted, or the stored `embed_meta` is incompatible with the embedder's space (LWM_013 invariant #5).
- `sqlite-vec` + `numpy` live in the `[semantic]` optional extra only — never in base dependencies (LWM_013 / ADR-0015).

## Delivered State (defe7e0)

Fully implemented: `vector_schema.py` (probe + additive schema + `embed_meta` guard), `vectorstore.py` (`knn`, `cosine_knn_numpy`, `vec0_available`, `semantic_retrieve`, pure-python cosine when numpy itself is absent), and `embedder.py`/`fusion.py`/`query.py`/`linking.py` all route through it. No remediation batch is outstanding for this ADR.

## Consequences

**Easier:** semantic retrieval works on any platform/build — sqlite-vec is an optimization, never a requirement. Backends agree byte-for-byte, so eval results do not depend on which backend ran. **Harder:** the `vec0` path is only a prefilter+rerank (no HNSW acceleration is used). Keyword fallback remains the guarantee when neither backend is reachable.
