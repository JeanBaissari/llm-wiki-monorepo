---
title: Redis
type: entity
created: 2026-08-11
updated: 2026-08-11
sources: [redis-sds]
tags: [redis, database, data-structure]
confidence: high
---
# Redis

Redis is an open-source, in-memory data structure server, first released in 2009.

## Internals

Redis serves key/value operations from RAM, driven by a single-threaded
[[event-loop|Event Loop]]. Strings are stored with the [[sds|Simple Dynamic Strings]]
representation, which keeps lengths explicit and binary-safe.

Atomicity across multiple commands is available through
[[lua-scripting|Lua Scripting]], and durability is handled by the
[[redis-persistence|Redis Persistence]] layer (RDB snapshots plus append-only file).

## Related

- Created by [[antirez|Salvatore Sanfilippo]].
- Scales horizontally through [[redis-cluster|Redis Cluster]].
- See the [[redis-internals-overview|Redis Internals Overview]] for the full map.
