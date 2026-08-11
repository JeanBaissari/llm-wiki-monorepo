---
title: Lua Scripting
type: concept
created: 2026-08-11
updated: 2026-08-11
sources: [redis-sds]
tags: [redis, scripting, atomicity]
confidence: high
---
# Lua Scripting

Lua Scripting lets a client run a script atomically inside [[redis|Redis]] via EVAL.

## Design

The embedded Lua interpreter runs on the same thread as the
[[event-loop|Event Loop]], so a script's commands execute without interleaving.
This gives multi-command atomicity without transactions. The scripting engine was
introduced by [[antirez|Salvatore Sanfilippo]] alongside the core data structures.
