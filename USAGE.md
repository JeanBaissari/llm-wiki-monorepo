# llm-wiki-monorepo — Complete User & Developer Overview

## 1. What this actually is

A **knowledge-base operating system for AI agents**. It takes raw source documents (PDFs, articles, code, papers, web pages) and turns them into a **persistent, cross-linked Markdown wiki** that agents build, maintain, query, and audit — with knowledge that *compounds*: every ingest, link, merge, summary, and contradiction check makes the next query smarter.

The genius of the design is the **shared state is just files**. The `wiki/` directory of Markdown pages is the single source of truth — there is **no database** (SQLite is only a regenerable *cache*), no API lock-in, and no single vendor. Any agent (Claude, Codex, Gemini, opencode, a cron job, you) can read and write the same pages, and the git repo itself is the versioned, reviewable, reversible audit trail.

Three surfaces consume the same files:

| Surface | What it is | For |
|---|---|---|
| **`llm-wiki` CLI** (Python) | 21 commands | Humans + scripts + CI |
| **MCP server** (`llm-wiki-mcp`, TypeScript) | 14 tools over stdio | Claude Code, Codex, Cursor, opencode, any MCP client |
| **Hermes skill** (`skill/SKILL.md` + 23 scripts) | In-conversation workflow | Claude/Hermes agent sessions |

## 2. How it works, exactly

```
raw/  (immutable sources)  ──►  ingest (2-step CoT, SHA256-cached)
                                   │
                                   ▼
wiki/  (pages: entities, concepts, summaries, comparisons, synthesis…)
   │  ▲
   │  │  lint (15 checks) · link-suggest (lexical + semantic) ·
   │  │  entities resolve (reversible canonical↔alias) · derive-edges ·
   │  │  summarize-communities (Leiden hierarchy + LLM summaries)
   ▼  │
graph-data.json  (generated)  ──►  graph-engine (TS) + graph insights
```

- **`discover.py` is the single source of truth for paths** — every tool calls `discover_layout()` at startup, so it auto-detects canonical (`wiki/` subdir), flat, or custom layouts (`content/`, `pages/`, `notes/`).
- **The MCP server spawns a Python sidecar** (`skill/scripts/sidecar.py`) and routes RPCs to it (hybrid search, lint, ingest, link suggestions, backup, entity discovery). The sidecar never leaves the repo — everything is local, private, offline-capable.
- **Reversibility by construction**: entity merges append to a git-diffable `.llm-wiki/entities/aliases.jsonl`; `unmerge` reverses them; `--apply` on links writes only `[[Canonical|surface]]` — prose is never rewritten.
- **Eval-first**: search-hybrid-default, entity resolution, Leiden, and derived edges are all *gated* — committed gold sets + baselines with fail-on-drop tests. The gates are real: they've caught bugs (the grown gold set exposed a metric bug; the two-signal ER guarantee was tested non-vacuously).
- **Byte-identical no-break invariants**: the base install is pure-Python lexical; every heavy dep (model2vec, GLiNER, graspologic, Splink, sqlite-vec) is an optional extra that degrades gracefully.

## 3. How a user installs & wires it

### One command (the whole repo, Linux/macOS/Windows CI-friendly)
```bash
bash install.sh
```
This checks Python ≥3.10, installs the Python package (`pip install -e .`), npm-installs the workspaces (mcp-server, graph-engine, shared-types, web-viewer, audit-shared), builds the TypeScript, and validates the CLI. Then:

```bash
# a) Python package usable anywhere:
pip install -e .          # or uv pip install -e ".[semantic,leiden,ner,entity-resolution]"
llm-wiki --version

# b) MCP server binary (after npm build):
llm-wiki-mcp --wiki ~/wikis/my-project     # run it; stdio protocol
```

### Claude Code
```bash
claude mcp add llm-wiki -- npx llm-wiki-mcp --wiki ~/wikis/my-project
# or project-scoped: create .mcp.json in the repo
# { "mcpServers": { "llm-wiki": { "command": "npx", "args": ["llm-wiki-mcp", "--wiki", "~/wikis/my-project"] } } }
```
The `npx llm-wiki-mcp` bin comes from `mcp-server/package.json` (`"llm-wiki-mcp": "./dist/main.js"` — so `cd mcp-server && npx tsc` first, or rely on `install.sh`).

### Codex / Cursor / VS Code (any MCP client)
Same pattern — `.mcp.json` / MCP settings pointing at `npx llm-wiki-mcp --wiki <root>`. The server is plain stdio MCP with 14 tools; `claude mcp list`-style commands work in every client.

### opencode
Add to `opencode.json`:
```json
{ "mcp": { "llm-wiki": { "type": "local", "command": ["npx", "llm-wiki-mcp", "--wiki", "~/wikis/my-project"], "enabled": true } } }
```

### Hermes (in-conversation skill)
```bash
ln -sf /path/to/llm-wiki-monorepo/skill ~/.hermes/skills/research/llm-wiki
```
The skill's SKILL.md is loaded automatically by the EOW cron job; changes propagate instantly (it's a symlink).

### What "wiring everything with a simple command" means today — and what's missing
- `install.sh` wires the **repo itself** (Python + TS + builds + validation).
- The **MCP registration** is one command per client (`claude mcp add …` / `.mcp.json` / opencode config).
- **Gap:** there is no single `llm-wiki setup` that (1) scaffolds a wiki, (2) registers the MCP server with the detected client (Claude/Codex/opencode), (3) symlinks the Hermes skill, and (4) prints a "hello" smoke test. That's my top UX improvement recommendation (see §8) — everything exists, it just isn't one command yet.

## 4. The full command inventory

**CLI (21 commands):** `scaffold` · `ingest` (2-step CoT, SHA256 cache) · `lint` (15 checks) · `discover` (auto-layout, `--json`) · `insights` (surprising connections + knowledge gaps) · `link-suggest` (lexical + semantic `--apply`, entity-aware) · `entities resolve|list|unmerge` (reversible ER, `--backend splink`) · `derive-edges` (quarantined similarity/co-occurrence, NMI-gated `--include-derived`) · `summarize-communities` (Leiden hierarchy, `--dry-run`, `--levels`) · `backup` (snapshot/restore/verify) · `deep-research` (multi-source pipeline) · `audit` (list/group human feedback) · `benchmark` · `migrate-log` · `ops` · `discover` · `tuning` (config surface, `--set`, `--emit`) · `index` (FTS5) · `search` (hybrid default, `--keyword`, `--set`) · `embed` · `eval` · `health` · `serve` (local preview: mermaid, KaTeX, feedback) · `claims redteam` (claim-health scoring)

**MCP tools (14):** `llm_wiki_status` · `llm_wiki_files` · `llm_wiki_read_file` · `llm_wiki_reviews` · `llm_wiki_search` (hybrid default) · `llm_wiki_graph` · `llm_wiki_graph_build` · `llm_wiki_graph_insights` · `llm_wiki_graph_search` · `llm_wiki_lint` · `llm_wiki_ingest` · `llm_wiki_suggest_links` · `llm_wiki_backup` · `llm_wiki_discover_entities`

## 5. How it replaces/upgrades an existing llm-wiki workflow

If a user already runs a "Karpathy llm-wiki" setup (scaffold + ingest + lint via scripts):
- **Same mental model, richer machine** — the wiki directory layout is compatible (entities/concepts/summaries + raw/ + audit/); `discover` auto-detects their existing layout, so migration is usually *zero-rewrite*: point tools at the old wiki root.
- **What they gain over the common tools**: reversible entity resolution (the "GPT-4 vs GPT 4" collapse), semantic link suggestion with safe `--apply`, hybrid search as the default (BM25+vectors via RRF, eval-certified), Leiden community detection with hierarchy, LLM community summaries as first-class pages, quarantined derived edges (graph discovers connections without polluting analytics), a full tuning surface instead of hardcoded constants, a 15-check lint, backup/restore with integrity verification, a local web preview, and an MCP layer so Claude/Codex/opencode talk to the wiki natively instead of shelling out.
- **Their scripts keep working** — every `skill/scripts/<cmd>.py` is still runnable directly; the CLI is a thin wrapper.

## 6. Twenty quick, realistic, code-based usage examples

### Low-level / single commands
1. **Bootstrap a codebase knowledge wiki in one line**
   ```bash
   llm-wiki scaffold ~/wikis/redis "Redis Internals" --template codebase
   ```
2. **Ingest a paper with the 2-step CoT pipeline (cached)**
   ```bash
   llm-wiki ingest ~/wikis/redis paper.pdf --llm openai --force
   ```
3. **Find the dead links before committing**
   ```bash
   llm-wiki lint ~/wikis/redis   # 15 checks: dead wikilinks, orphans, stale pages…
   ```
4. **Collapse duplicate entities reversibly**
   ```bash
   llm-wiki entities resolve ~/wikis/redis --backend splink --json
   llm-wiki entities unmerge ~/wikis/redis "GCC 13"        # undo one merge
   ```
5. **Search hybrid-first with the escape hatch**
   ```bash
   llm-wiki search ~/wikis/redis "cluster failover"        # hybrid default
   llm-wiki search ~/wikis/redis "cluster failover" --keyword   # lexical-only
   ```
6. **Wire an alias to a canonical page for link suggestions**
   ```bash
   llm-wiki entities resolve ~/wikis/redis
   llm-wiki link-suggest ~/wikis/redis --resolve-entities --semantic --page redis-cluster --apply
   ```
7. **Snapshot before a risky refactor, restore after**
   ```bash
   llm-wiki backup ~/wikis/redis --auto          # snapshot + verify
   llm-wiki backup ~/wikis/redis --restore <id>  # roll back
   ```
8. **Dry-run the cost of community summaries (zero LLM calls)**
   ```bash
   llm-wiki summarize-communities ~/wikis/redis --dry-run --levels 2 --json
   ```
9. **See the graph's own surprising connections**
   ```bash
   llm-wiki insights ~/wikis/redis --format json
   ```
10. **Tune retrieval without touching code**
    ```bash
    llm-wiki search ~/wikis/redis "aof rewrite" --set retrieval.simFloor=0.45
    llm-wiki tuning ~/wikis/redis --emit > /tmp/profile.json   # share the profile
    ```

### Mid-level / composition
11. **Full "new article → wiki" pipeline as one shell chain**
    ```bash
    llm-wiki ingest ~/wikis/redis article.md && llm-wiki lint ~/wikis/redis \
      && llm-wiki entities resolve ~/wikis/redis \
      && llm-wiki link-suggest ~/wikis/redis --resolve-entities --apply \
      && llm-wiki derive-edges ~/wikis/redis
    ```
12. **Wire a cron knowledge sweep (agent-native, $0.00)**
    ```bash
    0 3 * * * cd ~/wikis/redis && llm-wiki ingest raw/ --provider opencode \
      && llm-wiki summarize-communities . --levels 2 --force --provider opencode
    ```
13. **CI gate that fails on wiki decay**
    ```bash
    llm-wiki lint . && llm-wiki health . && llm-wiki eval . --split gate
    ```
14. **Serve the wiki locally with feedback forms**
    ```bash
    llm-wiki serve ~/wikis/redis   # mermaid + KaTeX rendering, audit feedback
    ```
15. **MCP-driven session**: ask Claude to "read the wiki's stance on Lua scripting" — it calls `llm_wiki_search`, then `llm_wiki_read_file`, then `llm_wiki_graph_insights` — all through the MCP tools, no shell.

### High-level / creative
16. **Multi-agent research team on one wiki**: three agents ingest different sources into the same `raw/`; the wiki lock (`portalocker` advisory locks) prevents write races; each agent's work lands as git-diffable pages; a fourth agent runs `llm-wiki audit` to adjudicate contradictions humans filed from Obsidian.
17. **"Ask this wiki" (v0.6.0 draft LWM_033)**: after summaries exist, `llm-wiki ask ~/wikis/redis "what changed in cluster failover between 6.x and 7.x?"` returns a cited answer — the RAG wave turns the wiki into a question-answering system, not a document store.
18. **Epistemic trust layer (LWM_034 draft)**: `llm-wiki contradictions detect .` flags "maxmemory 4GB" vs "maxmemory 4 GiB" pages before they rot; confidence becomes evidence-derived (`sources` count × recency × cross-page agreement) instead of author intention.
19. **Community-aware onboarding**: `summarize-communities --levels 2` produces a "Redis internals in one page" overview that a new contributor reads first — knowledge compounding made navigable.
20. **Derived-edge discovery as a review tool**: `llm-wiki derive-edges . --include-derived` reveals similarity links between concepts nobody wikilinked; a human reviews the report and promotes the good ones to real links — the graph proposes, the human disposes.

## 7. UX feasibility, ease of use — what's strong, what's weak

**Strong**
- **Zero-DB, zero-lock-in**: a wiki is a folder; git is the history; every artifact is inspectable.
- **Deterministic gates everywhere**: baselines, gold sets, reproducibility tests, byte-identical invariants — users get "it either passed or it didn't."
- **Degradation is graceful**: no `[semantic]`? hybrid search falls back to keyword byte-identically. No `[leiden]`? Louvain. No Splink? pure-Python ER. No model download? embed returns nothing, everything still works.
- **Safety rails**: reversible merges, suggest-only derived edges, `--dry-run` everywhere, atomic writes, advisory locks, audit trails.
- **One-shot CI**: `install.sh` + the certify gate make the "does it work on my machine" question machine-answerable.

**Weak / open gaps**
1. **No one-command client wiring** — the biggest UX gap. `claude mcp add …`, `.mcp.json`, opencode config, and the Hermes symlink are four separate manual steps. A `llm-wiki setup [--client claude|codex|opencode|hermes]` that detects and writes the config (and prints the smoke test) would collapse installation to one command.
2. **Optional extras are manual** — `[semantic]`/`[leiden]`/`[ner]`/`[entity-resolution]` are powerful but users must know to install them; there's no "recommended profile" (`pip install -e ".[recommended]"` or a setup prompt).
3. **First-run discoverability** — `llm-wiki --help` lists commands but there's no `llm-wiki demo`/`--example` that scaffolds a tiny wiki with pre-ingested content to play with in 60 seconds.
4. **RAG is drafted, not shipped** (LWM_033) — the wiki answers questions only through search today; the ask surface is the natural next increment.
5. **Confidence fields are inert** (LWM_034) — `confidence`/`contested`/`contradictions` exist in the schema but nothing computes them.
6. **GLiNER local path** (BKD-007) — the typed-span success path is CI-enforced only; the torch+CUDA weight of `[ner]` makes local installs painful on small disks.
7. **web-viewer is functional but unpolished** — no derived-edge overlay (BKD-006), no sigma.js graph view; the preview is "good enough" not "delightful."
8. **Windows/macOS hardening is recent** — all CI lanes are green now, but macOS/Linux symlink path handling and Windows cp1252/CRLF issues were only fixed in the last two days; edge cases in the wild may still surface.
9. **`serve` requires a built mcp-server dist** — first-run friction if a user only installed the Python side.
10. **No per-wiki auth/visibility story** — multi-user wikis assume shared filesystem trust; there's no permissions layer (by design, files-first — but worth stating as a boundary).

## 8. What I'd improve on the built structure (ranked)

1. **`llm-wiki setup`** — scaffold + client registration + skill symlink + optional extras profile + smoke test, one command. Highest leverage.
2. **`--example` / demo wiki** — a committed 5-minute playground (ingest → resolve → summarize → ask) for first-run.
3. **Ship LWM_033 (ask) then LWM_034 (contradictions)** — the two drafted v0.6.0 PRDs are the natural next minor; they complete the "epistemic" loop.
4. **Recommended-extras profile** + model caching guidance for `[ner]` (smaller ONNX/INT8 paths).
5. **BKD-006 web-viewer derived overlay + Sigma.js** — makes the quarantined layer visible.
6. **PRD review protocol pass** for LWM_033/034 (REVIEW_PROTOCOL checklists, Evidence Matrices already drafted).
7. **Search gold-set standing procedure** — per-minor curation loop (the BKD-002 open question), so the gate keeps growing.
8. **A landing README section "5 ways to run this"** (CLI / MCP / skill / cron / web) — currently the README is thorough but not onboarding-shaped.

---

**Bottom line:** the tool is genuinely ready to be *used* today — `bash install.sh`, scaffold a wiki, point Claude/Codex/opencode at `npx llm-wiki-mcp --wiki <root>`, and the 14 MCP tools + 21 CLI commands give you a reversible, eval-gated, agent-native knowledge base. The weak points are all *onboarding and surface* (one-command wiring, demo wiki, RAG/ask, viz) — the core loop (ingest → link → resolve → summarize → lint → gate) is complete, tested (725 tests, 8/8 certification, green CI on 17 jobs), and honest.
