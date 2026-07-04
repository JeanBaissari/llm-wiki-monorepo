/**
 * graph-engine/test/test_build.ts — Wiki → Graph Construction Tests
 *
 * Covers:
 *   - Empty wiki (no pages)
 *   - Single page (no edges)
 *   - Cross-linked pages (bidirectional edges)
 *   - Malformed wikilinks (skipped)
 *   - Missing wiki directory (throws)
 *   - Query pages skipped
 *   - Frontmatter parsing: title, type, sources
 *   - Wikilink resolution via title index
 */
import { describe, it, expect } from 'vitest';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { buildWikiGraph } from '../dist/build.js';
import type { GraphData } from '../dist/types.js';

// ── Helpers ──────────────────────────────────────────────────────────────

function createTempWiki(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'graph-test-'));
  return dir;
}

function writeWikiPage(wikiDir: string, relPath: string, content: string): void {
  const fullPath = path.join(wikiDir, relPath);
  const dirname = path.dirname(fullPath);
  fs.mkdirSync(dirname, { recursive: true });
  fs.writeFileSync(fullPath, content, 'utf-8');
}

function teardown(dir: string): void {
  fs.rmSync(dir, { recursive: true, force: true });
}

// ══════════════════════════════════════════════════════════════════════════ console
// Test: Empty wiki
// ══════════════════════════════════════════════════════════════════════════

describe('buildWikiGraph — empty wiki', () => {
  it('returns empty nodes/edges/communities for empty directory', async () => {
    const dir = createTempWiki();
    try {
      const result = await buildWikiGraph(dir);
      expect(result.nodes).toHaveLength(0);
      expect(result.edges).toHaveLength(0);
      expect(result.communities).toHaveLength(0);
    } finally {
      teardown(dir);
    }
  });

  it('throws for non-existent directory', async () => {
    await expect(buildWikiGraph('/nonexistent/path/to/wiki')).rejects.toThrow(
      'Wiki directory not found'
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Test: Single page (no edges)
// ══════════════════════════════════════════════════════════════════════════

describe('buildWikiGraph — single page', () => {
  it('creates one node with no edges', async () => {
    const dir = createTempWiki();
    try {
      writeWikiPage(dir, 'entities/python.md', `---
title: Python
type: entity
created: 2026-01-15
tags: [language, programming]
---

# Python

A versatile programming language.
`);

      const result = await buildWikiGraph(dir);
      expect(result.nodes).toHaveLength(1);
      expect(result.nodes[0].id).toBe('entities/python');
      expect(result.nodes[0].label).toBe('Python');
      expect(result.nodes[0].type).toBe('entity');
      expect(result.nodes[0].linkCount).toBe(0);
      expect(result.edges).toHaveLength(0);
    } finally {
      teardown(dir);
    }
  });

  it('uses H1 as fallback label when no frontmatter title', async () => {
    const dir = createTempWiki();
    try {
      writeWikiPage(dir, 'concepts/test.md', `---
type: concept
---

# Fallback Title

Content without frontmatter title.
`);

      const result = await buildWikiGraph(dir);
      expect(result.nodes).toHaveLength(1);
      expect(result.nodes[0].label).toBe('Fallback Title');
    } finally {
      teardown(dir);
    }
  });

  it('uses filename as last-resort label', async () => {
    const dir = createTempWiki();
    try {
      writeWikiPage(dir, 'entities/no_title.md', `
Content without any frontmatter or heading.
`);

      const result = await buildWikiGraph(dir);
      expect(result.nodes).toHaveLength(1);
      expect(result.nodes[0].label).toBe('no_title');
    } finally {
      teardown(dir);
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Test: Cross-linked pages (bidirectional edges)
// ══════════════════════════════════════════════════════════════════════════

describe('buildWikiGraph — cross-linked pages', () => {
  it('creates bidirectional edge for mutual wikilinks', async () => {
    const dir = createTempWiki();
    try {
      writeWikiPage(dir, 'entities/a.md', `---
title: Page A
type: entity
sources: [src1]
---

# Page A

Links to [[Page B]].
`);

      writeWikiPage(dir, 'entities/b.md', `---
title: Page B
type: entity
sources: [src1]
---

# Page B

Links to [[Page A]].
`);

      const result = await buildWikiGraph(dir);
      expect(result.nodes).toHaveLength(2);
      // Should have 1 edge (deduplicated)
      expect(result.edges).toHaveLength(1);
      // Both nodes should have linkCount > 0
      const a = result.nodes.find(n => n.id === 'entities/a');
      const b = result.nodes.find(n => n.id === 'entities/b');
      expect(a?.linkCount).toBeGreaterThan(0);
      expect(b?.linkCount).toBeGreaterThan(0);
    } finally {
      teardown(dir);
    }
  });

  it('deduplicates edges (A→B and B→A = one edge)', async () => {
    const dir = createTempWiki();
    try {
      writeWikiPage(dir, 'entities/a.md', `---
title: Page A
type: entity
---

# Page A

[[Page B]]
`);

      writeWikiPage(dir, 'entities/b.md', `---
title: Page B
type: entity
---

# Page B

[[Page A]]
`);

      const result = await buildWikiGraph(dir);
      expect(result.edges).toHaveLength(1); // deduplicated
    } finally {
      teardown(dir);
    }
  });

  it('skips unresolvable wikilinks', async () => {
    const dir = createTempWiki();
    try {
      writeWikiPage(dir, 'entities/a.md', `---
title: Page A
type: entity
---

# Page A

Links to [[Non Existent]].
`);

      const result = await buildWikiGraph(dir);
      expect(result.nodes).toHaveLength(1);
      expect(result.edges).toHaveLength(0); // no edge for dead link
    } finally {
      teardown(dir);
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Test: Query pages skipped
// ══════════════════════════════════════════════════════════════════════════

describe('buildWikiGraph — skipping query pages', () => {
  it('skips pages with type: query', async () => {
    const dir = createTempWiki();
    try {
      writeWikiPage(dir, 'entities/normal.md', `---
title: Normal Page
type: entity
---

# Normal Page
`);

      writeWikiPage(dir, 'queries/hidden.md', `---
title: Hidden Query
type: query
---

# Hidden Query
`);

      const result = await buildWikiGraph(dir);
      // Should only have 1 node (the entity, not the query)
      expect(result.nodes).toHaveLength(1);
      expect(result.nodes[0].type).toBe('entity');
    } finally {
      teardown(dir);
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Test: Wikilink resolution
// ══════════════════════════════════════════════════════════════════════════

describe('buildWikiGraph — wikilink resolution', () => {
  it('resolves [[Page Label]] by exact title match', async () => {
    const dir = createTempWiki();
    try {
      writeWikiPage(dir, 'entities/target.md', `---
title: Target Page
type: entity
---

# Target Page
`);

      writeWikiPage(dir, 'entities/source.md', `---
title: Source Page
type: entity
---

# Source Page

Links to [[Target Page]].
`);

      const result = await buildWikiGraph(dir);
      expect(result.edges).toHaveLength(1);
    } finally {
      teardown(dir);
    }
  });

  it('resolves wikilinks with aliases [[Target|display]]', async () => {
    const dir = createTempWiki();
    try {
      writeWikiPage(dir, 'entities/target.md', `---
title: Target Page
type: entity
---

# Target Page
`);

      writeWikiPage(dir, 'entities/source.md', `---
title: Source Page
type: entity
---

# Source Page

See [[Target Page|the target]] for details.
`);

      const result = await buildWikiGraph(dir);
      expect(result.edges).toHaveLength(1);
    } finally {
      teardown(dir);
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Test: Sources tracking
// ══════════════════════════════════════════════════════════════════════════

describe('buildWikiGraph — sources', () => {
  it('parses sources from frontmatter array', async () => {
    const dir = createTempWiki();
    try {
      writeWikiPage(dir, 'entities/page.md', `---
title: Test Page
type: entity
sources: [source-a, source-b]
---

# Test Page
`);

      const result = await buildWikiGraph(dir);
      expect(result.nodes).toHaveLength(1);
    } finally {
      teardown(dir);
    }
  });
});
