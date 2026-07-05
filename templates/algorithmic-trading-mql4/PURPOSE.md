# Algorithmic Trading MQL4/5 — Wiki Purpose

> A persistent, cross-linked knowledge base for MQL4/MQL5 algorithmic trading projects.
> Every page documents a strategy, indicator, risk model, or market concept — grounded in
> real EA code, backtest results, and forward-test observations.

## What this wiki is for

- **Entities** — Every EA name, indicator, library, script, tool, and utility named and owned
- **Concepts** — Trading principles: FVG, order blocks, swing detection, regime filters, state machines
- **Architecture** — Module dependency graphs, include file hierarchies, MCP server topologies
- **Decisions (ADRs)** — Why you chose one approach over another, with context and trade-offs
- **Risk models** — Position sizing rules, max drawdown limits, risk governor logic
- **Graphs** — Knowledge graph visualizations (wikilinks, code structure, merged)

## How to use this wiki

1. **For the AI agent (primary consumer):** This is your canonical knowledge store. Before writing
   code or modifying a strategy, search the wiki for existing context. Update pages when you
   discover new relationships or fix misunderstandings.
2. **For the human trader/developer:** Navigate via the index. Use the graph viewer to
   discover connections between strategies, indicators, and market concepts.
3. **For MCP tools:** The wiki is accessible programmatically — query, audit, and update
   from any connected AI interface (Claude Desktop, Cursor, etc.)

## Template structure

```
wiki/
├── entities/       — EAs, indicators, systems (one file per named entity)
├── concepts/       — Trading theory: FVG, swing, regime, state machines
├── architecture/   — Module dependency graphs, include hierarchy, MCP topology
├── decisions/      — Architecture Decision Records (ADRs)
├── graphs/         — Graph engine output: graph-data.json, code-graph.json, reports
├── index.md        — Master index of all pages, grouped by type
├── log.md          — Per-operation change log
├── raw/            — Immutable source documents
│   ├── src/        — MQL4/MQL5/Python source code
│   ├── docs/       — Technical documentation, PDFs, specs
│   └── research/   — Research papers, notes, experiments
└── SCHEMA.md       — This file (placed as CLAUDE.md at scaffold time)
```

## Key extensibility patterns

- Every EA page links to its included modules (`.mqh` files)
- Every concept page links to EAs that implement it
- Every backtest result records exact EA version, symbol, timeframe, and date range
- ADRs capture the decision context first — "why" before "what"
