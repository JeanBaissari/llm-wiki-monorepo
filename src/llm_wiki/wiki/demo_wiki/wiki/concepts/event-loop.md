---
title: Event Loop
type: concept
created: 2026-08-11
updated: 2026-08-11
sources: [redis-sds]
tags: [redis, concurrency, event-loop]
confidence: high
---
# Event Loop

The event loop is the single-threaded core of [[redis|Redis]]'s command processing.

## Design

Redis multiplexes sockets over a small `ae` event loop (select/epoll/kqueue).
Because there is exactly one thread, commands run without locking; long-running
scripts are the exception, which is why [[lua-scripting|Lua Scripting]] cooperates
with the loop by limiting script execution time.

The same loop structure powers the per-node dispatch in
[[redis-cluster|Redis Cluster]].
