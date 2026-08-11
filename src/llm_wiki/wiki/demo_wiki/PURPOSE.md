# Redis Internals — Demo Wiki

> Why this wiki exists: a committed, deterministic playground that lets a first-run
> user experience a populated, cross-linked wiki in under a minute — no LLM calls,
> no scaffolding by hand.

This demo wiki explains the internal architecture of Redis: its in-memory data
structures (Simple Dynamic Strings), the single-threaded event loop, embedded Lua
scripting, and persistence. Every page is hand-authored, wikilinked to at least one
sibling, and carries a fixed fixture date so the copy is byte-reproducible.

**What it is for:**

- Trying out `llm-wiki search`, `lint`, `discover`, `summarize-communities` and
  `serve` against real content immediately after installation.
- A template for how a compact topic wiki is structured (entities + concepts +
  summaries, a raw source, a dated log entry).

**What it is NOT for:**

- Real Redis documentation — see the upstream docs for authoritative material.
- A live corpus — it is a fixed snapshot, `--force` re-materializes the pristine copy.
