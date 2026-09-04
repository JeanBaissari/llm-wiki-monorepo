---
type: concept
title: "Commercial Licensing Risk"
confidence: high
contested: false
implemented_by:
  - "fred-vix-fetcher"
  - "mig-405b-data-source-hardening"
tags:
  - licensing
  - data-sources
  - risk
related:
  - "decisions/2026-08-17-pulse-data-sources"
  - "mig-405b-data-source-hardening"
created: 2026-08-17
updated: 2026-08-17
---

# Commercial Licensing Risk

## Definition

The legal and operational risk of using data APIs without proper commercial licensing. Yahoo Finance API is undocumented and not licensed for commercial use, creating exposure for any production system relying on it.

## Key Points

- Yahoo Finance API is free for personal use but **not licensed for commercial use**
- Rate limits are undocumented and enforced intermittently
- Commercial use without licensing can result in API access revocation or legal action
- FRED API and Alpha Vantage are explicitly licensed for commercial use

## Affected Fetchers

| Fetcher | Current Risk | Mitigation |
|---------|-------------|------------|
| VIX | HIGH — Yahoo Finance | Migrate to FRED API |
| SPX | HIGH — Yahoo Finance | Migrate to Alpha Vantage (deferred) |
| News | LOW — best-effort source | Retained as-is |
| AUDJPY | N/A — hardcoded | Needs source discovery |
| GDT | N/A — hardcoded | Needs source discovery |
| OU | N/A — hardcoded | Needs source discovery |

## Migration Targets

- **VIX**: FRED API (VIXCLS series) — free, official, no licensing issues
- **SPX**: Alpha Vantage premium — $49.99/mo, requires budget decision
