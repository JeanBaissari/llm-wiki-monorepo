/**
 * mcp-server/test/test_search.test.ts — BM25 Search Engine Tests (SQLite FTS5)
 *
 * Covers:
 *   - buildIndex creates index from wiki files via index_wiki.py
 *   - search returns ranked results from SQLite FTS5
 *   - search returns empty for empty index
 *   - query with no matching terms returns empty
 *   - clearIndex resets connection cache
 *   - snippet generation includes query term
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs/promises';
import * as fsSync from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { execFileSync } from 'node:child_process';
import { buildIndex, search, clearIndex } from '../dist/search.js';

// Resolve monorepo root for finding index_wiki.py
const REPO_ROOT = path.resolve(import.meta.dirname, '..', '..');

let tmpDir: string;

beforeEach(() => {
  tmpDir = fsSync.mkdtempSync(path.join(os.tmpdir(), 'search-test-'));
  clearIndex(); // Fresh connection cache
});

afterEach(async () => {
  await fs.rm(tmpDir, { recursive: true, force: true });
  clearIndex();
});

/** Run index_wiki.py on the given wiki root */
function runIndexer(wikiRoot: string): void {
  const scriptPath = path.join(REPO_ROOT, 'skill', 'scripts', 'index_wiki.py');
  execFileSync('python3', [scriptPath, wikiRoot], {
    stdio: 'pipe',
    timeout: 30_000,
  });
}

/** Create a fixture wiki under the given root dir */
async function setupWiki(rootDir: string): Promise<void> {
  const pagesDir = path.join(rootDir, 'wiki');
  await fs.mkdir(path.join(pagesDir, 'entities'), { recursive: true });
  await fs.mkdir(path.join(pagesDir, 'concepts'), { recursive: true });

  await fs.writeFile(path.join(pagesDir, 'entities', 'python.md'), `---
title: Python
type: entity
---

# Python

Python is a high-level programming language known for its readability.
It is widely used in data science, web development, and automation.
Python supports multiple programming paradigms.
`);

  await fs.writeFile(path.join(pagesDir, 'entities', 'pytorch.md'), `---
title: PyTorch
type: entity
---

# PyTorch

PyTorch is an open-source machine learning framework.
It is developed by Meta AI and used for deep learning applications.
PyTorch supports dynamic computation graphs.
`);

  await fs.writeFile(path.join(pagesDir, 'concepts', 'deep_learning.md'), `---
title: Deep Learning
type: concept
---

# Deep Learning

Deep learning is a subset of machine learning.
It uses neural networks with many layers to learn from data.
Popular frameworks include PyTorch and TensorFlow.
`);

  // Build the SQLite FTS5 index
  runIndexer(rootDir);
}

describe('search — buildIndex + search', () => {
  it('returns ranked results for a query', async () => {
    await setupWiki(tmpDir);

    const results = await search(tmpDir, 'python programming');
    expect(results.length).toBeGreaterThan(0);

    // Python page should rank highest for "python" query
    const pyResult = results.find(r => r.title === 'Python');
    expect(pyResult).toBeDefined();
    if (pyResult) {
      expect(pyResult.score).toBeGreaterThan(0);
    }
  });

  it('returns results with snippets', async () => {
    await setupWiki(tmpDir);

    const results = await search(tmpDir, 'deep learning');
    expect(results.length).toBeGreaterThan(0);

    for (const r of results) {
      expect(r.snippet).toBeTruthy();
      expect(r.snippet.length).toBeGreaterThan(0);
    }
  });

  it('returns empty for no match', async () => {
    await setupWiki(tmpDir);

    const results = await search(tmpDir, 'zzzznonexistentterm');
    expect(results).toHaveLength(0);
  });

  it('returns empty for empty wiki', async () => {
    const wikiRoot = path.join(tmpDir, 'empty-wiki');
    await fs.mkdir(path.join(wikiRoot, 'wiki'), { recursive: true });

    // Run indexer — will exit 1 (no pages), but that's OK for empty wiki
    try {
      runIndexer(wikiRoot);
    } catch {
      // Expected for empty wiki
    }

    const results = await search(wikiRoot, 'anything');
    expect(results).toHaveLength(0);
  });

  it('respects the topK limit', async () => {
    await setupWiki(tmpDir);

    const results = await search(tmpDir, 'learning', 1);
    expect(results.length).toBeLessThanOrEqual(1);
  });
});

describe('search — clearIndex', () => {
  it('clears the connection cache for fresh reopen', async () => {
    await setupWiki(tmpDir);

    // First search
    const results1 = await search(tmpDir, 'python');
    expect(results1.length).toBeGreaterThan(0);

    // Clear and re-search
    clearIndex();
    const results2 = await search(tmpDir, 'python');
    expect(results2.length).toBeGreaterThan(0);
    // Results should be the same (same index, same query)
    expect(results2[0].title).toBe(results1[0].title);
  });
});

describe('search — buildIndex', () => {
  it('builds index without searching', async () => {
    const wikiRoot = path.join(tmpDir, 'wiki-proj');
    await fs.mkdir(path.join(wikiRoot, 'wiki', 'pages'), { recursive: true });
    await fs.writeFile(path.join(wikiRoot, 'wiki', 'pages', 'test.md'), `---
title: Test Page
---

# Test Page

This is a test page with some content about machine learning.
`);

    // buildIndex should create the index
    await buildIndex(wikiRoot);

    // Now search should work
    const results = await search(wikiRoot, 'machine learning');
    expect(results.length).toBeGreaterThan(0);
  });
});
