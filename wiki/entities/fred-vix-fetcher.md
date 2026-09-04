---
type: entity
title: "FredVIXFetcher"
language: python
namespace: "tools"
status: experimental
version: "0.1"
tags:
  - fetcher
  - pulse-engine
  - fred-api
  - vix
related:
  - "mig-405b-data-source-hardening"
  - "pluggable-fetcher-architecture"
  - "commercial-licensing-risk"
  - "decisions/2026-08-17-pulse-data-sources"
sources:
  - "mig-405b-external-data-sources-benchmark"
created: 2026-08-17
updated: 2026-08-17
---

# FredVIXFetcher

## Overview

VIX data fetcher using the FRED API (Federal Reserve Economic Data). Replaces Yahoo Finance fetcher for VIX data due to commercial licensing restrictions.

## Implementation Details

- **Source**: FRED API series `VIXCLS` (CBOE Volatility Index)
- **Authentication**: API key from `os.environ["FRED_API_KEY"]`
- **Processing**: Fetches VIXCLS series, computes rolling 50-period mean/std
- **Output format**: Same `PulseFrame` format as Yahoo fetcher (backward compatible)
- **Fallback**: If `FRED_API_KEY` not set, logs warning and falls back to Yahoo with "dev-only" tag

## Error Handling

- HTTP status checking before JSON parsing
- Returns empty frame list (not crash) on non-200
- Structured error logging with status code
- Exponential backoff: 60s → 120s → 240s on repeated errors

## Dependencies

- FRED API key (environment variable)
- Python `requests` library (via MIG-400 bridge infrastructure)
