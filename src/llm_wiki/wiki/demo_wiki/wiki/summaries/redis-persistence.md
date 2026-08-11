---
title: Redis Persistence
type: summary
created: 2026-08-11
updated: 2026-08-11
sources: [redis-sds]
tags: [redis, persistence, durability]
confidence: high
---
# Redis Persistence

[[redis|Redis]] persists state through two mechanisms: point-in-time RDB snapshots
and an append-only file (AOF) that replays every write.

## Trade-offs

RDB snapshots are compact and fast to load but can lose the writes since the last
snapshot. AOF replays are more durable but grow over time and need compaction.
Snapshot buffers reuse the [[sds|Simple Dynamic Strings]] representation to move
memory efficiently during background saves.
