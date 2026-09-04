---
type: concept
title: "Structured Logging"
confidence: high
contested: false
implemented_by:
  - "mig-405b-data-source-hardening"
tags:
  - logging
  - observability
  - fetcher
related:
  - "fetcher-error-handling"
  - "mig-405b-data-source-hardening"
created: 2026-08-17
updated: 2026-08-17
---

# Structured Logging

## Definition

JSON-formatted log output with consistent event types and fields, enabling programmatic log analysis and alerting for PulseEngine fetcher failures.

## Event Types

| Event Type | Description |
|------------|-------------|
| `rate_limited` | API rate limit exceeded (HTTP 429) |
| `parse_error` | JSON structure doesn't match expected format |
| `timeout` | API response timeout |
| `source_unavailable` | API down or unreachable (HTTP 500/503) |

## Design Decision

- **Per-fetcher logger** (not shared) for traceability
- Each fetcher instance gets its own named logger
- Enables filtering logs by specific data source
