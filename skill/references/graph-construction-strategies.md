# Knowledge Graph Construction Strategies

When pairing LLM-wiki with graphify, the full pipeline (detection → AST extraction → semantic extraction → clustering → labeling → HTML/JSON) can be impractical for large codebases. This reference covers when and how to pivot.

## When Full Graphify Pipeline Is Appropriate

- Codebase under 500 files, under 500K words
- Heavy documentation with deep cross-references that need semantic extraction
- Single-use deep analysis (not recurring cron)
- The graphify CLI or Node.js API is stable and API keys are configured

## When Full Pipeline Is Impractical

- **Massive codebases** (1,500+ files, 7M+ words) — detection alone takes minutes, semantic extraction would consume enormous token budgets
- **Graphify API instability** — `extract()` return values change between versions, CLI flags shift, Node module resolution fails in subdirectories
- **Documentation is the primary value** — when the code structure matters less than the doc content (strategy docs, research papers, architecture specs), the code graph adds noise not signal

## The Fallback: Wiki Cross-Reference Graph

Instead of running graphify on the full codebase, build the knowledge graph directly from wiki page [[wikilinks]]:

```python
import json, os, re

wiki_dir = 'wiki/'
nodes, links = [], []

for subdir, ptype in [('entities', 'entity'), ('concepts', 'concept')]:
    for f in os.listdir(os.path.join(wiki_dir, subdir)):
        if not f.endswith('.md'): continue
        content = open(os.path.join(wiki_dir, subdir, f)).read()
        title = re.search(r'^# (.+)', content, re.MULTILINE).group(1)
        nid = f"{ptype}:{f.replace('.md','')}"
        nodes.append({"id": nid, "label": title, "type": ptype, "source_file": f"{subdir}/{f}"})
        for m in re.finditer(r'\[\[([^\]]+)\]\]', content):
            tid = f"entity:{m.group(1).lower().replace('/','-').replace(' ','-')}"
            links.append({"source": nid, "target": tid, "relation": "references", "confidence": "EXTRACTED"})

# Add tag nodes from frontmatter
# Generate GRAPH_REPORT.md with god nodes, community structure, surprising connections
```

**Advantages:**
- Instant construction (no LLM tokens, no API calls, no Node.js dependency issues)
- Graph exactly mirrors wiki structure — every node and edge corresponds to a written page
- Perfect for cron-based EOW refreshes (fast, deterministic, re-runnable)
- GRAPH_REPORT.md provides the same god-nodes/surprises/communities output as graphify

**Disadvantages:**
- Misses code-only relationships (imports, function calls, module dependencies)
- No automatic discovery of undocumented concepts
- Page quality depends on manual wiki curation first

## Hybrid Approach

For repos that need BOTH:
1. Build wiki pages first (manual or subagent-driven) — establishes the knowledge layer
2. Run graphify AST-only on the code: `extract('.', {mode: 'ast'})` — captures code structure
3. Merge: code nodes get wiki-documented labels, wiki pages get code-structure edges
4. Run graphify clustering on the merged graph

This gives you the best of both without the token cost of full semantic extraction.
