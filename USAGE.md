# llm-wiki-monorepo — Complete User & Developer Overview

## 1. What this actually is

A **knowledge-base operating system for AI agents**. It takes raw source documents (PDFs, articles, code, papers, web pages) and turns them into a **persistent, cross-linked Markdown wiki** that agents build, maintain, query, and audit — with knowledge that *compounds*: every ingest, link, merge, summary, and contradiction check makes the next query smarter.

The genius of the design is the **shared state is just files**. The `wiki/` directory of Markdown pages is the single source of truth — there is **no database** (SQLite is only a regenerable *cache*), no API lock-in, and no single vendor. Any agent (Claude, Codex, Gemini, opencode, a cron job, you) can read and write the same pages, and the git repo itself is the versioned, reviewable, reversible audit trail.

Three surfaces consume the same files:

| Surface | What it is | For |
|---|---|---|
| **`llm-wiki` CLI** (Python) | 27 commands | Humans + scripts + CI |
| **MCP server** (`llm-wiki-mcp`, TypeScript) | 15 tools over stdio | Claude Code, Codex, Cursor, opencode, any MCP client |
| **Hermes skill** (`skill/SKILL.md` + 26 scripts) | In-conversation workflow | Claude/Hermes agent sessions |

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
Same pattern — `.mcp.json` / MCP settings pointing at `npx llm-wiki-mcp --wiki <root>`. The server is plain stdio MCP with 15 tools; `claude mcp list`-style commands work in every client.

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
- The **MCP registration** is now one command: `llm-wiki setup <root> [--title]`
  (v0.6.0 / LWM_035) scaffolds/validates the wiki, registers the MCP server with
  the detected client(s) — claude (`claude mcp add` or `.mcp.json`), codex
  (`~/.codex/config.toml`), opencode (`opencode.json`), hermes (skill symlink) —
  idempotently, with `--dry-run`/`--uninstall` and a health + `tools/list` smoke
  test. `install.sh` still wires the repo; `llm-wiki setup` wires your wiki to
  your clients.
- **Remaining gap:** there is no cross-machine provisioning story (a
  `llm-wiki setup` on a fresh machine after `git clone` still needs Node/npm for
  the TS surfaces and the per-client binaries). The Python-only core works
  everywhere; the MCP/web surfaces need a one-time `install.sh`.

## 4. The full command inventory

**CLI (27 commands):** `scaffold` · `ingest` (2-step CoT, SHA256 cache) · `lint` (15 checks) · `discover` (auto-layout, `--json`) · `insights` (surprising connections + knowledge gaps) · `link-suggest` (lexical + semantic `--apply`, entity-aware) · `entities resolve|list|unmerge` (reversible ER, `--backend splink`) · `derive-edges` (quarantined similarity/co-occurrence, NMI-gated `--include-derived`) · `summarize-communities` (Leiden hierarchy, `--dry-run`, `--levels`) · `backup` (snapshot/restore/verify) · `deep-research` (multi-source pipeline) · `audit` (list/group human feedback) · `benchmark` · `migrate-log` · `ops` · `tuning` (config surface, `--set`, `--emit`) · `index` (FTS5) · `search` (hybrid default, `--keyword`, `--set`) · `embed` · `eval` · `health` · `serve` (local preview: mermaid, KaTeX, feedback) · `claims redteam` (claim-health scoring) · **`setup`** (one-command client wiring, v0.6.0) · **`demo`** (materialize the demo wiki) · **`ask`** (grounded QA over summaries + pages) · **`contradictions`** (detect/apply confidence + conflicts)

**MCP tools (15):** `llm_wiki_status` · `llm_wiki_files` · `llm_wiki_read_file` · `llm_wiki_reviews` · `llm_wiki_search` (hybrid default) · **`llm_wiki_ask`** (grounded QA) · `llm_wiki_graph` · `llm_wiki_graph_build` · `llm_wiki_graph_insights` · `llm_wiki_graph_search` · `llm_wiki_lint` · `llm_wiki_ingest` · `llm_wiki_suggest_links` · `llm_wiki_backup` · `llm_wiki_discover_entities`

## 5. How it replaces/upgrades an existing llm-wiki workflow

If a user already runs a "Karpathy llm-wiki" setup (scaffold + ingest + lint via scripts):
- **Same mental model, richer machine** — the wiki directory layout is compatible (entities/concepts/summaries + raw/ + audit/); `discover` auto-detects their existing layout, so migration is usually *zero-rewrite*: point tools at the old wiki root.
- **What they gain over the common tools**: reversible entity resolution (the "GPT-4 vs GPT 4" collapse), semantic link suggestion with safe `--apply`, hybrid search as the default (BM25+vectors via RRF, eval-certified), Leiden community detection with hierarchy, LLM community summaries as first-class pages, quarantined derived edges (graph discovers connections without polluting analytics), a full tuning surface instead of hardcoded constants, a 15-check lint, backup/restore with integrity verification, a local web preview, grounded **`ask`** answers with citations, contradiction-aware evidence confidence (v0.6.0), one-command client wiring (`llm-wiki setup`), and an MCP layer so Claude/Codex/opencode talk to the wiki natively instead of shelling out.
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
17. **"Ask this wiki" (shipped, LWM_033)**: `llm-wiki ask ~/wikis/redis "what changed in cluster failover between 6.x and 7.x?"` returns a cited answer — the RAG wave turns the wiki into a question-answering system, not a document store.
18. **Epistemic trust layer (shipped, LWM_034)**: `llm-wiki contradictions detect .` flags "maxmemory 4GB" vs "maxmemory 4 GiB" pages before they rot; confidence becomes evidence-derived (`sources` count × recency × cross-page agreement) instead of author intention.
19. **Community-aware onboarding**: `summarize-communities --levels 2` produces a "Redis internals in one page" overview that a new contributor reads first — knowledge compounding made navigable.
20. **Derived-edge discovery as a review tool**: `llm-wiki derive-edges . --include-derived` reveals similarity links between concepts nobody wikilinked; a human reviews the report and promotes the good ones to real links — the graph proposes, the human disposes.

## 7. UX feasibility, ease of use — what's strong, what's weak

> **Status: §7 weaknesses 1–9 shipped in v0.6.0 (2026-08-11).** Items 1–3
> (`setup`, demo wiki, first-run) are closed by LWM_035/036; 4–5 (ask +
> contradictions/confidence) by LWM_033/034; 6 (GLiNER local path) by LWM_037;
> 7 (web-viewer overlay + Sigma.js + exports) by LWM_038; 8 (cross-platform
> hardening) by the `test_cross_platform_edge.py` suite + CI lane; 9 (serve
> friction) by the serve `--build` flag + actionable error. Item 10 remains a
> stated boundary (now documented in `docs/operations/security-and-boundaries.md`).

**Strong**
- **Zero-DB, zero-lock-in**: a wiki is a folder; git is the history; every artifact is inspectable.
- **Deterministic gates everywhere**: baselines, gold sets, reproducibility tests, byte-identical invariants — users get "it either passed or it didn't."
- **Degradation is graceful**: no `[semantic]`? hybrid search falls back to keyword byte-identically. No `[leiden]`? Louvain. No Splink? pure-Python ER. No model download? embed returns nothing, everything still works.
- **Safety rails**: reversible merges, suggest-only derived edges + contradictions, `--dry-run` everywhere, atomic writes, advisory locks, audit trails.
- **One-shot CI**: `install.sh` + the certify gate make the "does it work on my machine" question machine-answerable.

**Remaining / edge**
1. **Cross-machine provisioning is still manual** — `llm-wiki setup` wires a wiki to the local clients, but a fresh `git clone` machine still needs `install.sh` (Node/npm for the TS surfaces) + per-client binaries. A container/devcontainer or a `setup --bootstrap` that also installs the repo is the natural next step.
2. **Optional extras are discoverable but not automatic** — `pip install -e ".[recommended]"` now exists (semantic + leiden + entity-resolution), but users must still opt in; no auto-detection of hardware to suggest the right profile.
3. **GLiNER local path is documented, not end-to-end ONNX** — LWM_037 delivered the torch-free runner + model-cache convention + measured budget, but the one-time ONNX export of the pinned model still requires a torch run (CI `ner-verification` covers the typed-span success path).
4. **web-viewer Sigma view is not unit-rendered** — the WebGL path falls back to SVG on any failure; the layout/graph construction is tested, the GPU render itself is only exercised manually.
5. **Contradiction extraction is lexical-first** — great on numeric/polarity/exclusive-category conflicts; subtle paraphrased contradictions need the opt-in `--assist llm` screening.
6. **No per-wiki auth/visibility story** — multi-user wikis assume shared filesystem trust; there's no permissions layer (by design, files-first — documented as a boundary).

## 8. What I'd improve on the built structure (ranked)

> **Status: all 8 shipped in v0.6.0 (2026-08-11).** 1→`llm-wiki setup` (LWM_035);
> 2→`llm-wiki demo` (LWM_036); 3→`ask` + `contradictions` (LWM_033/034);
> 4→`.[recommended]` + `[ner]` cache/ONNX guidance (LWM_037); 5→web-viewer
> overlay + Sigma.js + JSON Canvas/JSON-LD exports (LWM_038); 6→REVIEW_PROTOCOL
> pass (both PRDs reviewed to approved, evidence committed); 7→standing gold-set
> curation loop (`curate_gold_set.py` + `gate_search_goldset_fresh`); 8→README
> "Five ways to run this".

The next increment is the follow-on list in §7: cross-machine provisioning
(`setup --bootstrap`/devcontainer), auto extras-profiles by hardware, GLiNER
one-time ONNX export wiring, and the multi-hop agentic RAG wave (LWM_033
deferral). **Now delivered (LWM_039 §D):** see README.md → *[Five ways to run this](README.md#five-ways-to-run-this)* for the five surfaces.

---

**Bottom line:** the tool is genuinely ready to be *used* today — `bash install.sh`, `llm-wiki setup ~/wikis/my-project --title "…"`, then point Claude/Codex/opencode at `npx llm-wiki-mcp --wiki <root>`, and the 15 MCP tools + 27 CLI commands give you a reversible, eval-gated, agent-native knowledge base — including grounded `ask` answers and contradiction-aware confidence. Verified: 860 tests, 9/9 certification, green CI on 18 jobs.
