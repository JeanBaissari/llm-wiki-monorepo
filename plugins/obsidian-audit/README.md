# obsidian-audit (LLM Wiki Audit)

Obsidian plugin for filing anchored audit feedback. Select text in any wiki
page, leave a comment, and the plugin writes an audit file to `audit/` — the
same schema and anchor algorithm used by the web viewer and consumed by the
LLM Wiki `audit` operation.

## Build

```bash
cd audit-shared && npm install && npm run build   # dependency (bundled)
cd ../plugins/obsidian-audit
npm install
npm run build        # production bundle → main.js
npm run dev          # esbuild watch mode
```

`bash install.sh` from the repo root builds `audit-shared` first, then this
package.

## Install into a vault

Symlink the plugin folder into the vault (recommended, supports hot reload):

```bash
npm run link -- "/path/to/your/vault"
# symlinks this folder to <vault>/.obsidian/plugins/llm-wiki-audit/
```

Then enable **LLM Wiki Audit** in Obsidian → Settings → Community plugins.

To install manually instead, copy `main.js`, `manifest.json`, and `styles.css`
into `<vault>/.obsidian/plugins/llm-wiki-audit/`.

## Usage

Configure in the plugin settings: **Wiki root** (relative to the vault, usually
`.`), **Audit directory** (default `audit`), and **Author**.

Commands (bindable to hotkeys):

- **Audit: Add feedback on selection** — severity + comment modal → writes an
  audit file.
- **Audit: List open feedback for current file** — notice summarising open
  audits targeting the current page.
- **Audit: Open audit folder** — reveal `audit/` in the file explorer.

Process the queued feedback with `llm-wiki audit <wiki-root> --open` and the
`audit` operation described in [skill/SKILL.md](../../skill/SKILL.md).

## Test

```bash
npm test          # vitest run
npm run typecheck # tsc --noEmit
```

## Docs

- [Root README](../../README.md) — project overview
- [skill/references/audit-guide.md](../../skill/references/audit-guide.md) — audit file format and workflow
- [audit-shared](../../audit-shared) — schema/anchor library this plugin bundles
- [docs/reference/file-map.md](../../docs/reference/file-map.md) — file inventory
