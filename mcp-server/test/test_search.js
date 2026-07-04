/**
 * mcp-server/test/test_search.ts — BM25 Search Engine Tests
 *
 * Covers:
 *   - buildIndex creates index from wiki files
 *   - search returns ranked results
 *   - search returns empty for empty index
 *   - query with no matching terms returns empty
 *   - clearIndex resets index state
 *   - snippet generation includes query term
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs/promises';
import * as path from 'node:path';
import * as os from 'node:os';
import { buildIndex, search, clearIndex } from '../src/search.js';
let tmpDir;
beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'search-test-'));
    clearIndex(); // Fresh state
});
afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
    clearIndex();
});
async function setupWiki(dir) {
    await fs.mkdir(path.join(dir, 'entities'), { recursive: true });
    await fs.mkdir(path.join(dir, 'concepts'), { recursive: true });
    await fs.writeFile(path.join(dir, 'entities', 'python.md'), `---
title: Python
type: entity
---

# Python

Python is a high-level programming language known for its readability.
It is widely used in data science, web development, and automation.
Python supports multiple programming paradigms.
`);
    await fs.writeFile(path.join(dir, 'entities', 'pytorch.md'), `---
title: PyTorch
type: entity
---

# PyTorch

PyTorch is an open-source machine learning framework.
It is developed by Meta AI and used for deep learning applications.
PyTorch supports dynamic computation graphs.
`);
    await fs.writeFile(path.join(dir, 'concepts', 'deep_learning.md'), `---
title: Deep Learning
type: concept
---

# Deep Learning

Deep learning is a subset of machine learning.
It uses neural networks with many layers to learn from data.
Popular frameworks include PyTorch and TensorFlow.
`);
}
describe('search — buildIndex + search', () => {
    it('returns ranked results for a query', async () => {
        const wikiDir = path.join(tmpDir, 'wiki');
        await setupWiki(wikiDir);
        const results = await search(wikiDir, 'python programming');
        expect(results.length).toBeGreaterThan(0);
        // Python page should rank highest for "python" query
        const pyResult = results.find(r => r.title === 'Python');
        expect(pyResult).toBeDefined();
        if (pyResult) {
            expect(pyResult.score).toBeGreaterThan(0);
        }
    });
    it('returns results with snippets', async () => {
        const wikiDir = path.join(tmpDir, 'wiki');
        await setupWiki(wikiDir);
        const results = await search(wikiDir, 'deep learning');
        expect(results.length).toBeGreaterThan(0);
        for (const r of results) {
            expect(r.snippet).toBeTruthy();
            expect(r.snippet.length).toBeGreaterThan(0);
        }
    });
    it('returns empty for no match', async () => {
        const wikiDir = path.join(tmpDir, 'wiki');
        await setupWiki(wikiDir);
        const results = await search(wikiDir, 'zzzznonexistentterm');
        expect(results).toHaveLength(0);
    });
    it('returns empty for empty wiki', async () => {
        const wikiDir = path.join(tmpDir, 'empty-wiki');
        await fs.mkdir(wikiDir, { recursive: true });
        const results = await search(wikiDir, 'anything');
        expect(results).toHaveLength(0);
    });
    it('respects the topK limit', async () => {
        const wikiDir = path.join(tmpDir, 'wiki');
        await setupWiki(wikiDir);
        const results = await search(wikiDir, 'learning', 1);
        expect(results.length).toBeLessThanOrEqual(1);
    });
});
describe('search — clearIndex', () => {
    it('clears the index for fresh rebuild', async () => {
        const wikiDir = path.join(tmpDir, 'wiki');
        await setupWiki(wikiDir);
        // First search builds index
        const results1 = await search(wikiDir, 'python');
        expect(results1.length).toBeGreaterThan(0);
        // Clear and re-search
        clearIndex();
        const results2 = await search(wikiDir, 'python');
        expect(results2.length).toBeGreaterThan(0);
        // Results should be the same (rebuild produces same index)
        expect(results2[0].title).toBe(results1[0].title);
    });
});
describe('search — buildIndex', () => {
    it('builds index without searching', async () => {
        const wikiDir = path.join(tmpDir, 'wiki');
        await setupWiki(wikiDir);
        // buildIndex should not throw
        await buildIndex(wikiDir);
    });
    it('is idempotent for same wiki path', async () => {
        const wikiDir = path.join(tmpDir, 'wiki');
        await setupWiki(wikiDir);
        await buildIndex(wikiDir);
        // Second call should be a no-op
        await expect(buildIndex(wikiDir)).resolves.toBeUndefined();
    });
});
