---
type: concept
title: "Fetcher Error Handling"
confidence: high
contested: false
implemented_by:
  - "mig-405b-data-source-hardening"
  - "fred-vix-fetcher"
tags:
  - fetcher
  - error-handling
  - resilience
related:
  - "exponential-backoff"
  - "structured-logging"
  - "mig-405b-data-source-hardening"
created: 2026-08-17
updated: 2026-08-17
---

# Fetcher Error Handling

## Definition

HTTP-level error handling for PulseEngine data fetchers, ensuring graceful degradation on API failures rather than crashes.

## Implementation Pattern

1. **HTTP status checking**: Verify `response.status == 200` before JSON parsing
2. **JSON structure validation**: `try/except KeyError` around expected data paths
3. **Graceful degradation**: Return empty frame list (not crash) on errors
4. **Structured logging**: Distinct event types for different failure modes
5. **Exponential backoff**: Progressive delay on repeated errors

## Error Event Types

| Event Type | Description | Trigger |
|------------|-------------|---------|
| `rate_limited` | API rate limit exceeded | HTTP 429 |
| `parse_error` | JSON structure unexpected | KeyError in data path |
| `timeout` | API response timeout | Connection/read timeout |
| `source_unavailable` | API down or unreachable | HTTP 500/503 |

## Backoff Strategy

- Initial: 60 seconds
- Second failure: 120 seconds
- Third failure: 240 seconds
- Doubles on each subsequent failure

## Distinction: yahoo_parse_error vs yahoo_api_error

- `yahoo_parse_error`: JSON received but structure doesn't match expected format
- `yahoo_api_error`: HTTP-level error (non-200 status)
