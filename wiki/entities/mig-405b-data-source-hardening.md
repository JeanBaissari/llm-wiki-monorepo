---
type: entity
title: "MIG-405b: External Data Sources — Source Selection & Fetcher Hardening"
language: python
namespace: "tools"
status: active
version: "1.0"
tags:
  - prd
  - phase-4
  - pulse-engine
  - data-sources
  - fetcher
related:
  - "mig-405-news-distribution-service"
  - "mig-400-tcp-zmq-dual-bridge"
  - "mig-305v2-pulseengine"
  - "decisions/2026-08-17-pulse-data-sources"
  - "pluggable-fetcher-architecture"
sources:
  - "mig-405b-external-data-sources-benchmark"
created: 2026-08-17
updated: 2026-08-17
---

# MIG-405b: External Data Sources — Source Selection & Fetcher Hardening

## Overview

PRD for selecting, documenting, and hardening external data sources for all 7 PulseEngine fetchers. Re-scoped from a 24-hour latency benchmark to focused source selection + documentation + error handling.

## Scope

- Replace Yahoo Finance (not licensed for commercial use) with FRED/Alpha Vantage
- Add proper HTTP error handling to all fetchers
- Document blocked stubs (AUDJPY, GDT, OU) with migration paths
- No benchmark script — licensing issues are already well-documented

## LOC Estimate

~400 LOC in fetcher hardening + documentation

## Dependencies

- **Depends on**: MIG-400 (Python bridge infrastructure for FredVIXFetcher HTTP requests)
- **Note**: Originally designed to BLOCK MIG-305v2; MIG-305v2 was implemented first; this PRD now validates and hardens those choices post-hoc

## Phases

### Phase 4.1: Source Documentation — DONE
- Created `DECISION-004-pulse-data-sources.md`
- Per-fetcher: current source, limitations, licensing status, migration target, cost
- RAG status assigned per fetcher (GREEN / YELLOW / RED)

### Phase 4.2: Fetcher Error Handling
- HTTP status checking on VIX and SPX fetchers
- JSON structure validation with distinct error event types
- Exponential backoff: 60s → 120s → 240s
- Structured logging for all live fetchers

### Phase 4.3: Fetcher README + Config Update
- `pulse_fetchers/README.md` with per-fetcher documentation
- `pulse_config.yaml` — no TBD markers, license and status fields added

### Phase 4.4: VIX → FRED Migration
- `FredVIXFetcher` implementation using FRED API
- Yahoo fetcher demoted to `# DEV-ONLY` fallback

### Phase 4.5: Blocked Stub Documentation
- AUDJPY, GDT, OU documented with migration targets (no implementation)

## Acceptance Criteria

- [ ] HTTP error handling + JSON validation on all live fetchers
- [ ] Exponential backoff on repeated fetcher errors
- [ ] FRED API fetcher implemented and working for VIX
- [ ] Yahoo fetcher demoted to `# DEV-ONLY` fallback
- [ ] `pulse_config.yaml` has no `TBD` markers
- [ ] `pulse_fetchers/README.md` exists with per-fetcher documentation
- [ ] Blocked stubs documented with migration targets
- [ ] FAQ updated to reference DECISION-004
