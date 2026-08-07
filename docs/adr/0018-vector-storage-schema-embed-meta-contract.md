# ADR 0018: Vector Storage Schema + `embed_meta` Contract

- **Status:** accepted
- **Date:** 2026-08-06
- **Context:** LWM_014 (v0.4.0 vector persistence) needed to store page embeddings next to the existing FTS5 index without disturbing the keyword path. The repo's moat is "no DB, files are canonical; keyword search stays byte-identical" — so the schema had to be purely additive, and every vector reader had to be protected from mixing vectors produced by different embedding spaces.

## Decision

Vector storage is **additive tables in the existing `.index/wiki.db`** (`src/llm_wiki/semantic/vector_schema.py`), never a migration of FTS5 data:

- **`page_vectors`** — the always-present fallback store: one row per page (`rel_path`, `sha256`, `dim`, raw little-endian float32 BLOB, `indexed_at`). A pure-numpy KNN works over this with zero native extension (ADR-0016 / LWM_017). Rows carry the page `sha256` so stale vectors are detectable (LWM_016 freshness).
- **`embed_meta`** — the single-row guard: `model_id`, `revision`, `dimension`, `normalization`, `quantization`, `build_id`, `schema_version`. Every vector reader asserts `embed_meta_matches` (which deliberately ignores `build_id`, a rebuild marker) and falls back to keyword on mismatch — a mismatch forces keyword, never a corrupt KNN result (LWM_013 invariant #5).
- **`vec_pages`** — optional `vec0` virtual table, created/populated only when the sqlite-vec extension loads (ADR-0016 routing).
- All schema creation is `CREATE ... IF NOT EXISTS`; the FTS5 tables (`pages` / `index_meta` / `index_stats`) are never touched, so keyword search stays byte-identical by construction (LWM_013 invariant #2). The module is stdlib-only (`sqlite3` + `struct`) and always imports, with or without the `[semantic]` extra.

## Delivered State (defe7e0)

Fully implemented in `vector_schema.py` (schema v1, `store_vector`/`delete_vector`/`iter_vectors`/`get_vectors`, `write_embed_meta`/`read_embed_meta`/`embed_meta_matches`, `open_index_db` with the same WAL pragmas the indexer uses). Consumers: `vectorstore.py`, `query.py` (hybrid), `linking.py`, `derived_edges.py`. No remediation batch is outstanding for this ADR.

## Consequences

**Easier:** embedding persistence is an additive layer — existing wikis need no migration; a schema change is versioned via `VECTOR_SCHEMA_VERSION`. The `embed_meta` guard makes mixed-space corruption structurally impossible. **Harder:** readers must remember to assert `embed_meta` before KNN; the guard's failure mode is silent keyword fallback, which can mask a misconfigured embedder until eval numbers are compared.
