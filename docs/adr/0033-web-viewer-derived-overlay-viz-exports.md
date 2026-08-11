# ADR 0033: Web-Viewer Derived-Edge Overlay + Sigma.js + JSON Canvas/JSON-LD Exports

- **Status:** accepted
- **Date:** 2026-08-11
- **Context:** LWM_038 (v0.6.0, absorbs backlog BKD-006) — the derived layer (LWM_029/ADR-0027) was quarantined in `.index/derived-edges.json` and invisible; its only consumers were the opt-in analytics path. LWM_029's open question asked for a visually distinct, toggleable overlay so users could inspect latent connections without them entering analytics. The ROADMAP also deferred Sigma.js/WebGL viz + JSON Canvas/JSON-LD exports.

## Decision

**Web-viewer-only changes** (`web-viewer/`, invariant 9 — no backend graph output change, overlay off-by-default byte-identical):

- **Derived-edge overlay:** a `GET /api/graph/derived` route reads `.index/derived-edges.json` (resolving page-stem endpoints to `wiki/<relpath>` node ids via `buildGraph`'s byKey aliases, dropping unresolvable endpoints), and a client toggle — **off by default** — renders derived edges dashed/dimmed with `layer:"derived"`. With the toggle off, the canonical graph + rendering are byte-identical to today. The overlay READS the derived layer; it never re-enables derived edges into analytics.
- **Sigma.js/WebGL view:** a zoomable/panable WebGL mode (sigma 3.0.3 + graphology 0.26.0, both MIT; ~166 KB min / ~38 KB gzipped, measured) alongside the d3-force SVG renderer; mermaid + KaTeX untouched; SVG fallback on any WebGL failure.
- **Exports:** JSON Canvas 1.0 + JSON-LD (pinned offline `@context`) of the graph — both layers labeled derived vs canonical, with a layer-separated option; schema-validity tests.

## Delivered State

`web-viewer/server/routes/derived.ts` + `exports.ts` (mounted in `index.ts`), `web-viewer/client/graph.ts` (overlay renderer), `client/main.ts` (toggle + view switch), `client/sigma-view.ts`, `client/styles.css` (derived-edge styling), `web-viewer/test/derived-overlay.test.ts` (8), `exports.test.ts` (6), `sigma-view.test.ts` (5), `routes.test.ts` (9) — 28 tests, tsc clean, esbuild build green; `sigma`/`graphology` in `web-viewer/package.json` + root lockfile.

## Consequences

**Easier:** the quarantined layer becomes inspectable; large graphs render in WebGL; open export formats (JSON Canvas/JSON-LD) unblock tooling. **Harder:** Sigma's GL enum tables are built at module-eval (needs a vitest WebGL shim); the GPU render path is not unit-rendered (falls back to SVG; layout/graph construction is tested); JSON-LD `@context` is pinned to a w3id-style URI — versioning is manual.
