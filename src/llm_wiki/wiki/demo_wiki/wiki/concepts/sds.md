---
title: Simple Dynamic Strings
type: concept
created: 2026-08-11
updated: 2026-08-11
sources: [redis-sds]
tags: [redis, data-structure, memory]
confidence: high
---
# Simple Dynamic Strings

Simple Dynamic Strings (SDS) is the string representation used by [[redis|Redis]].

## Design

SDS stores an explicit length and free capacity alongside the buffer. This makes
length queries O(1), keeps the representation binary-safe, and amortizes append
costs by pre-allocating headroom — the same strategy that powers the
[[redis-persistence|Redis Persistence]] layer's snapshot buffers.

The design trade-offs are pinned in the `raw/redis-sds.md` source referenced by this
page's `sources` frontmatter.
