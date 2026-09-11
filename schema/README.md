# Schema — Machine-Readable Contracts

Canonical machine-readable schema artifacts for the llm-wiki-monorepo.

## Layout

```
schema/
├── README.md
├── versions/
│   ├── v0.2.1/
│   │   ├── audit.schema.json                — Audit feedback entries
│   │   ├── claim-sidecar.schema.json        — Optional claim records
│   │   ├── log-event.schema.json            — Operation log events
│   │   ├── operation-manifest.schema.json   — Operation manifests
│   │   ├── page.schema.json                 — Wiki page frontmatter
│   │   └── template-schema.schema.json      — Template metadata
│   ├── migrate.py                           — Schema migration runner (stub)
│   └── migrations.json                      — Migration registry + current_version
├── fixtures/
│   ├── valid/                               — Valid schema examples
│   └── invalid/                             — Invalid schema examples
└── generated/
    └── base-schema.md                       — Generated human-readable schema
```

## Versioning

The schema has its own frozen `current_version` field in
[`versions/migrations.json`](versions/migrations.json) (currently `v0.2.1`).
It is **not** pegged to the project release version — project releases bump
`pyproject.toml`/`package.json`, while the schema only moves when a contract
migration is authored and registered in `migrations.json`.

## Validators

- Python: `src/llm_wiki/contracts/schema_validator.py`
- TypeScript: `audit-shared/src/schema_validator.ts`

Both consume the same JSON schema files and shared golden fixtures.
