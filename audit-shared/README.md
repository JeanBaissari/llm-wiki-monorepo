# audit-shared

Shared TypeScript library implementing the LLM Wiki **audit file contract** —
schema, text-anchor algorithm, id generator, and YAML serialization. It is the
single source of truth used by the web viewer and the Obsidian plugin, so
feedback filed from either surface is byte-compatible and resolvable by the
`audit` operation.

## Contract

An audit is one markdown file (`YYYYMMDD-HHMMSS-<4hex>[-slug].md`) with YAML
frontmatter and a `# Comment` body:

```yaml
---
id: 20260409-143022-a1b2          # must match the filename prefix
target: wiki/concepts/Example.md  # path relative to the wiki root
target_lines: [45, 52]            # 1-indexed inclusive range (best effort)
anchor_before: "..."              # up to 80 chars before the selection, verbatim
anchor_text: "..."                # exact selected text, verbatim
anchor_after: "..."               # up to 80 chars after the selection, verbatim
severity: warn                    # info | suggest | warn | error
author: me
source: web-viewer                # obsidian-plugin | web-viewer | manual
created: 2026-04-09T14:30:22+08:00
status: open                      # open | resolved
---
```

- `computeAnchor()` captures the anchor window (80 chars of context by default).
- `resolveAnchor()` locates a drifted selection: line range → unique
  `anchor_text` → combined `anchor_before + anchor_text + anchor_after`;
  returns `null` when ambiguous (stale — human must re-anchor).
- `makeId()` / `filenameFor()` generate ids and filenames.
- `toMarkdown()` / `fromMarkdown()` round-trip the file format.

Full format and workflow: [skill/references/audit-guide.md](../skill/references/audit-guide.md).

## Build

Required before the web viewer or Obsidian plugin can bundle this package.

```bash
cd audit-shared
npm install
npm run build      # tsc -b → dist/
```

`bash install.sh` from the repo root builds it in order.

## Usage

```ts
import {
  AuditEntrySchema, toMarkdown, fromMarkdown,
  computeAnchor, resolveAnchor, makeId, filenameFor,
} from "audit-shared";
```

## Test

```bash
npm test          # vitest run
npm run typecheck # tsc --noEmit
```

## Docs

- [Root README](../README.md) — project overview
- [skill/references/audit-guide.md](../skill/references/audit-guide.md) — audit file format and processing workflow
- [web-viewer](../web-viewer) and [plugins/obsidian-audit](../plugins/obsidian-audit) — consumers
- [docs/reference/file-map.md](../docs/reference/file-map.md) — file inventory
