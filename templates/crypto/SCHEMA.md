# Crypto Schema

Extends the shared base schema (`_shared/base-schema.md`) for the crypto domain. All base page types, frontmatter fields, naming conventions, index format, cross-referencing, and contradiction rules apply unless overridden below.

## Domain Page Types

| Type | Directory | Purpose |
|------|-----------|---------|
| protocol | crypto/protocols/ | A blockchain protocol — chain, consensus, TVL, launch |
| token | crypto/tokens/ | A cryptocurrency token — tokenomics, distribution, market data |
| defi_project | crypto/defi/ | A DeFi project — category, TVL, protocol dependencies |
| regulation | crypto/regulations/ | A regulatory framework or ruling — jurisdiction, scope, impact |

## Domain File Naming

- Protocols: `protocol-name.md` (e.g., `ethereum.md`, `solana.md`, `cosmos.md`)
- Tokens: `ticker-name.md` (e.g., `eth-ethereum.md`, `sol-solana.md`, `usdc-usd-coin.md`)
- DeFi projects: `project-name.md` (e.g., `uniswap.md`, `aave.md`, `compound.md`)
- Regulations: `jurisdiction-act-year.md` (e.g., `eu-mica-2023.md`, `us-executive-order-2022.md`)

## Domain-Specific Frontmatter

All base frontmatter fields (`type`, `title`, `tags`, `related`, `sources`, `created`, `updated`) apply.

### Protocol pages (with mandatory chain, consensus, tvl, launch_date)

```yaml
protocol: string               # Protocol name
chain: string                  # Layer or chain name (e.g., L1, L2, sidechain)
consensus: string              # Consensus mechanism (e.g., PoW, PoS, DPoS, PoA)
tvl: string                    # Total Value Locked (latest known figure with currency)
launch_date: YYYY-MM-DD       # Mainnet launch date
ecosystem: string              # Primary ecosystem (e.g., Ethereum, Cosmos, Solana)
native_token: string           # Native token ticker or slug
vm: string                     # Virtual machine (EVM, SVM, CosmWasm, etc.)
languages: [string]            # Smart contract languages supported
bridges: [string]              # Bridges to other chains
status: string                 # active | deprecated | sunset | planned
website: string                # Project website URL
```

### Token pages

```yaml
token: string                  # Token name
ticker: string                 # Ticker symbol (e.g., ETH, SOL, USDC)
type: string                   # native | erc20 | bep20 | spl | other
chain: string                  # Native chain
total_supply: string           # Maximum or total supply
circulating_supply: string     # Current circulating supply
launch_date: YYYY-MM-DD       # Token launch date
market_cap: string             # Latest known market cap
all_time_high: string          # ATH price and date (optional)
use_cases: [string]            # Primary use cases
```

### DeFi project pages

```yaml
defi_project: string           # Project name
category: string               # lending | dex | yield | derivatives | insurance | bridge | launchpad
tvl: string                    # Total Value Locked
chain: string                  # Primary chain
version: string                # Protocol version
governance: string             # Governance token (if any)
audits: [string]               # Audit firms or links
dependencies: [string]         # Protocols or infrastructure this relies on
risks: [string]                # Known risks (smart contract, oracle, liquidity, regulatory)
```

### Regulation pages

```yaml
regulation: string             # Regulation name
jurisdiction: string           # Country or region
body: string                   # Regulating authority
year: int                      # Year enacted or proposed
status: string                 # proposed | enacted | in_effect | challenged
scope: string                  # What it governs (exchanges, stablecoins, DeFi, NFTs, mining)
key_provisions: [string]       # Summary of key rules
impact: string                 # Impact assessment on the ecosystem
```

## Domain Index

`crypto/index.md` lists pages grouped by type (protocols, tokens, DeFi projects, regulations), plus a "Chain comparison table" and a "Regulatory tracker" section.
