---
type: concept
title: "RAG Status"
confidence: high
contested: false
implemented_by:
  - "mig-405b-data-source-hardening"
tags:
  - status
  - fetcher
  - risk-assessment
related:
  - "mig-405b-data-source-hardening"
  - "decisions/2026-08-17-pulse-data-sources"
created: 2026-08-17
updated: 2026-08-17
---

# RAG Status

## Definition

Red/Amber/Green status classification for PulseEngine data sources, indicating operational readiness and risk level.

## Status Definitions

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| GREEN | Operational, no issues | None |
| YELLOW | Acceptable but with caveats | Monitor, no immediate action |
| RED | Not acceptable for production | Migration or source discovery required |

## Current Assignments

| Fetcher | Status | Reason |
|---------|--------|--------|
| VIX | RED | Yahoo Finance not licensed for commercial use |
| SPX | RED | Yahoo Finance not licensed for commercial use |
| News | YELLOW | Best-effort source, acceptable for now |
| CreditProxy | GREEN | Composite (derived), no external HTTP |
| AUDJPY | RED | Hardcoded value, needs MT5 OHLC source |
| GDT | RED | Hardcoded value, needs source discovery |
| OU | RED | Hardcoded value, needs source discovery |
