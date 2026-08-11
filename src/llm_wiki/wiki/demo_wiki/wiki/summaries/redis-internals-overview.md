---
title: Redis Internals Overview
type: summary
created: 2026-08-11
updated: 2026-08-11
sources: [redis-sds]
tags: [redis, internals, overview]
confidence: high
---
# Redis Internals Overview

[[redis|Redis]] combines three core mechanisms: the [[sds|Simple Dynamic Strings]]
representation for memory-safe string handling, a single-threaded
[[event-loop|Event Loop]] for lock-free command processing, and
[[lua-scripting|Lua Scripting]] for atomic multi-command execution.

Durability is layered on top via [[redis-persistence|Redis Persistence]], and
[[redis-cluster|Redis Cluster]] extends the same model horizontally across nodes.
The project's design lineage runs through [[antirez|Salvatore Sanfilippo]], Redis's
creator.

This overview page is the recommended entry point for a first read of the wiki.
