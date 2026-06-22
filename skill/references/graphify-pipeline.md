# Graphify Pipeline Integration

When the wiki lives inside a development repo (in-repo `wiki/`), the
graphify knowledge graph tool (`@sentropic/graphify`) adds a structural
layer between raw sources and compiled synthesis. This is the pipeline
defined in the TYRELL_WELLICK SOUL.

## Pipeline Overview

```
1. Raw sources     → wiki/raw/        (immutable — articles, papers, transcripts)
2. Graphify        → wiki/graphs/     (knowledge graph from .graphify/)
3. LLM compilation → wiki/compiled/   (cross-referenced synthesized insights)
4. EOW cron refresh                   (re-run graphify + recompile against current codebase)
```

## Directory Layout

```
repo/
├── wiki/
│   ├── raw/           ← standard llm-wiki raw sources
│   ├── graphs/        ← graphify outputs (graph.json, GRAPH_REPORT.md, graph.html)
│   ├── compiled/      ← LLM-synthesized pages from graph + sources
│   ├── entities/
│   ├── concepts/
│   ├── comparisons/
│   └── queries/
├── .graphify/         ← graphify working directory (AST, detection, extraction)
│   ├── graph.json
│   ├── GRAPH_REPORT.md
│   └── graph.html
```

## Graphify Extraction: Two-Phase

Graphify runs in two phases:

1. **AST extraction** (no LLM) — processes code files (.py, .ts, .js, etc.) into structural
   nodes and edges. Fast, deterministic, no token cost. Produces `.graphify/.graphify_ast.json`.

2. **Semantic extraction** (requires LLM) — processes docs, papers, markdown files into
   concept nodes with EXTRACTED/INFERRED/AMBIGUOUS confidence tags. Requires the graphify
   skill's agent pipeline or `--semantic` flag.

Running bare `graphify .` only does AST. It exits with:
> "detected non-code corpus files that require semantic extraction"

To complete the full pipeline, the agent must follow the graphify skill's Step 1-9 procedure
(extraction → clustering → community labeling → HTML/report generation).

## Initial Ingest Workflow

For a newly wiki'd repo, follow this order:

1. **Run graphify** on the repo directory (via the graphify skill's full pipeline).
   This builds the structural graph from code + documents.

2. **Copy graphify outputs** to `wiki/graphs/`:
   ```bash
   cp .graphify/graph.json wiki/graphs/
   cp .graphify/GRAPH_REPORT.md wiki/graphs/
   cp .graphify/graph.html wiki/graphs/   # interactive viz
   ```

3. **Ingest repo documentation** as raw sources into `wiki/raw/articles/` —
   save CLAUDE.md, README.md, PRD.md, and any design docs as raw source files.

4. **Run standard wiki ingest** (per llm-wiki skill) on the saved raw sources,
   using the graph to guide cross-references and entity extraction.

5. **Create compiled synthesis pages** in `wiki/compiled/` — these pull from both
   the graph (structural relationships) and raw sources (factual claims), with
   provenance markers and confidence levels.

## EOW Refresh (Cron Job)

Schedule a Friday 16:00 cron job that:
1. Runs `graphify --update` on the repo
2. Copies updated graph outputs to `wiki/graphs/`
3. Runs `wiki lint` to find stale/contradictory pages
4. Appends findings to `wiki/log.md`

The cron job should load both `llm-wiki` and `graphify` skills.
