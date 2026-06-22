# Algorithmic Trading Wiki — Purpose

This template scaffolds a wiki for developing, testing, and documenting
algorithmic trading strategies.

**What it is for:**

- Maintaining a complete inventory of trading strategies with their
  logic, parameters, and evolution.
- Recording backtest results with standardised performance metrics so
  strategies can be compared objectively.
- Documenting technical indicators and risk models with their
  mathematical definitions and implementation details.
- Tracking risk model assumptions, regime filters, and position sizing
  rules.

**What it is NOT for:**

- Live trading or order execution — use a broker's API or a dedicated
  execution platform for that.
- Real-time market data ingestion — this is a knowledge base, not a
  data pipeline.
- Portfolio-level P&L accounting — use the `finance` template or a
  dedicated portfolio system.

**Key extensibility pattern:** Each strategy links to the indicators
and risk models it depends on. Each backtest records the exact strategy
version, indicator parameters, and market regime for reproducibility.
