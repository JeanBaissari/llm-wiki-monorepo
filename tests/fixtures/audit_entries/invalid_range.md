---
id: audit-004
type: review
status: open
created: 2026-01-15
updated: 2026-01-15
page: wiki/concepts/test_page.md
anchor:
  line: 99999
  context: "Nonexistent line"
  offset: 0
severity: low
tags: [test, fixture, invalid-range]
---

## Summary

This anchor points to a line (99999) that exceeds the file's length.

## Suggestion

Check anchor resolution with invalid ranges and verify graceful fallback.
