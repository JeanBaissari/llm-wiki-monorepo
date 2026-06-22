# Finance Wiki — Purpose

This template scaffolds a wiki for tracking financial markets,
instruments, trading strategies, and performance reports.

**What it is for:**

- Building a reference knowledge base on markets (equities, fixed income,
  FX, crypto, derivatives) and the instruments traded within them.
- Documenting and versioning trading strategies so their logic, risk
  profile, and historical performance are transparent.
- Storing periodic reports that aggregate portfolio-level metrics.

**What it is NOT for:**

- Tick data storage or backtesting infrastructure — use dedicated
  platforms (QuantConnect, backtrader, etc.) for that alongside the
  `algorithmic-trading` template.
- Portfolio management or order execution — this is a knowledge base,
  not a trading system.
- Tax or compliance record keeping.

**Key extensibility pattern:** Each strategy page links to the
instruments it trades and the reports that evaluate its performance.
Market pages describe the structure and participants of each market.
