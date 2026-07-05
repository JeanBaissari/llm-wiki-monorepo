# ADR 011: Inverted Entity Index for O(1) Link Suggestions

- **Status:** accepted
- **Date:** 2026-07-04
- **Context:** The `link_suggest.py` tool needs to find pages that mention the same entities but don't link to each other. For a wiki with N pages and M entities per page, a naive O(N²) comparison quickly becomes intractable (10,000 pages = 50M comparisons). The tool needs to run interactively during agent sessions where latency matters.
- **Decision:** An `InvertedIndex` dataclass with dual maps is used: `entity_to_pages` maps an entity name to the set of page stems that mention it, and `page_to_entities` maps each page stem to the entities it mentions. Building the index is O(N × M) — one pass through every page extracting entities. Querying "which pages mention entity X but don't link to the page about X" is O(1) — a set lookup minus existing wikilinks. The `--apply` flag auto-adds suggested `[[wikilinks]]` to pages. Entity extraction draws from frontmatter titles, H2/H3 headings, and bolded text.
- **Consequences:** Easier: suggestions are instant even on large wikis. The dual-map structure also enables "find orphan pages" queries trivially. Harder: the index is memory-resident and rebuilt on every run — no persistence. Entity extraction is heuristic (headings + bold text) and misses implicit references. Case sensitivity in entity matching can cause missed suggestions.
