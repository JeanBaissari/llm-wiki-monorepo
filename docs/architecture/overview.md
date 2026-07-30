# LLM Wiki Monorepo — Purpose

## What this system is

A complete, portable knowledge base operating system. It takes the Karpathy LLM Wiki pattern and wraps it in production-grade infrastructure: agent skills, MCP server, knowledge graph engine, domain-specific templates, browser clipping, human feedback loops, and automated maintenance.

## Why it exists

AI-written knowledge bases are powerful but fragile. Without structure, they drift. Without feedback loops, errors compound. Without graph analysis, connections stay hidden. Without templates, every wiki starts from zero.

This system solves all four problems in a single, installable package.

## Core principles

1. **Wiki directory is the shared state.** Every component reads/writes the same markdown files. No database. No API lock-in. Just files.
2. **Agent writes, human steers.** The AI does all the grunt work — summarizing, cross-referencing, filing, bookkeeping. The human curates sources, asks questions, files feedback.
3. **Knowledge compounds.** Every ingest, query, lint, and audit pass makes the wiki richer. Cross-references accumulate. Contradictions get flagged. The graph gets denser.
4. **Domain-specific from day one.** Templates pre-configure the wiki for the domain — page types, naming conventions, frontmatter rules, research questions.
5. **Portable and standalone.** One `git clone`. Works with any AI agent (Hermes, Claude Code, Codex), any MCP-compatible client, any machine.

## What it replaces

- Scattered markdown notes with no structure
- RAG systems that re-derive knowledge on every query
- Manual cross-referencing and index maintenance
- Ad-hoc feedback ("you were wrong about X" lost in chat history)
- Wiki drift where stale pages outnumber fresh ones

## Success criteria

- [ ] Any agent can scaffold a domain-specific wiki in one command
- [ ] Two-step ingest produces higher-quality wiki pages than single-pass
- [ ] Knowledge graph surfaces connections a human would miss
- [ ] Review system catches AI errors before they become accepted facts
- [ ] EOW cron keeps wikis healthy without human intervention
- [ ] MCP server enables headless/automated wiki operations
- [ ] Templates cover 19 domains relevant to Baissari Enterprises' work
