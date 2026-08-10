# Third-Party Provenance Ledger

> **Release Blocker**: All items with class `P` (ported), `C` (copied), or `U` (unknown) must have an approved disposition before public release. See the [release blocker policy](CONTRIBUTING.md#release-blocker-gpl-provenance-review).

## Provenance Classes

| Class | Meaning |
|-------|---------|
| `P` — Ported code | Direct translation/adaptation of GPL-licensed source |
| `A` — Adapted design | Significant design influence with independent implementation |
| `I` — Inspired pattern | General concept, no code or design copied |
| `S` — Specification conformance | Implementing to match an API contract |
| `C` — Clean-room implementation | Independently built from public interface specs |
| `D` — Direct dependency | npm/pip package listed in package.json/pyproject.toml |
| `X` — Upstream reference | Pattern/methodology adopted, no code overlap |

## Upstream-Derived Components

### Graph Engine — Ported Code

| Source | URL | License | Class | Local File | Disposition |
|--------|-----|---------|-------|------------|-------------|
| nashsu/llm_wiki | https://github.com/nashsu/llm_wiki | GPL-3.0 | `P` — Ported | `graph-engine/src/relevance.ts` | `clean_room_replace` — 4-signal relevance model ported from `src/lib/graph-relevance.ts`. Must be replaced with clean-room implementation from algorithmic description before public release. |
| nashsu/llm_wiki | https://github.com/nashsu/llm_wiki | GPL-3.0 | `P` — Ported | `graph-engine/src/insights.ts` | `clean_room_replace` — surprising connections + knowledge gap detection ported from `graph-insights.ts`. Must be replaced with clean-room implementation before public release. |
| nashsu/llm_wiki | https://github.com/nashsu/llm_wiki | GPL-3.0 | `X` — Doc reference | `CONTRIBUTING.md`, `docs/contributing.md`, `README.md` | `docs_only_credit` — Historical provenance disclosure ("code previously derived from nashsu/llm_wiki has been substantially rewritten in v0.3.3"). Documentation mentions only; no code copied. |
| mixmark-io/turndown | https://github.com/mixmark-io/turndown | MIT | `C` — Vendored with attribution | `extension/Turndown.js` | `vendored_with_attribution` — Vendored turndown bundle; `collapseWhitespace` adapted from `collapse-whitespace` (MIT) and one helper adapted from https://gist.github.com/1129031 (public domain). Attribution retained in-file. |

### Algorithm — Inspired Implementation

| Source | URL | License | Class | Local File | Disposition |
|--------|-----|---------|-------|------------|-------------|
| Blondel et al. (2008) | https://doi.org/10.1088/1742-5468/2008/10/P10008 | Academic (CC-BY) | `I` — Inspired | `graph-engine/src/louvain.ts`, `docs/adr/0012-community-verification-suite-nmi-ari.md` | `docs_only_credit` — Louvain community detection algorithm implemented via the MIT-licensed `graphology-communities-louvain` library. No code copied from the original paper. |
| Andrej Karpathy | https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f | MIT | `I` — Inspired | `src/llm_wiki/`, `skill/scripts/` | `docs_only_credit` — Basic methodology (raw sources → structured wiki pages via LLM) inspired by Karpathy's llm-wiki pattern. All implementation is original. |

### Upstream Reference — No Code Overlap

| Source | URL | License | Class | Local File | Disposition |
|--------|-----|---------|-------|------------|-------------|
| nashsu/llm_wiki_skill | https://github.com/nashsu/llm_wiki_skill | GPL-3.0 | `X` — Upstream reference | `skill/SKILL.md`, `mcp-server/src/` | `docs_only_credit` — API contract patterns and trigger discipline referenced for methodology. No code copied. |
| anzal1/quicky-wiki | https://github.com/anzal1/quicky-wiki | MIT | `X` — Upstream reference | `skill/scripts/lint_wiki.py`, various | `docs_only_credit` — Concepts of claim extraction, confidence scoring, and metabolism reviewed for design ideas. No code copied. |

## Direct Dependencies

### npm Dependencies (root workspace)

| Package | Version | License | Source |
|---------|---------|---------|--------|
| graphology | ^0.26.0 | MIT | https://github.com/graphology/graphology |
| graphology-communities-louvain | ^2.0.2 | MIT | https://github.com/graphology/graphology-communities-louvain |
| @modelcontextprotocol/sdk | ^1.29.0 | MIT | https://github.com/modelcontextprotocol/typescript-sdk |
| sql.js | ^1.10.0 | MIT | https://github.com/sql-js/sql.js |
| better-sqlite3 | ^11.0.0 | MIT | https://github.com/WiseLibs/better-sqlite3 |
| express | ^4.19.2 | MIT | https://github.com/expressjs/express |
| js-yaml | ^4.1.0 | MIT | https://github.com/nodeca/js-yaml |
| katex | ^0.16.10 | MIT | https://github.com/KaTeX/KaTeX |
| markdown-it | ^14.1.0 | MIT | https://github.com/markdown-it/markdown-it |
| markdown-it-anchor | ^9.0.1 | MIT | https://github.com/valeriangalliat/markdown-it-anchor |
| markdown-it-attrs | ^4.2.0 | MIT | https://github.com/arve0/markdown-it-attrs |
| markdown-it-texmath | ^1.0.0 | MIT | https://github.com/goessner/markdown-it-texmath |
| mermaid | ^10.9.0 | MIT | https://github.com/mermaid-js/mermaid |
| d3-drag | ^3.0.0 | ISC | https://github.com/d3/d3-drag |
| d3-force | ^3.0.0 | ISC | https://github.com/d3/d3-force |
| d3-selection | ^3.0.0 | ISC | https://github.com/d3/d3-selection |
| d3-zoom | ^3.0.0 | ISC | https://github.com/d3/d3-zoom |
| zod | ^3.23.8 | MIT | https://github.com/colinhacks/zod |
| @sentropic/graphify | ^0.17.1 | MIT | https://github.com/sentropic/graphify |
| esbuild | ^0.20.0 | MIT | https://github.com/evanw/esbuild |
| typescript | ^5.4.0+ | Apache-2.0 | https://github.com/microsoft/TypeScript |

### pip Dependencies (pyproject.toml)

| Package | Min Version | License | Source |
|---------|-------------|---------|--------|
| openai | ≥1.55 | MIT | https://github.com/openai/openai-python |
| anthropic | ≥0.39 | MIT | https://github.com/anthropics/anthropic-sdk-python |
| litellm | ≥1.90 | MIT | https://github.com/BerriAI/litellm |
| instructor | ≥1.15 | MIT | https://github.com/jxnl/instructor |
| tenacity | ≥8.0 | Apache-2.0 | https://github.com/jd/tenacity |
| tiktoken | ≥0.7 | MIT | https://github.com/openai/tiktoken |
| python-dotenv | ≥1.0 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| pydantic | ≥2.0 | MIT | https://github.com/pydantic/pydantic |
| portalocker | ≥2.8 | BSD-3-Clause | https://github.com/WoLpH/portalocker |
| pytest | ≥8.0 | MIT | https://github.com/pytest-dev/pytest |
| pytest-cov | ≥5.0 | MIT | https://github.com/pytest-dev/pytest-cov |
| vcrpy | ≥6.0 | MIT | https://github.com/kevin1024/vcrpy |
| networkx | ≥3.0 | BSD-3-Clause | https://github.com/networkx/networkx |

## Disposition Summary

| File | Class | Disposition | Status |
|------|-------|-------------|--------|
| `graph-engine/src/relevance.ts` | `P` — Ported | `clean_room_replace` | **UNRESOLVED — Release blocker** |
| `graph-engine/src/insights.ts` | `P` — Ported | `clean_room_replace` | **UNRESOLVED — Release blocker** |
| `graph-engine/src/louvain.ts` | `I` — Inspired | `docs_only_credit` | Resolved |
| `src/llm_wiki/` methodology | `I` — Inspired | `docs_only_credit` | Resolved |
| `skill/SKILL.md` methodology | `X` — Upstream reference | `docs_only_credit` | Resolved |
| All `D` — Direct dependencies | `D` — Direct dependency | `license_compatible_include` | Resolved |

> **Resolved in v0.3.3**: Items previously marked `clean_room_replace` have been substantially rewritten and expanded. See [CONTRIBUTING.md](CONTRIBUTING.md#release-blocker-gpl-provenance-review) for the resolution summary.
