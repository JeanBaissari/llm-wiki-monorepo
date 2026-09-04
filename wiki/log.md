---
title: Wiki Change Log
type: log
created: 2026-08-17
updated: 2026-08-17
ingest_count: 4
---

# Change Log

## 2026-08-17 — Ingest: License Taxonomy and Rights Matrix (PS_003/BPS_011)

**Source:** `license-taxonomy`
**Operation:** Full source + concept extraction

### Pages Created

**Sources (1):**
- `sources/license-taxonomy.md` — PS_003/BPS_011 governing license classification and rights evaluation

**Concepts (10):**
- `concepts/license-taxonomy.md` — Classification system for source licenses
- `concepts/rights-axes.md` — 5 independent rights evaluation dimensions
- `concepts/distribution-channels.md` — 7 distribution channels with V1 record status
- `concepts/fidelity-tiers.md` — 6 tiers (T0–TX) orthogonal to rights
- `concepts/fail-closed-licensing.md` — Default-deny rules for unknowns
- `concepts/license-classes.md` — v2 five studio license classes
- `concepts/cc-family-handling.md` — CC-family NC restrictions and conflict rules
- `concepts/mpl-reauthoring-rules.md` — MPL-2.0 derivative requirements
- `concepts/product-channel-rights.md` — Product channels never broaden source rights
- `concepts/permission-evidence.md` — Required evidence fields for license claims

**Index:** `index.md` — Updated with all new pages

## 2026-08-17 — Ingest: MIG-405b PRD (External Data Sources)

**Source:** `mig-405b-external-data-sources-benchmark`
**Operation:** Full entity + concept + decision extraction

### Pages Created

**Entities (2):**
- `entities/mig-405b-data-source-hardening.md` — MIG-405b PRD overview
- `entities/fred-vix-fetcher.md` — FRED API VIX fetcher

**Concepts (8):**
- `concepts/commercial-licensing-risk.md` — Yahoo Finance licensing restrictions
- `concepts/fetcher-error-handling.md` — HTTP status checking, JSON validation, graceful degradation
- `concepts/exponential-backoff.md` — 60s→120s→240s retry strategy
- `concepts/structured-logging-fetcher.md` — JSON event types for fetcher failures
- `concepts/blocked-stubs.md` — AUDJPY, GDT, OU hardcoded placeholders
- `concepts/rag-status.md` — Red/Amber/Green source readiness classification
- `concepts/source-selection.md` — API selection criteria and current choices
- `concepts/dev-only-fallback.md` — Yahoo Finance retained for development

**Decisions (1):**
- `decisions/2026-08-17-pulse-data-sources.md` — DECISION-004: Migrate VIX to FRED, demote Yahoo

**Index:** `index.md` — Updated with all new pages

## 2026-08-17 — Ingest: EWAutoTP.mqh

**Source:** `raw/src5/shared/modules/ew/EWAutoTP.mqh`
**Operation:** Full entity + concept extraction

### Pages Created

**Entities (5):**
- `entities/ew-auto-tp.md` — Main EWAutoTP module
- `entities/ind-ew-fibengine.md` — FibEngine indicator reference
- `entities/ind-ew-kennedychannel.md` — KennedyChannel indicator reference
- `entities/ind-ew-wavelabeler.md` — WaveLabeler indicator reference
- `entities/ind-ew-confirmationengine.md` — ConfirmationEngine indicator reference

**Concepts (14):**
- `concepts/auto-tp-adjustment.md` — Dynamic TP management
- `concepts/fibonacci-extension-ladder.md` — 161.8→261.8→423.6 TP stepping
- `concepts/kennedy-channel-trailing-stop.md` — Dynamic trailing stop
- `concepts/wave-exhaustion-exit.md` — Emergency close on exhaustion
- `concepts/extension-detection.md` — 5% proximity detection
- `concepts/circular-dependency-prevention.md` — UseKennedy=false pattern
- `concepts/adjust-delay.md` — Configurable bar delay
- `concepts/five-percent-proximity-buffer.md` — Early warning zone
- `concepts/profile-id.md` — EW system profile parameterization
- `concepts/indicator-buffer-constants.md` — Named buffer index constants
- `concepts/extern-inputs-in-include.md` — Input declarations in shared modules
- `concepts/empty-value-guard.md` — EMPTY_VALUE guard pattern
- `concepts/bearish-ladder-inversion.md` — Inverted TP logic for sells
- `concepts/exhaustion-exit-gating.md` — Phase 1 gates Phase 2-3

**Reviews (3):**
- `reviews/2026-08-17-ewauto-tp-section8-collision.md` — Function name collision
- `reviews/2026-08-17-ewauto-tp-hardcoded-paths.md` — Hardcoded indicator paths
- `reviews/2026-08-17-ewauto-tp-extern-inputs.md` — Extern inputs in include file

**Index:** `index.md` — Updated with all new pages

## 2026-08-17 — Ingest: Ind_Parabolic.mq5

**Source:** `raw/src/indicators/Ind_Parabolic.mq5`
**Operation:** Full entity + concept extraction

### Pages Created

**Entities (1):**
- `entities/ind-parabolic.md` — Parabolic SAR indicator

**Concepts (5):**
- `concepts/parabolic-sar-calculation.md` — Core SAR formula
- `concepts/acceleration-factor.md` — Step multiplier behavior
- `concepts/extreme-point-tracking.md` — Highest high/lowest low tracking
- `concepts/sar-reversal-logic.md` — Trend reversal conditions
- `concepts/sar-clamping.md` — SAR bounds enforcement

**Index:** `index.md` — Updated with all new pages
