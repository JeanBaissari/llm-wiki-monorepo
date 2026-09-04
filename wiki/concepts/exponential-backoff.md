---
type: concept
title: "Exponential Backoff"
confidence: high
contested: false
implemented_by:
  - "mig-405b-data-source-hardening"
  - "fred-vix-fetcher"
tags:
  - resilience
  - retry
  - fetcher
related:
  - "fetcher-error-handling"
  - "mig-405b-data-source-hardening"
created: 2026-08-17
updated: 2026-08-17
---

# Exponential Backoff

## Definition

A retry strategy where the delay between attempts doubles after each failure, preventing thundering herd problems and giving rate-limited APIs time to recover.

## Parameters (PulseEngine Fetchers)

- **Initial delay**: 60 seconds
- **Second attempt**: 120 seconds
- **Third attempt**: 240 seconds
- **Doubling**: Continues on each subsequent failure

## Rationale

- Prevents hammering a rate-limited or temporarily unavailable API
- Gives the API time to recover from rate limiting
- Reduces load on external services during outages
- Standard pattern for HTTP client resilience
