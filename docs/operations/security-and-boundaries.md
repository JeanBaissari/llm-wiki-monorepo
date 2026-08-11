# Security & Trust Boundary

This document states the security and visibility boundary of an LLM Wiki
deployment. It is a **stated boundary, not a gap to be closed**: the system is
deliberately files-first, and per-wiki authentication/visibility is the
filesystem and the git repo — not a permissions layer in the application.

> There is no per-wiki auth/visibility layer, and none is planned; auth/visibility is the filesystem and the git repo.

## Trust model: files-first

A wiki is a directory of Markdown pages plus its git repository. That means
**per-wiki authorization, audit, and provenance are the filesystem + git
permissions**, by design:

- Who can read a wiki = who can read the `wiki/` directory (OS filesystem
  permissions).
- Who can write a wiki = who can write files under `wiki/` (OS permissions +
  git write access).
- What changed and why = the git history (the versioned, reviewable, reversible
  audit trail).

**Multi-user wikis assume shared-filesystem trust.** All agents and users that
can reach the `wiki/` directory and its git repo are trusted to read and write
it. There is no per-page, per-user, or per-role permission model inside the
application. If you need that, put the wiki on a filesystem/private repo whose
permissions express it (see recommended patterns below).

**Derived state carries the same boundary.** The SQLite caches (FTS5 search
index, vector store, entity-alias tables) and the `.llm-wiki/` sidecar state
(alias tables, claim sidecar) are *derived* from `wiki/` files and are
regenerable — they are **not an auth surface** and hold no secrets beyond what
is already in the source files.

## Network surface

The system has a deliberately small network surface:

- **MCP server (`llm-wiki-mcp`) is stdio-local with no network surface.** It
  speaks the MCP protocol over standard input/output. **No HTTP or RPC
  listeners; nothing binds a port.** It only ever talks to the process that
  launched it.
- **Web preview (`llm-wiki serve`) is an opt-in, local-only server** for human
  browsing (mermaid, KaTeX, audit feedback). It binds a localhost port and is
  meant for a single user's browser. **It must not be exposed to untrusted
  networks without an authentication layer in front of it** (see pattern 2).
- The Python sidecar spawned by the MCP server never leaves the repo —
  everything is local and private.

## Recommended patterns

When a deployment needs a stronger boundary than single-user local, apply these
patterns at the *platform* layer — the application does not enforce any of
them:

1. **Git-based authorization** — keep the wiki in a private repository; gate
   writes with branch protection and code review. Wiki writes are commits, so
   every change is attributable and reversible.
2. **Private host behind auth for a shared web preview** — if the web preview
   is ever shared, deploy it behind an authenticated private host
   (reverse-proxy auth, SSO, VPN). Never expose the preview directly to the
   open internet.
3. **Editor-level ACLs** — enforce per-user read/write with the editor or OS:
   Obsidian vault permissions, per-directory OS file ACLs on `wiki/` and
   `raw/`, or a shared drive with group permissions.
4. **Never commit secrets or env files** — no `.env`, API keys, tokens, or
   credentials in the wiki repo. Use `.gitignore` for env files and
   `python-dotenv` for local overrides (loaded from outside the repo).
5. **`raw/` immutability is a provenance guarantee, not a secrecy guarantee** —
   sources are never modified by the pipeline, but they are as readable as the
   rest of the filesystem. Protect sensitive sources with the same filesystem
   permissions you would apply to any file.

## Boundary statement

- **In scope:** filesystem + git permissions are the auth/visibility boundary;
  derived caches are regenerable and not an auth surface; the MCP server is
  stdio-local; the web preview is opt-in local-only.
- **Out of scope (by design):** any application-level authentication,
  authorization, or per-wiki visibility layer. No such code is planned.
- **Do not:** expose `llm-wiki serve` to untrusted networks without an
  authentication layer; commit secrets into the wiki repo; treat derived
  caches or `raw/` as an access-control mechanism.
