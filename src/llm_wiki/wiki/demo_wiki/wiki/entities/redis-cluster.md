---
title: Redis Cluster
type: entity
created: 2026-08-11
updated: 2026-08-11
sources: [redis-sds]
tags: [redis, distributed-systems, sharding]
confidence: high
---
# Redis Cluster

Redis Cluster is the sharding layer that lets [[redis|Redis]] scale horizontally
across multiple nodes.

## How it works

Keys are mapped to 16,384 hash slots, and each node owns a range of slots. A
single-threaded [[event-loop|Event Loop]] per node keeps command handling simple,
while the cluster protocol handles slot rebalancing and failover.
