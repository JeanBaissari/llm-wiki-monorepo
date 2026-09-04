---
type: concept
title: "Source Selection"
confidence: high
contested: false
implemented_by:
  - "mig-405b-data-source-hardening"
  - "decisions/2026-08-17-pulse-data-sources"
tags:
  - data-sources
  - api
  - selection
related:
  - "commercial-licensing-risk"
  - "blocked-stubs"
  - "decisions/2026-08-17-pulse-data-sources"
created: 2026-08-17
updated: 2026-08-17
---

# Source Selection

## Definition

The process of choosing external data APIs for PulseEngine fetchers based on licensing, cost, reliability, and data quality requirements.

## Selection Criteria

1. **Commercial licensing**: Must be explicitly licensed for commercial use
2. **Cost**: Free preferred; paid requires budget approval
3. **Reliability**: Uptime, rate limits, documented API
4. **Data quality**: Accuracy, latency, historical coverage
5. **Integration effort**: API complexity, authentication requirements

## Selected Sources

| Data | Selected Source | Rationale |
|------|----------------|-----------|
| VIX | FRED API (VIXCLS) | Free, official, commercial-use licensed |
| SPX | Alpha Vantage (deferred) | Requires $49.99/mo subscription |
| News | nfs.faireconomy.media | Best-effort, acceptable for now |

## Deferred Sources

| Data | Candidate | Blocker |
|------|-----------|---------|
| SPX | Alpha Vantage premium | Budget decision needed |
| AUDJPY | MT5 OHLC via ZMQ | MIG-400 dependency |
| GDT | Fonterra/paid agricultural | Source discovery needed |
| OU | World Bank/FAO/raw computation | Source discovery needed |
