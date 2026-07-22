# Schema — Machine-Readable Contracts

Canonical machine-readable schema artifacts for the llm-wiki-monorepo.

## Layout

```
schema/
├── README.md
├── versions/
│   ├── v0.2.1/
│   │   ├── page.schema.json               — Wiki page frontmatter
│   │   ├── audit.schema.json               — Audit feedback entries
│   │   ├── log-event.schema.json           — Operation log events
│   │   ├── template-schema.schema.json     — Template metadata
│   │   ├── operation-manifest.schema.json  — Operation manifests
│   │   └── claim-sidecar.schema.json       — Optional claim records
│   └── migrations.json                     — Migration registry
├── fixtures/
│   ├── valid/                              — Valid schema examples
│   └── invalid/                            — Invalid schema examples
└── generated/
    └── base-schema.md                      — Generated human-readable schema
```

## Versioning

Schema versions are pegged to the project release version (v0.2.1).
The `current_version` field in `migrations.json` tracks the active schema.

## Validators

- Python: `src/llm_wiki/schema_validator.py`
- TypeScript: `audit-shared/src/schema_validator.ts`

Both consume the same JSON schema files and shared golden fixtures.
