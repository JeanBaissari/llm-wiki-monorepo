# Security Policy

## Supported versions

The **0.6.x** release line is the supported line and receives security fixes
(current release: see [`docs/release/versioning.md`](docs/release/versioning.md)).
Older release lines are unsupported and should be upgraded.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately through GitHub Security Advisories:

1. Go to **Security → Advisories → Report a vulnerability** in
   [`JeanBaissari/llm-wiki-monorepo`](https://github.com/JeanBaissari/llm-wiki-monorepo/security/advisories/new).
2. Include affected version(s), a description of the issue, reproduction steps,
   and any known impact.

Maintainers will triage and respond in the advisory thread. Please allow time
for a fix before any public disclosure, and coordinate disclosure timing with
the maintainers.

## Trust boundary

Per-wiki authorization and visibility are deliberately the **filesystem + git
permissions** — there is no application-level auth layer, and none is planned.
Files-first is the design. The full boundary statement is in
[`docs/operations/security-and-boundaries.md`](docs/operations/security-and-boundaries.md);
the essentials:

- **MCP server is stdio-local.** It speaks MCP over standard input/output and
  binds no ports; it only talks to the process that launched it.
- **The web preview is opt-in and local-only.** `web-viewer` binds a localhost
  port for a single user's browser; never expose it to untrusted networks
  without an authentication layer in front.
- **Never commit secrets.** No `.env`, API keys, tokens, or credentials in a
  wiki repo. Start from [`.env.example`](.env.example) and keep `.env`
  gitignored.
- **`raw/` is immutable for provenance, not secrecy.** Protect sensitive
  sources with the filesystem permissions you would use for any file.

Multi-user wikis assume shared-filesystem trust: anyone who can read/write the
`wiki/` directory can read/write the wiki.
