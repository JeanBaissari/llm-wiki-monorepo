---
name: llm-wiki
description: >-
  Build and maintain a Karpathy-style LLM knowledge base — a self-compiling
  Obsidian markdown wiki where an Agent ingests raw sources, compiles
  cross-linked concept/entity/summary pages, answers queries against the
  corpus, lints the graph for health, and audits in-context human feedback
  filed from Obsidian or the local web viewer. Use when (1) scaffolding a
  new knowledge base for any research topic, (2) ingesting
  articles/papers/PDFs/web pages into raw/, (3) compiling or restructuring
  wiki articles from existing raw material, (4) answering questions
  against the wiki and filing durable answers back, (5) running lint
  passes for dead links / orphan pages / coverage gaps / audit shape,
  (6) processing human feedback from the audit/ directory and applying
  corrections. Not for general note-taking, daily journals, or non-wiki
  Obsidian use.
---

# LLM Wiki — Karpathy Knowledge Base Pattern

> **Experimental skill — iterating.**
> Authored by Lewis Liu (lylewis@outlook.com) · Inspired by [Karpathy's llm-wiki Gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

## Core idea

Instead of RAG (re-retrieving raw docs on every query), the LLM **compiles** raw sources into a persistent, cross-linked wiki. Every ingest, query, lint, and audit pass makes the wiki richer. Knowledge compounds — and the human stays in the loop via a structured feedback channel instead of ad-hoc corrections that get lost.

- **You** own: sourcing raw material, asking good questions, steering direction, filing feedback on anything the AI got wrong.
- **LLM** owns: all writing, cross-referencing, filing, bookkeeping, and acting on your feedback.

The wiki is a living artifact with **eight operations** — `compile`, `ingest` (single-pass), `ingest-2step` (two-step chain-of-thought), `query`, `lint`, `audit`, `research` (deep research), `insights` (graph insights). Every session starts by reading `CLAUDE.md`, `PURPOSE.md`, and `wiki/index.md`.

## Directory layout

```
<wiki-root>/
├── PURPOSE.md          ← Project purpose — why this wiki exists, scope, success criteria
├── CLAUDE.md          ← Schema: scope, conventions, current articles, gaps
├── log/               ← Per-day operation log (one file per day)
│   ├── 20260409.md
│   └── 20260410.md
├── audit/             ← Human feedback inbox (one file per comment)
│   ├── 20260409-143022-claude-code-size.md
│   └── resolved/      ← Processed feedback, archived with resolution notes
├── raw/               ← Immutable source documents (LLM reads, never writes)
│   ├── articles/
│   ├── papers/
│   ├── notes/
│   └── refs/          ← Pointer files for large binaries kept outside raw/
├── wiki/              ← LLM-generated knowledge (LLM writes, you read)
│   ├── index.md       ← Master catalog — every page, structured by category
│   ├── concepts/      ← Concept/topic pages (split into subfolders when >1200 words)
│   ├── entities/      ← People, tools, papers, organizations
│   ├── summaries/     ← Per-source summary pages
│   ├── comparisons/   ← Side-by-side comparisons of entities, tools, or concepts
│   └── graphs/        ← Graphify knowledge graph outputs (copied from .graphify/)
└── outputs/
    └── queries/       ← Query answers (promote durable ones to wiki/)
```

`CLAUDE.md` is the **schema file** — the single most important configuration. It tells the LLM the wiki's scope, naming conventions, current article list, open questions, and research gaps. Read `references/schema-guide.md` for what to put in it. Read it at the start of every session.

## Core principles

Five rules govern everything below. If a future instruction contradicts one, flag it to the user before acting.

### 1. Divide and conquer

A single concept page should **never** try to cover a complex topic end-to-end. Target: **400–1200 words per page**. When a topic would blow past that:

- Create a subfolder: `wiki/concepts/<topic>/`
- Put a short index page at `wiki/concepts/<topic>/index.md` — definition, list of sub-pages, one-line summaries
- Put each aspect in its own file: `wiki/concepts/<topic>/<aspect>.md`
- In `wiki/index.md`, show the hierarchy via indented bullets

Example layout (from a real wiki):
```
wiki/tech/claude-code/
├── index.md                         (overview + links to sub-pages)
├── Claude_Code_Architecture.md
├── Claude_Code_Agent_Framework.md
├── Claude_Code_Bridge_System.md
├── Claude_Code_Query_Engine.md
├── Claude_Code_Skills_Plugins.md
├── Claude_Code_State_Management.md
└── Claude_Code_Tool_System.md
```

One fat file covering all seven aspects would be unreadable and unlinkable. Seven focused files + an index page give you navigation, selective reading, clean backlinks, and small audit targets.

### 2. Mermaid for diagrams, KaTeX for formulas

- **Any flow, sequence, hierarchy, or state diagram** must be written in mermaid — never ASCII art. ASCII boxes rot fast and are impossible to annotate.
  ````
  ```mermaid
  flowchart LR
      A[raw/article.md] --> B[summary]
      B --> C[concept page]
      C --> D[index.md]
  ```
  ````
- **Any formula** must be written in KaTeX: inline `$f(x) = \sum_i w_i x_i$` or block `$$...$$`.

Both render in the web viewer (server-side KaTeX, client-side mermaid) and in Obsidian with default settings.

### 3. Raw file policy

Small text-based sources (md, txt, small pdfs, small images) → copy into `raw/<subfolder>/`.

Large binaries (videos, model weights, installers, datasets, large PDFs >10 MB) → **do not copy**. Instead:

- Create a pointer file at `raw/refs/<slug>.md` with:
  ```yaml
  ---
  kind: ref
  external_path: /Volumes/external/models/llama-3-70b/
  size: ~140 GB
  ---
  ```
  followed by a short description of what it is and why it matters to this wiki.
- Wiki pages cite `[[raw/refs/<slug>]]` exactly like any other source.

This keeps the wiki repo git-friendly and portable.

### 4. Audit is the human feedback surface

The wiki is AI-written; it will be wrong sometimes. The raw sources are human-written; they will contradict each other. The `audit/` directory is how humans correct both without losing the corrections in chat history.

- Humans file feedback via the Obsidian plugin or the web viewer. Each feedback is one file in `audit/` with YAML frontmatter (anchor, target, severity) and a markdown body.
- The AI **must** periodically run the `audit` op — never silently ignore `audit/*.md` files.
- When feedback is applied, the file moves to `audit/resolved/` with a `# Resolution` section appended and a log entry recorded in `log/YYYYMMDD.md`.

See `references/audit-guide.md` for the full file format and processing workflow.

### 5. Graphify knowledge graph (optional)

For codebases with documentation, use graphify to build a structural knowledge graph. See `references/graphify-pipeline.md`. The graph lives at `.graphify/` in the repo and its outputs copy to `wiki/graphs/`. The EOW cron refreshes it conditionally (see `references/eow-cron-pipeline.md`). For large codebases (>1M words), fall back to building the graph from wikilinks — see `references/graph-construction-strategies.md`.

---

## The five operations

Every action on the wiki is one of these five. Each appends an entry to the current day's log file (`log/YYYYMMDD.md`).

### 1. `compile`

(Re)structure wiki content from existing `raw/` material — including splitting oversized pages, merging near-duplicates, and rebuilding `index.md`.

**When to run**: after a big ingest batch, when an existing page has outgrown 1200 words, when `index.md` no longer reflects reality, or when the user says "clean up the wiki".

**Steps**:
1. Read `CLAUDE.md`, `wiki/index.md`, and every file in the target subtree.
2. For each page over ~1200 words: plan a split into `concepts/<topic>/` with an index + sub-pages. Confirm the plan with the user before writing.
3. For each pair of near-duplicate pages: propose a merge. Confirm, then rewrite.
4. Regenerate `wiki/index.md` so every page is listed exactly once.
5. Log: `## [HH:MM] compile | <what you did — files touched, splits, merges>`

### 2. `ingest`

Add a new source. **One source typically touches 5–15 wiki pages.**

**Steps**:
1. Save source to the right subfolder:
   - web article → `raw/articles/<slug>.md`
   - paper → `raw/papers/<slug>.md` (extracted text for big PDFs)
   - note → `raw/notes/<slug>.md`
   - large binary → `raw/refs/<slug>.md` pointer file (see raw file policy)
2. Read the source in full.
3. **For URL re-ingests**: compute SHA256 of the raw/ body, compare to stored `sha256:` in frontmatter. Skip if identical; flag drift if changed.
4. **Add raw frontmatter**: every new raw file gets a frontmatter block with `source_url:`, `ingested:` (date), and `sha256:` of the body content.
5. Create `wiki/summaries/<slug>.md` (200–400 words — key takeaways, not a rewrite; see `references/article-guide.md`). Include a provenance marker `^[raw/<subfolder>/<slug>]` at the end of the summary to denote the source.
6. Create or update relevant concept pages in `wiki/concepts/`. Respect divide-and-conquer: if a concept page would exceed 1200 words, split instead of cramming.
7. Create or update entity pages in `wiki/entities/` for any new people / tools / papers / organizations referenced.
8. **Apply page creation thresholds**: only create new pages when an entity/concept appears in **2+ sources** OR is central to one source. Do not create pages for passing mentions.
9. Update `wiki/index.md` so the new pages appear under the right category.
10. Log: `## [HH:MM] ingest | <slug> — <one-line description> (touched N pages)`

### 3. `query`

Answer a question **grounded in the wiki**, not general knowledge.

**Steps**:
1. Read `wiki/index.md`. Scan for relevant pages by category.
2. Read the identified pages in full; follow one level of wikilinks.
3. If the wiki doesn't have enough material, say so and suggest what to ingest next instead of making something up.
4. Synthesize the answer, citing pages inline with `[[Page Name]]`.
5. Save to `outputs/queries/<YYYY-MM-DD>-<question-slug>.md`.
6. If the answer is durable (a comparison, analysis, or new synthesis) → promote a cleaned-up version to `wiki/concepts/`, add to `index.md`.
7. Log: `## [HH:MM] query | <question-slug>` (and a separate `## [HH:MM] promote | ...` line if promoted).

### 4. `lint`

Health check. Run:

```bash
python3 scripts/lint_wiki.py <wiki-root>
```

The script reports:
- **Dead wikilinks** — `[[Target]]` where `Target.md` doesn't exist
- **Orphan pages** — pages with no inbound wikilinks
- **Missing index entries** — pages not listed in `wiki/index.md`
- **Frequently-linked missing pages** — `[[X]]` referenced 3+ times but no page
- **log/ shape** — stray files or wrong filenames in `log/`
- **audit/ shape** — malformed YAML frontmatter in `audit/*.md`
- **Audit target resolution** — every open audit's `target` file must exist
- **Stale pages** — pages not updated in >90 days (check git history or frontmatter `updated:` date)
- **Confidence signals** — pages with `confidence: low` in frontmatter (flagged for review)
- **Contradiction signals** — pages with `contested: true` or `contradictions: [page]` in frontmatter
- **Source drift** — SHA256 mismatches between raw/ files and their stored frontmatter `sha256:`
- **Page size** — pages over 200 lines (candidates for splitting)

For each issue, propose a fix, confirm with the user, then apply. Log: `## [HH:MM] lint | <N> issues found, <M> fixed`.

### 5. `audit`

Process human feedback from `audit/`.

**Steps**:
1. Run `python3 scripts/audit_review.py <wiki-root> --open` to get a grouped list.
2. For each open audit, read the file. Use the `anchor_before` / `anchor_text` / `anchor_after` window to locate the exact range in the target file (line numbers may have drifted).
3. Decide the action:
   - **Accept**: apply the correction to the target file.
   - **Partially accept**: apply what makes sense, note the rest in the resolution.
   - **Reject**: explain why in the resolution — the feedback may be based on a misreading of scope or a contradictory source.
   - **Defer**: add to `CLAUDE.md` "Open research questions" and leave the audit in place with a comment.
4. For applied audits, append a `# Resolution` section to the audit file:
   ```markdown
   # Resolution

   2026-04-10 · accepted.
   Fixed the file count (was "~1,900", corrected to "~1,800" per commit abc123).
   Updated: tech/Claude_Code.md lines 47–48.
   ```
5. Move the file from `audit/` to `audit/resolved/`. Filename unchanged.
6. Log per resolved audit:
   ```
   ## [HH:MM] audit | resolved 20260409-143022-a1b2 — <one-line what>
   ```
7. Never delete audit files. Rejected ones still go to `resolved/` with the rejection rationale in their resolution section — that's valuable history.

See `references/audit-guide.md` for the full audit file format.

### 6. `ingest-2step` (Two-Step Chain-of-Thought Ingest)

Higher-quality ingest using a two-stage LLM pipeline. See `references/ingest-guide.md` for the full prompt architecture.

**When to use:** For complex sources, domain-critical content, or when single-pass ingest produces incomplete pages. Use single-pass `ingest` for simple/well-structured sources.

**Steps:**
1. Read `CLAUDE.md`, `PURPOSE.md`, and `wiki/index.md` for orientation.
2. Save source to appropriate `raw/` subdirectory. Compute SHA256 for drift detection.
3. **Stage 1 — Analysis:** The LLM analyzes the source, extracting:
   - Key entities (people, tools, organizations, concepts)
   - Core claims and findings
   - Relationships between entities
   - Contradictions with existing wiki content
4. **Stage 2 — Generation:** The LLM takes the Stage 1 analysis as context and produces:
   - `---FILE:` blocks for new/updated wiki pages
   - `---REVIEW:` blocks for issues needing human attention (missing pages, duplicates, contradictions)
5. Parse FILE/REVIEW blocks, write/update wiki pages, create review items.
6. Update `wiki/index.md`, append to `log/YYYYMMDD.md`.
7. Report: pages created/updated, reviews generated.

**Script:** `python3 skill/scripts/ingest.py <wiki-root> <source-path>`

### 7. `research` (Deep Research)

Async research task: web search + local wiki search + auto-ingest + synthesis.

**When to use:** When the wiki needs to answer a question that requires external sources, or when building up knowledge on a new topic.

**Steps:**
1. Define the research topic and depth.
2. Web search for sources, collect URLs.
3. Fetch/clip sources into `raw/articles/`.
4. Ingest each source (using single-pass or two-step as appropriate).
5. Synthesize findings across all sources into a synthesis page in `wiki/synthesis/`.
6. Update `wiki/index.md`, append to `log/YYYYMMDD.md`.
7. Report: sources found, pages created, synthesis path.

**Script:** `python3 skill/scripts/deep_research.py <wiki-root> "<topic>" [--depth <n>]`

### 8. `insights` (Graph Insights)

Analyze the wiki's knowledge graph for surprising connections and knowledge gaps.

**When to use:** During lint passes, EOW cron health checks, or on-demand when exploring the wiki's structure.

**Output:**
- **Surprising Connections:** Cross-community edges, peripheral-to-hub links, cross-type connections that might reveal non-obvious relationships.
- **Knowledge Gaps:** Isolated pages (degree ≤ 1), sparse communities (low cohesion), bridge nodes connecting multiple knowledge clusters.

**Script:** `python3 skill/scripts/graph_insights.py <wiki-root> [--connections <n>] [--gaps <n>]`

---

## Tooling

| Tool | Purpose |
|------|---------|
| [Obsidian](https://obsidian.md) | IDE for browsing the wiki; graph view shows connections |
| **`plugins/obsidian-audit/`** | Obsidian plugin — select text → add feedback → writes to `audit/` |
| **`web/`** | Local Node.js server — preview the wiki with mermaid/math rendered; select → feedback → `audit/` |
| `scripts/scaffold.py` | Bootstrap a new wiki directory tree |
| `scripts/ingest.py` | Two-step chain-of-thought ingest (higher quality) |
| `scripts/lint_wiki.py` | Fourteen-pass health check (links, orphans, index, frontmatter, staleness, confidence, contradictions, drift, size, rotation, audit shape, log shape) |
| `scripts/deep_research.py` | Web search + auto-ingest + synthesis for a research topic |
| `scripts/graph_insights.py` | Surprising connections and knowledge gap detection |
| `scripts/audit_review.py` | Group open/resolved audits by target file |
| `scripts/migrate_log.py` | Convert v1 log.md to v2 log/ directory |
| **`mcp-server/`** | Standalone MCP server — 8 tools (status, files, read, reviews, search, graph, lint, ingest) working against any wiki directory |
| [qmd](https://github.com/tobi/qmd) | Optional local semantic search (useful at >100 pages) |
| [Obsidian Headless](https://github.com/obsidian-headless/obsidian-headless) | Server-side Obsidian for headless deployments — render, lint, and sync wikis without a GUI |

The Obsidian plugin and the web viewer both write audit files in the **same format** with **the same anchor algorithm**, so feedback filed from either place can be resolved by either place.

### Obsidian Headless (server deployments)

For wiki deployments on headless servers where a full Obsidian GUI is unavailable:

1. Install [obsidian-headless](https://github.com/obsidian-headless/obsidian-headless) on the server.
2. Configure it to point at the wiki root and serve on a local port.
3. Set up a systemd service to keep it running — see the project docs for a reference unit file.
4. Use the headless instance for continuous sync, automated lint runs triggered by git hooks, and CI/CD integration in the EOW cron pipeline.

This pairs well with the web/ viewer for delivering rendered wiki content without requiring each team member to run Obsidian locally.

---

## Graphify Integration

[Graphify](https://github.com/nousresearch/graphify) builds a structural knowledge graph from codebase documentation. When integrated with the wiki, it enhances discoverability by producing:

- **Entity/relation graphs** — extracted from code symbols, docstrings, and markdown headings
- **Wikilink adjacency** — derived from `[[Page Name]]` references in wiki articles
- **Graph outputs** — JSON adjacency lists, DOT/GraphViz files, and a rendered HTML graph view

### When to use graphify

- **Codebase wikis** — any wiki documenting a software project with source code benefits from AST-level structural extraction
- **Large wikis (>200 pages)** — the graph provides a navigation layer beyond what wikilinks alone offer
- **Multi-repo wikis** — graphify can cross-link entities across repositories

### When to skip graphify

- **Small wikis (<50 pages)** — wikilinks and Obsidian's built-in graph view are sufficient
- **Pure knowledge wikis** — topics without a codebase (history, philosophy, etc.) gain little from AST extraction
- **Very large codebases (>1M words)** — fall back to building the graph from wikilinks only; see `references/graph-construction-strategies.md`

### Pipeline overview

```
raw/ sources ──► ingest ──► wiki/ pages ──► graphify ──► .graphify/ ──► wiki/graphs/
                                                    │
                                              (AST + wikilinks)
```

See `references/graphify-pipeline.md` for the full integration pipeline, including configuration, invocation, and output structure.

---

## EOW Cron Maintenance

A weekly (end-of-week) cron job keeps the wiki healthy and the knowledge graph fresh. This is automated by the Hermes agent's cron system — see `references/eow-cron-pipeline.md`.

### Schedule

- **Frequency**: Weekly, typically Friday 23:00 or Sunday 02:00 (configurable)
- **Scope**: All repos known to have active wikis (tracked in the Hermes profile's cron config)

### Steps performed

1. **Discover** — enumerate repos under management that contain a `CLAUDE.md` + `wiki/` with recent activity
2. **Assess health** — run `lint` to check for drift, stale pages, dead links, and orphan pages
3. **Rebuild graphify graphs** — conditionally:
   - If the wiki has a `.graphify/` config, run graphify in **AST-only mode** (never full semantic — the cron window is bounded; deep semantic passes run ad-hoc)
   - Copy outputs to `wiki/graphs/`
   - For wikis >1M words, use wikilink-only graph construction
4. **Compile health report** — write a summary to `log/` for the week
5. **Alert on failures** — if lint finds >5 new issues or graphify crashes, flag to the user at next session start

### Conditional graph rebuild

The cron always checks whether the wiki's content has changed since the last graph build (diff `raw/` + `wiki/` against the stored `.graphify/.last_build` hash). If unchanged, skip the rebuild entirely to conserve resources.

---

## Comparisons Page Type

The `wiki/comparisons/` directory holds side-by-side comparison pages. Use this when two or more entities, tools, papers, or concepts need direct contrast.

### Format

```markdown
---
title: Tool X vs Tool Y
created: 2026-04-09
updated: 2026-04-09
confidence: medium
contested: false
---

# Tool X vs Tool Y

| Dimension | Tool X | Tool Y |
|-----------|--------|--------|
| Purpose | ... | ... |
| Strengths | ... | ... |
| Weaknesses | ... | ... |
| Licensing | ... | ... |

## Summary

Key differences and recommendation. ^[raw/articles/comparison-source.md]
```

### Conventions

- Filename: `wiki/comparisons/<entity-X>-vs-<entity-Y>.md`
- Every comparison cites its sources with provenance markers (`^[raw/...]`)
- Comparisons are listed in `wiki/index.md` under a `## Comparisons` section
- Comparisons pages have the same frontmatter conventions as other wiki pages (confidence, contested, provenance)

---

## Template System

The monorepo ships with 19 domain-specific project templates. Each template provides a pre-configured `PURPOSE.md`, `SCHEMA.md` (becomes `CLAUDE.md`), and domain-specific page types and directories.

**Available templates:** `research`, `codebase`, `finance`, `algorithmic-trading`, `cybersecurity`, `machine-learning`, `prompt-engineering`, `copywriting`, `marketing`, `design-systems`, `architecture`, `crypto`, `commodities`, `decompilers`, `medicine`, `developer-tools`, `personal-growth`, `reading`, `business`

**Template contents:**
- `PURPOSE.md` — Why this wiki exists, scope, success criteria, key questions
- `SCHEMA.md` → `CLAUDE.md` — Page types, naming conventions, frontmatter rules, domain-specific conventions
- `extra-dirs.json` — Additional directories beyond the base wiki structure
- Optional: `index-format.md` — Custom index.md template

**Using templates:**
```bash
python3 scripts/scaffold.py ~/my-wiki "My Topic" --template codebase
```

Templates live at `templates/<name>/` in the monorepo. Create new templates by copying an existing one and customizing.

---

## Starting a new wiki

```bash
python3 scripts/scaffold.py <wiki-root> "<Topic Title>" [--template <name>]
```

Without `--template`, uses the default `research` template. With `--template`, copies the domain-specific PURPOSE.md and SCHEMA.md (as CLAUDE.md), creates the template's extra directories, and sets up the wiki with domain-appropriate conventions.

After scaffolding:
1. Fill in `CLAUDE.md` — define scope, naming conventions, initial research questions.
2. Start ingesting sources.
3. Ask questions to build up `outputs/queries/`; promote durable answers.
4. Run `lint` periodically.
5. Run `audit` whenever new feedback accumulates.

---

## `wiki/index.md` format

The LLM rebuilds `index.md` on every compile and touches it on every ingest. Format:

```markdown
# Index — <Topic>

> One-sentence scope of the wiki.

## 🔖 Navigation
- [[#Concepts]] · [[#Entities]] · [[#Summaries]] · [[#Comparisons]] · [[#Open Questions]]

## Concepts
### <Category A>
- [[concepts/Foo]] — one-line summary
- [[concepts/Bar/index|Bar]] — (folder-split) one-line summary
    - [[concepts/Bar/aspect-1]] — ...
    - [[concepts/Bar/aspect-2]] — ...

### <Category B>
- ...

## Entities
- [[entities/Andrej Karpathy]] — AI researcher, author of the llm-wiki pattern

## Summaries (chronological)
- 2026-04-09 — [[summaries/llm-wiki-gist]] — Karpathy's original Gist

## Comparisons
- [[comparisons/tool-x-vs-tool-y]] — Tool X vs Tool Y: purpose, strengths, weaknesses

## Open Questions
- Q1: ...
```

Rules:
- Every wiki page must appear exactly once in `index.md`. `lint` enforces this.
- Folder-split concepts show hierarchy via indented bullets.
- `index.md` + `CLAUDE.md` together are what the AI reads at session start.

---

## `log/` format

See `references/log-guide.md` for full details. Minimum:

- One file per day: `log/YYYYMMDD.md`
- H1 = the date; H2 per entry with `## [HH:MM] <op> | <one-line description>`
- Ops: `compile`, `ingest`, `ingest-2step`, `query`, `lint`, `audit`, `research`, `insights`, `promote`, `split`, `scaffold`

Quick grep across history: `grep -rh "^\#\# \[" log/ | tail -20`.

---

## Use cases

- **Research deep-dive** — reading papers/articles on a topic over weeks; the wiki evolves with your understanding, and the audit trail keeps AI mistakes from silently accumulating
- **Personal wiki** — journal entries, notes, ideas compiled into a personal encyclopedia; comment on anything you disagree with later, the AI corrects it
- **Team knowledge base** — fed by Slack threads, meeting notes, docs; team members file corrections through the web viewer
- **Reading companion** — filing each book chapter as you go; builds a rich companion wiki by the end

---

## References

- `references/schema-guide.md` — What to put in `CLAUDE.md`
- `references/article-guide.md` — How to write good wiki articles (length, wikilinks, mermaid, math, divide-and-conquer, provenance markers)
- `references/log-guide.md` — The `log/` folder convention
- `references/audit-guide.md` — Audit file format, anchor strategy, processing workflow
- `references/tooling-tips.md` — Obsidian setup, Web Clipper, qmd, plugin + web installation
- `references/graphify-pipeline.md` — Full graphify + wiki integration pipeline
- `references/graph-construction-strategies.md` — When to use full graphify vs wikilinks-only graph
- `references/eow-cron-pipeline.md` — Weekly automated maintenance pattern
- `references/migration-guide.md` — Migrating v1 wikis to v2 format
- `references/ingest-guide.md` — Two-step chain-of-thought ingest prompt architecture
- `../templates/` — 19 domain-specific project templates with PURPOSE.md + SCHEMA.md
- `../mcp-server/` — Standalone MCP server for programmatic wiki access
- `../graph-engine/` — Knowledge graph engine (relevance model, Louvain communities, insights)
- `../extension/` — Chrome browser extension for web clipping
