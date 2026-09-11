# extension

Chrome (Manifest V3) web clipper for LLM Wiki. It converts the current page to
clean Markdown — using vendored [Readability.js](https://github.com/mozilla/readability)
and [Turndown](https://github.com/mixmark-io/turndown) — and **downloads** it
for placement in the wiki's `raw/` directory. There is no auto-ingest and no
network call: clipping is local and the file lands in your browser's downloads
folder.

## Install (load unpacked)

1. Open `chrome://extensions`.
2. Enable **Developer mode** (top right).
3. Click **Load unpacked** and select this `extension/` directory.
4. Pin the extension, then open it on any article page.

No build step and no package manager — the extension is plain JS
(`manifest.json`, `popup.html`, `popup.js`, plus the vendored libraries).

## Clip → download flow

1. In the popup, enter the wiki path (stored locally for reference) and choose a
   target folder (`raw/articles/`, `raw/papers/`, or `raw/notes/`).
2. Click **Clip Current Page**. The page is extracted and converted to Markdown
   with frontmatter (`source_url`, `ingested`, `source_type: article`).
3. Chrome downloads it to `Downloads/wiki-imports/<folder>/<title-slug>.md`.
4. Move the file into your wiki's matching `raw/` folder, then ingest it with
   `llm-wiki ingest <wiki-root> raw/articles/<title-slug>.md` (or the two-step
   `skill/scripts/ingest.py`).

The auto-ingest feature present in earlier versions was removed; the extension
never writes into the wiki directly.

## Test

None — no package manifest or test suite. Verify manually by loading unpacked
and clipping a page.

## Docs

- [Root README](../README.md) — project overview
- [skill/references/tooling-tips.md](../skill/references/tooling-tips.md) — Web Clipper setup and workflow
- [docs/reference/file-map.md](../docs/reference/file-map.md) — file inventory
- [AGENTS.md](../AGENTS.md) — repository conventions
