# Concurrency Control in llm-wiki-monorepo

This document describes the concurrency guarantees, locking strategy, and
conflict resolution workflow for the LLM Wiki monorepo.

## Architecture

The wiki directory is the shared state for the entire system. Every component
reads and writes the same markdown files. All writes are protected by a
three-layer concurrency strategy:

1. **Per-page advisory locking** — Only one agent can write to a page at a time.
2. **Atomic writes** — Files are never partially written; crash leaves the old
   file intact.
3. **Content-hash conflict detection** — Optimistic locking detects when another
   agent modified a page since you read it.

The implementation lives in `src/llm_wiki/core/locking.py` (locks) and
`src/llm_wiki/core/atomic.py` + `src/llm_wiki/core/hashing.py` (writes and
conflict hashes). `skill/scripts/lock_wiki.py` re-exports the primitives.

## Single-Machine Multi-Agent (File Locking)

On a single machine, concurrent agent processes coordinate through file locks.

### How It Works

- When an agent writes to a page (e.g. `wiki/entities/Example.md`), it first
  acquires a lock at `<page path>.lock` — i.e.
  `wiki/entities/Example.md.lock` next to the page. Flat wikis lock the page in
  place; lock files always sit next to the page they protect.
- The lock file is created with `O_CREAT | O_EXCL` (atomic claim) and carries
  the holder's metadata: `token`, `pid`, `timestamp`, `monotonic`, and
  `hostname`.
- If another agent tries to write the same page, it retries with a small
  backoff until the default timeout (30 seconds) is exceeded; then the write
  fails with a `locked` status and a clear error message.

### Stale Lock Recovery

If an agent crashes while holding a lock, the lock is broken automatically on
the next acquire attempt under these rules (`locking.py`):

1. **Dead owner PID**: the lock is stale once its age exceeds
   `timeout × STALE_TIMEOUT_FACTOR` (`30s × 3 = 90s` by default).
2. **Unreadable PID / unknown liveness**: the lock is only broken after the
   absolute `HARD_STALE_LIMIT` of 300 seconds, so a lock that is still being
   written is never treated as stale.
3. Breaking is a claim operation: the lock file is renamed aside, re-verified,
   and only removed if it is still stale — a lock that became live in the
   meantime is restored rather than deleted.

For bulk manual cleanup there is no lint flag: `lint_wiki.py` accepts only
`--check-templates` and `--json`. The `clean_stale_locks(pages_dir)` helper in
`llm_wiki.core.locking` (re-exported by `skill/scripts/lock_wiki.py`) performs
the same staleness-aware cleanup programmatically:

```bash
python3 -c "from llm_wiki.core.locking import clean_stale_locks; print(clean_stale_locks('wiki/'))"
```

## Multi-Machine (Git-Based Merge)

File locking with `fcntl`/`portalocker` only works on local filesystems. For
multi-machine scenarios, the recommended workflow is git-based:

```bash
# Before any agent operation:
git pull --rebase origin main

# Agent performs writes (locks are local to this machine)...

# After agent operation:
git add wiki/
git commit -m "Agent: <description of changes>"
git pull --rebase origin main  # Fetch other machines' changes
# If conflicts: git resolves what it can, marks conflicts for human
git push origin main
```

Git's standard merge markers (`<<<<<<<`, `=======`, `>>>>>>>`) surface conflicts
that filesystem-level optimistic locking couldn't prevent (e.g., two agents on
different machines modified the SAME page before either committed).

## Atomic Writes

All wiki file writes use an atomic write pattern (`llm_wiki.core.atomic.atomic_write`):

1. Write content to a temp file: `.<filename>.tmp.<PID>`
2. Force-flush to disk (`fsync`)
3. Atomically replace to the target filename (`os.replace`)

POSIX guarantees `os.rename()` is atomic on the same filesystem, and
`os.replace()` extends atomic-replace semantics to Windows. If the process
crashes mid-write:
- The original file is untouched.
- Only the `.tmp.<PID>` file is left behind (cleaned up automatically on next run).

## Optimistic Locking (Content Hash)

Each written wiki page stores a `_content_hash` field in its YAML frontmatter:

```yaml
---
title: Example Page
type: concept
_content_hash: a1b2c3d4...
---
```

The hash is computed over the page body with the `_content_hash` line removed,
so injecting the hash never changes the hash. Before writing, the writer:
1. Reads the current on-disk hash.
2. Compares it with the hash the new content expects to replace (`read_hash`).
3. If the hashes differ, another agent modified the page → **conflict**.

## Conflict Resolution

### How Conflicts Are Detected

When Agent A reads a page to modify it, the page content hash is `X`. Before
writing, Agent A re-checks the on-disk hash. If it's now `Y` (Agent B modified
the page), a conflict is detected.

### What Happens on Conflict

Agent A's changes are NOT discarded. Instead:
1. The new content is written to `PageName (conflict).md` (Obsidian-compatible convention).
2. A clear stderr message is emitted: `CONFLICT: <page> was modified by another agent. Your changes saved to <page> (conflict).md.`
3. The original page (modified by Agent B) is left untouched on disk.

### Resolving Conflicts Manually

1. Find conflict files: `find wiki -name "*(conflict).md"`
2. Compare the conflict file with the current page:
   ```bash
   diff wiki/entities/Page.md "wiki/entities/Page (conflict).md"
   ```
3. Manually merge desired changes into the original page.
4. Delete the conflict file: `rm "wiki/entities/Page (conflict).md"`
5. Commit: `git add wiki/ && git commit -m "Resolve conflict for Page.md"`

There is no automatic conflict-file cleanup and no `--clean-conflicts` lint
flag. Lint flags unresolved **git merge markers** (`<<<<<<<`) inside wiki files
as issues; `(conflict).md` files must be resolved manually with the steps
above. If you keep a conflict file on disk, it counts as a normal page until
resolved.

## `--force` Flag

The `--force` flag skips conflict detection completely:
- Still acquires the lock (prevents mid-write corruption from concurrent writes).
- Still writes atomically.
- Skips the content hash comparison.

Use `--force` for:
- Known-good overwrites in single-agent mode.
- Automated scripts that have already resolved conflicts externally.
- Re-running an ingest whose output you intentionally want to replace.

## Lock Timeout

| Method | Value |
|--------|-------|
| Default | 30 seconds (`DEFAULT_LOCK_TIMEOUT` in `llm_wiki.core.locking`) |
| Programmatic | `WikiLock(page_path, timeout=<seconds>)` / `write_wiki(..., lock_timeout=<seconds>)` |

There is currently **no** `--lock-timeout` CLI flag and no
`LLM_WIKI_LOCK_TIMEOUT` env var; raising the timeout requires calling the
locking API directly.

## Limitations

- **Not CRDT-based**: Multi-agent editing of the SAME page simultaneously is not
  supported. Two agents editing the same page will produce a conflict file. This is
  intentional — wiki pages are authored once and refined over time, not
  simultaneously edited.
- **Local filesystem only**: `fcntl`/`msvcrt` locking requires a local filesystem.
  NFS and network filesystems are explicitly not supported. Use the git-based merge
  workflow for multi-machine coordination.
- **No distributed lock manager**: Redis, etcd, and other distributed coordination
  primitives are out of scope. Git is the distributed coordination primitive.
