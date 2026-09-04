---
type: concept
title: "Blocked Stubs"
confidence: high
contested: false
implemented_by:
  - "mig-405b-data-source-hardening"
tags:
  - fetcher
  - stub
  - blocked
  - pulse-engine
related:
  - "mig-405b-data-source-hardening"
  - "pluggable-fetcher-architecture"
  - "decisions/2026-08-17-pulse-data-sources"
created: 2026-08-17
updated: 2026-08-17
---

# Blocked Stubs

## Definition

PulseEngine fetchers that return hardcoded values because no suitable external data source has been identified or implemented. These are placeholders awaiting source discovery.

## Current Blocked Stubs

| Fetcher | Hardcoded Value | Target Source | Status |
|---------|----------------|---------------|--------|
| AUDJPY | 0.0 | MT5 OHLC via TCP (MIG-400) | Blocked — needs MIG-400 |
| GDT | 3500.0 | Fonterra screen-scraping or paid agricultural data | Blocked — needs source discovery |
| OU | 0.0 | World Bank Commodity API, FAO, or raw computation | Blocked — needs source discovery |

## Why Blocked

- **AUDJPY**: Requires live MT5 OHLC data, which depends on MIG-400 TCP/ZMQ bridge
- **GDT**: Global Dairy Trade price data — no free API available; candidates require evaluation
- **OU**: Ornstein-Uhlenbeck mean reversion parameter — can be computed from historical data but needs source selection

## Migration Path

Each stub has documented source candidates but no implementation until:
1. Source availability confirmed
2. Licensing verified
3. MIG-400 infrastructure available (for AUDJPY)
