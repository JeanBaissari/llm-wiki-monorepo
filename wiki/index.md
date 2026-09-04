---
title: Trading Suite Wiki
type: index
created: 2026-08-17
updated: 2026-08-18
wiki_config:
  schema: algorithmic-trading-mql4
  page_dirs: [concepts, entities, summaries, comparisons, graphs, synthesis]
  has_raw: true
  has_log: true
  has_audit: true
  has_outputs: true
---

# Index — Trading Suite Wiki

> One-sentence scope of the wiki.

## Navigation
- [[#Concepts]] · [[#Entities]] · [[#Decisions]] · [[#Reviews]] · [[#Sources]] · [[#Open Questions]]

## Concepts

### MQL5 Coding Standards (from STANDARDS.md)
- [[wiki/concepts/mql5-coding-standards|MQL5 Coding Standards]] — Professional coding standards for MT5 ecosystem
- [[wiki/concepts/module-guard-macros|Module Guard Macros]] — `__SRC5_<NAMESPACE>_<MODULE>_MQH__` format for all .mqh files
- [[wiki/concepts/indicator-buffer-rules|Indicator Buffer Rules]] — Explicit buffer types: INDICATOR_DATA, INDICATOR_CALCULATIONS, INDICATOR_COLOR
- [[wiki/concepts/price-symbol-access-rules|Price/Symbol Access Rules]] — SymbolInfoDouble instead of Ask/Bid globals
- [[wiki/concepts/icustom-handle-pattern|iCustom Handle Pattern]] — Handle-based indicator access with caching
- [[wiki/concepts/trade-operations-ctrade|Trade Operations (CTrade)]] — CTrade for all order operations, no raw OrderSend
- [[wiki/concepts/input-validation-oninit|Input Validation in OnInit]] — INIT_PARAMETERS_INCORRECT for invalid configs
- [[wiki/concepts/ontrade-transaction-lifecycle|OnTradeTransaction Lifecycle]] — Trade lifecycle event tracking
- [[wiki/concepts/version-management|Version Management]] — MQL5 "X.XX", Python "X.Y.Z", DLL "X,Y,Z" formats
- [[wiki/concepts/backtest-methodology|Backtest Methodology]] — Tick data requirements, pass/fail criteria
- [[wiki/concepts/ea-code-review-checklist|EA Code Review Checklist]] — 12-point validation before Phase 3
- [[wiki/concepts/module-contribution-guide|Module Contribution Guide]] — When to add shared modules, namespace conventions
- [[wiki/concepts/research-first-gate|Research-First Gate]] — No strategy reaches development without research PRD

### Auto-TP / Take-Profit Management
- [[wiki/concepts/auto-tp-adjustment|Auto-TP Adjustment]] — Dynamic TP management during Wave 3 extensions
- [[wiki/concepts/fibonacci-extension-ladder|Fibonacci Extension Ladder]] — 161.8 → 261.8 → 423.6% TP stepping
- [[wiki/concepts/kennedy-channel-trailing-stop|Kennedy Channel Trailing Stop]] — Dynamic trailing stop from Kennedy channel boundaries
- [[wiki/concepts/wave-exhaustion-exit|Wave Exhaustion Exit]] — Close all orders when completion > 80 + divergence
- [[wiki/concepts/extension-detection|Extension Detection]] — 5% proximity buffer to 161.8% target
- [[wiki/concepts/adjust-delay|Adjust Delay]] — Configurable bar delay before TP modification
- [[wiki/concepts/bearish-ladder-inversion|Bearish Ladder Inversion]] — Inverted TP logic for sell orders
- [[wiki/concepts/exhaustion-exit-gating|Exhaustion Exit Gating]] — Phase 1 gates Phase 2-3

### Indicator / Signal Concepts
- [[wiki/concepts/five-percent-proximity-buffer|5% Proximity Buffer]] — Early-warning zone for extension detection
- [[wiki/concepts/profile-id|Profile ID]] — EW system profile parameterization
- [[wiki/concepts/indicator-buffer-constants|Indicator Buffer Constants]] — Named constants for 4 consumed indicators
- [[wiki/concepts/empty-value-guard|EMPTY_VALUE Guard]] — Pattern for guarding against invalid buffer values
- [[wiki/concepts/circular-dependency-prevention|Circular Dependency Prevention]] — UseKennedy=false pattern
- [[wiki/concepts/extern-inputs-in-include|Extern Inputs in Include File]] — Input declarations in shared modules (violates standard)
- [[wiki/concepts/bulls-power|Bulls Power]] — Oscillator measuring buying pressure via High - EMA

### PulseEngine Data Sources
- [[wiki/concepts/commercial-licensing-risk|Commercial Licensing Risk]] — Yahoo Finance not licensed for commercial use
- [[wiki/concepts/fetcher-error-handling|Fetcher Error Handling]] — HTTP status checking, JSON validation, graceful degradation
- [[wiki/concepts/exponential-backoff|Exponential Backoff]] — 60s→120s→240s retry strategy on fetcher errors
- [[wiki/concepts/structured-logging-fetcher|Structured Logging]] — JSON event types for fetcher failure modes
- [[wiki/concepts/blocked-stubs|Blocked Stubs]] — AUDJPY, GDT, OU hardcoded values awaiting source discovery
- [[wiki/concepts/rag-status|RAG Status]] — Red/Amber/Green classification for data source readiness
- [[wiki/concepts/source-selection|Source Selection]] — API selection criteria: licensing, cost, reliability, quality
- [[wiki/concepts/dev-only-fallback|Dev-Only Fallback]] — Yahoo Finance retained for development with log warnings

### License Taxonomy & Provenance
- [[wiki/concepts/license-taxonomy|License Taxonomy]] — Classification system for source licenses and rights evaluation
- [[wiki/concepts/rights-axes|Rights Axes]] — 5 independent dimensions: evaluation, modification, distribution, publication, redistribution
- [[wiki/concepts/distribution-channels|Distribution Channels]] — 7 channels: internal_evaluation through documentation_excerpt
- [[wiki/concepts/fidelity-tiers|Fidelity Tiers]] — 6 tiers (T0–TX) orthogonal to rights
- [[wiki/concepts/fail-closed-licensing|Fail-Closed Licensing]] — Default-deny rules for unknown/missing license info
- [[wiki/concepts/license-classes|License Classes]] — v2 five classes: permissive, weak-copyleft, strong-copyleft, nc-restricted, custom-terms
- [[wiki/concepts/cc-family-handling|CC-Family Handling]] — Creative Commons NC restrictions and dual-header conflict rules
- [[wiki/concepts/mpl-reauthoring-rules|MPL-2.0 Re-Authoring Rules]] — File-level copyleft requirements for MPL-2.0 derivatives
- [[wiki/concepts/product-channel-rights|Product-Channel Rights]] — Product channels never broaden source rights
- [[wiki/concepts/permission-evidence|Permission Evidence]] — Required fields: license ID, evidence, rights, restrictions, reviewer, date

### Parabolic SAR Algorithm
- [[wiki/concepts/parabolic-sar-calculation|Parabolic SAR Calculation]] — Core SAR formula: SAR[i] = SAR[i-1] + step × (EP - SAR[i-1])
- [[wiki/concepts/acceleration-factor|Acceleration Factor]] — Step multiplier controlling SAR convergence speed
- [[wiki/concepts/extreme-point-tracking|Extreme Point Tracking]] — Highest high/lowest low tracking for SAR direction
- [[wiki/concepts/sar-reversal-logic|SAR Reversal Logic]] — Conditions triggering trend direction changes
- [[wiki/concepts/sar-clamping|SAR Clamping]] — Preventing SAR from exceeding recent price extremes

## Entities

### MQL5 Standard Library (from STANDARDS.md)
- [[wiki/entities/ctrade|CTrade]] — MQL5 standard library class for position management
- [[wiki/entities/cpositioninfo|CPositionInfo]] — MQL5 standard library class for reading position properties
- [[wiki/entities/corderops|COrderOps]] — Custom order operations wrapper with position lifecycle tracking
- [[wiki/entities/cglobaleventbus|CGlobalEventBus]] — Event bus class for inter-component communication

### MIG — PulseEngine Data Sources
- [[wiki/entities/mig-405b-data-source-hardening|MIG-405b]] — External data source selection, documentation & fetcher error handling (Phase 4)
- [[wiki/entities/fred-vix-fetcher|FredVIXFetcher]] — FRED API VIX fetcher replacing Yahoo Finance

### EW System — Auto-TP
- [[wiki/entities/ew-auto-tp|EWAutoTP]] — Auto-adjusting TP ladder, Kennedy trailing stop, exhaustion exit orchestrator (v1.00)

### EW System — Indicators
- [[wiki/entities/ind-ew-fibengine|Ind_EW_FibEngine]] — Fibonacci extension/retracement price levels
- [[wiki/entities/ind-ew-kennedychannel|Ind_EW_KennedyChannel]] — Kennedy channel boundaries + trailing stop
- [[wiki/entities/ind-ew-wavelabeler|Ind_EW_WaveLabeler]] — Wave number, state, completion probability
- [[wiki/entities/ind-ew-confirmationengine|Ind_EW_ConfirmationEngine]] — Multi-factor confirmation (RSI, BB, divergence, volume)

### Standalone Indicators
- [[wiki/entities/ind-bulls|Ind Bulls]] — Bulls Power oscillator measuring buying pressure (v1.00)
- [[wiki/entities/ind-parabolic|Ind Parabolic]] — Parabolic Stop-And-Reversal indicator (v1.00)

## Decisions

- [[wiki/decisions/2026-05-18-mql5-native-code-requirement|MQL5-Native Code Requirement]] — Write pure MQL5, not MQL4 compatibility mode
- [[wiki/decisions/2026-05-18-research-first-gate-enforcement|Research-First Gate Enforcement]] — No strategy reaches Phase 3 without research PRD
- [[wiki/decisions/2026-08-17-pulse-data-sources|DECISION-004: PulseEngine Data Source Selection]] — Migrate VIX to FRED, demote Yahoo to dev-only, document blocked stubs

## Reviews

- [[wiki/reviews/2026-08-17-ewauto-tp-section8-collision|2026-08-17 EWAutoTP Section 8 Collision]] — PipFactor/LogInfo/LogError redefine inline, COLLIDE with Logger/Helpers
- [[wiki/reviews/2026-08-17-ewauto-tp-hardcoded-paths|2026-08-17 EWAutoTP Hardcoded Paths]] — Indicator paths hardcoded as string literals
- [[wiki/reviews/2026-08-17-ewauto-tp-extern-inputs|2026-08-17 EWAutoTP Extern Inputs]] — extern inputs in shared module violate standard

## Sources

- [[wiki/sources/standards-md|STANDARDS.md — MT5 Algorithmic Trading Suite]] — Professional coding standards, quality gates, and contribution guides
- [[wiki/sources/ind-bulls-source|Ind Bulls Source]] — Bulls Power indicator MQL5 source code
- [[wiki/sources/license-taxonomy|License Taxonomy and Rights Matrix]] — PS_003/BPS_011 governing license classification and rights evaluation

## Synthesis

- [[wiki/synthesis/standards-md-extraction-summary|STANDARDS.md Extraction Summary]] — Key entities, concepts, claims, relationships, and contradictions from standards document

## Architecture

- [[wiki/architecture/module-namespace-architecture|Module Namespace Architecture]] — Module dependency graph and namespace conventions for MT5 suite

## Open Questions

- [[wiki/entities/ind-ew-triangledetector|Ind_EW_TriangleDetector]] — Triangle pattern detector (prior ingest)
- [[wiki/concepts/contracting-triangle|Contracting Triangle]] — Monotonic amplitude decrease pattern
- [[wiki/concepts/triangle-classification|Triangle Classification]] — 7 triangle variant taxonomy
- [[wiki/concepts/running-triangle|Running Triangle]] — Same-direction sloping trendlines pattern
