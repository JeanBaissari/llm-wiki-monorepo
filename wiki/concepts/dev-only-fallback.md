---
type: concept
title: "Dev-Only Fallback"
confidence: high
contested: false
implemented_by:
  - "fred-vix-fetcher"
tags:
  - fallback
  - fetcher
  - development
related:
  - "fred-vix-fetcher"
  - "commercial-licensing-risk"
  - "mig-405b-data-source-hardening"
created: 2026-08-17
updated: 2026-08-17
---

# Dev-Only Fallback

## Definition

A degraded data source retained for development/testing purposes when the production source is unavailable. Marked with `# DEV-ONLY` comments and log warnings to prevent accidental production use.

## Yahoo Finance as Dev-Only Fallback

- If `FRED_API_KEY` not set, `FredVIXFetcher` falls back to Yahoo Finance
- Logs warning with "dev-only" tag on each fallback activation
- Code marked with `# DEV-ONLY: Not licensed for commercial use` comment
- **Must never be used in production** — licensing risk

## Purpose

- Enables local development without FRED API key
- Allows testing fetcher logic without external API dependency
- Provides graceful degradation for development environments
