# Concurrency Control in llm-wiki-monorepo

This document describes the concurrency guarantees, locking strategy, and
conflict resolution workflow for the LLM Wiki monorepo.

## Architecture

The wiki directory is the shared state for the entire system. Every component
reads and writes the same markdown files. Starting in v0.2.0 (stable through v0.3.4), all writes are
protected by a three-layer concurrency strategy:

1. **Per-page advisory locking** — Only one agent can write to a page at a time.
2. **Atomic writes** — Files are never partially written; crash leaves the old
   file intact.
3. **Content-hash conflict detection** — Optimistic locking detects when another
   agent modified a page since you read it.

## Single-Machine Multi-Agent (File Locking)

On a single machine, concurrent agent processes coordinate through file locks.

### How It Works

- When an agent writes to `wiki/pages/entities/Example.md`, it first acquires a
  lock at `wiki/pages/entities/Example.md.lock`.
- The lock file contains the holder's PID, timestamp, and hostname.
- If another agent tries to write the same page, it waits up to `--lock-timeout`
  seconds (default: 30s) for the lock to be released.
- If the timeout is exceeded, the write fails with a `locked` status and a clear
  error message.

### Stale Lock Recovery

If an agent crashes while holding a lock, the lock file must be cleaned up:

1. **Automatic**: Any agent attempting to acquire a lock first checks if the
   existing lock is stale. A lock is stale if:
   - It is older than `lock_timeout × 3` seconds (timeout-based, works everywhere).
   - On Unix: the PID in the lock file belongs to a dead process (fast-path).

2. **Manual**: Run `python3 lint_wiki.py <wiki-root> --clean-stale-locks` to
   remove all stale locks from the wiki.

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

All wiki file writes use an atomic write pattern:

1. Write content to a temp file: `.<filename>.tmp.<PID>`
2. Force-flush to disk (`fsync`)
3. Atomically rename to the target filename (`os.rename`)

POSIX guarantees `os.rename()` is atomic on the same filesystem. If the process
crashes mid-write:
- The original file is untouched.
- Only the `.tmp.<PID>` file is left behind (cleaned up automatically on next run).

## Optimistic Locking (Content Hash)

Each wiki page stores a `_content_hash` field in its YAML frontmatter:

```yaml
---
title: Example Page
type: concept
_content_hash: a1b2c3d4...
---
```

Before writing, the agent:
1. Reads the current on-disk hash.
2. Compares it with the hash the page had when the agent first read it.
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

1. Find conflict files: `ls wiki/pages/**/*"(conflict).md"`
2. Compare the conflict file with the current page:
   ```bash
   diff wiki/pages/entities/Page.md "wiki/pages/entities/Page (conflict).md"
   ```
3. Manually merge desired changes into the original page.
4. Delete the conflict file: `rm "wiki/pages/entities/Page (conflict).md"`
5. Commit: `git add wiki/ && git commit -m "Resolve conflict for Page.md"`

### Automatic Conflict Cleanup

- **Lint check**: Running `python3 lint_wiki.py <wiki-root>` flags unresolved
  conflict files as severity=error (Pass 16).
- **Archive**: Running `python3 lint_wiki.py <wiki-root> --clean-conflicts`
  moves conflict files older than 30 days to `_archive/conflicts/`.
- **Scheduled**: The EOW (end-of-week) cron pipeline includes automatic conflict
  cleanup as part of the weekly maintenance cycle.

## `--force` Flag

The `--force` flag skips conflict detection completely:
- Still acquires the lock (prevents mid-write corruption from concurrent writes).
- Still writes atomically.
- Skips the content hash comparison.

Use `--force` for:
- Known-good overwrites in single-agent mode.
- Automated scripts that have already resolved conflicts externally.
- Disaster recovery where stale lock files block progress.

## Lock Timeout Configuration

| Method | Example |
|--------|---------|
| CLI flag | `python3 ingest.py <wiki> <source> --lock-timeout 10` |
| Env var | `LLM_WIKI_LOCK_TIMEOUT=10 python3 ingest.py <wiki> <source>` |
| Default | 30 seconds |

## Limitations

- **Not CRDT-based**: Multi-agent editing of the SAME page simultaneously is not
  supported. Two agents editing the same page will produce a conflict file. This is
  intentional — wiki pages are authored once and refined over time, not
  simultaneously edited.
- **Local filesystem only**: `fcntl`/`msvcrt` locking requires a local filesystem.
  NFS and network filesystems are explicitly not supported. Use the git-based merge
  workflow for multi-machine coordination.
- **No distributed lock manager**: Redis, etcd, and other distributed coordination
  primitives are out of scope for v0.3.4. Git is the distributed coordination
  primitive.
