---
id: audit-003
type: review
status: open
created: 2026-01-15
updated: 2026-01-15
page: wiki/concepts/test_page.md
anchor:
  line: 5
  context: "# Test Page"
  offset: 1
severity: low
tags: [test, fixture, duplicate]
---

## Summary

This anchor text ("# Test Page") may match multiple locations in the file
or appear in multiple pages, creating ambiguity.

## Suggestion

Use a more specific anchor context or line number.
