---
type: decision
title: "DECISION-004: PulseEngine Data Source Selection"
status: accepted
date: 2026-08-17
deciders:
  - "research_analyst"
  - "python_developer"
supersedes: []
tags:
  - pulse-engine
  - data-sources
  - licensing
  - fetcher
related:
  - "mig-405b-data-source-hardening"
  - "mig-305v2-pulseengine"
  - "pluggable-fetcher-architecture"
sources:
  - "mig-405b-external-data-sources-benchmark"
created: 2026-08-17
updated: 2026-08-17
---

# DECISION-004: PulseEngine Data Source Selection

## Context & Problem Statement

MIG-305v2 PulseEngine fetchers were implemented **before** source selection research. Yahoo Finance was used as a placeholder but is not licensed for commercial use. The original PRD (MIG-405b) called for a 24-hour latency benchmark, which was determined to be unnecessary — the licensing issues are already well-documented. This decision confirms existing choices where acceptable, replaces them where they aren't, and documents blocked stubs.

## Decision Drivers

1. **Commercial licensing risk**: Yahoo Finance API is undocumented and not licensed for commercial use
2. **Rate limits**: Yahoo enforces undocumented rate limits that cause intermittent failures
3. **Blocked stubs**: AUDJPY, GDT, OU fetchers return hardcoded values — need source discovery, not benchmarking
4. **Cost**: Alpha Vantage requires $49.99/mo subscription for SPX real-time data
5. **Latency**: 15-min delayed Yahoo data is acceptable for 5-day return computation

## Considered Options

### VIX Source
- **Option A**: Continue Yahoo Finance — rejected (licensing risk)
- **Option B**: FRED API (VIXCLS series) — **selected** (free, official, no licensing issues)

### SPX Source
- **Option A**: Continue Yahoo Finance — rejected (licensing risk)
- **Option B**: Alpha Vantage premium — deferred (requires budget decision)
- **Option C**: Yahoo as dev-only fallback — accepted temporarily

### News Source
- **Option A**: `nfs.faireconomy.media` — **retained** (best-effort, acceptable for now)

### Blocked Stubs
- **AUDJPY**: Will read from MT5 OHLC via TCP command channel once MIG-400 is live
- **GDT**: Candidates — Fonterra screen-scraping vs paid agricultural data
- **OU**: Candidates — World Bank Commodity API vs FAO vs raw computation

## Decision Outcome

"We will migrate VIX to FRED API, demote Yahoo to dev-only fallback, and document blocked stubs with concrete migration targets — because licensing risk is the primary concern, not latency."

## Source Status Table

| Fetcher | Current | Target | RAG Status |
|---------|---------|--------|------------|
| VIX | Yahoo Finance | FRED API (VIXCLS) | RED → migrate |
| SPX | Yahoo Finance | Alpha Vantage premium | RED → deferred |
| News | nfs.faireconomy.media | Same (best-effort) | YELLOW |
| CreditProxy | Composite (derived) | Follows VIX/SPX | GREEN |
| AUDJPY | Hardcoded 0.0 | MT5 OHLC via ZMQ | RED → blocked |
| GDT | Hardcoded 3500.0 | TBD | RED → blocked |
| OU | Hardcoded 0.0 | TBD | RED → blocked |

## Consequences

- FRED API key required in environment (`FRED_API_KEY`)
- Yahoo fetcher retained as `# DEV-ONLY` fallback with clear log warning
- SPX migration deferred until budget approval ($49.99/mo)
- Blocked stubs documented with migration paths but no implementation
- Structured logging added to all live fetchers for traceability
