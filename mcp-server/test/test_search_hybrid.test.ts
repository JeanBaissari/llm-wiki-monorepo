/**
 * mcp-server/test/test_search_hybrid.test.ts — MCP llm_wiki_search hybrid-default path
 *
 * LWM_032 / ADR-0020 (AD-16): hybrid became the default for llm_wiki_search in
 * v0.5.0. These tests cover the MCP layer that the old test_search.test.ts
 * (keyword engine only) never exercised:
 *
 *   1. default mode=hybrid → sidecar.call("hybrid_search", ...) is invoked and
 *      results are formatted with the `_[matched]_` provenance tag header
 *   2. mode="keyword" → sidecar is NOT invoked (escape hatch)
 *   3. sidecar unavailable (null / not running / call error) → graceful
 *      fallthrough to the keyword path
 *
 * The sidecar is a pure stub (no real process). The sanctioned hybrid output is
 * additionally frozen as a committed content snapshot corpus (LWM_025):
 * test/fixtures/hybrid-search.snapshot.txt is asserted by string equality at
 * the bottom of this file, and the LWM_032 AC#4 sanctioned diff (exact hybrid
 * header + matched tag) is asserted inline below.
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs/promises';
import * as fsSync from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { execFileSync } from 'node:child_process';
import { setConfig } from '../dist/projects/config.js';
import { discoverLayout } from '../dist/projects/discover.js';
import { setSidecar } from '../dist/registry.js';
import type { PythonSidecar } from '../dist/adapters/sidecar.js';
import { handleSearch } from '../dist/tools/search.js';
import { clearIndex } from '../dist/search.js';

const REPO_ROOT = path.resolve(import.meta.dirname, '..', '..');

// LWM_025: the sanctioned hybrid-search output snapshot — the frozen contract.
// Any change to the formatting in tools/search.ts (header, matched tag, path,
// snippet lines) breaks this test until the corpus is intentionally bumped.
const HYBRID_SNAPSHOT = path.join(
  import.meta.dirname, 'fixtures', 'hybrid-search.snapshot.txt');

interface SidecarCall {
  method: string;
  params: Record<string, unknown>;
}

interface SidecarStub {
  running: boolean;
  result: unknown;
  error: Error | null;
  calls: SidecarCall[];
  isRunning(): boolean;
  call(method: string, params: Record<string, unknown>): Promise<unknown>;
}

function makeStub(
  opts: { running?: boolean; result?: unknown; error?: Error | null } = {},
): SidecarStub {
  return {
    running: opts.running ?? true,
    result: opts.result,
    error: opts.error ?? null,
    calls: [],
    isRunning() {
      return this.running;
    },
    async call(method: string, params: Record<string, unknown>): Promise<unknown> {
      this.calls.push({ method, params });
      if (this.error) throw this.error;
      return this.result;
    },
  };
}

let tmpDir: string;

beforeEach(async () => {
  tmpDir = fsSync.mkdtempSync(path.join(os.tmpdir(), 'search-hybrid-test-'));
  clearIndex();
  setSidecar(null);
});

afterEach(async () => {
  setSidecar(null);
  clearIndex();
  await fs.rm(tmpDir, { recursive: true, force: true });
});

/** Build a small real wiki (pages + FTS5 index) so the keyword path works. */
async function setupWiki(rootDir: string): Promise<void> {
  const pagesDir = path.join(rootDir, 'wiki', 'concepts');
  await fs.mkdir(pagesDir, { recursive: true });
  await fs.writeFile(path.join(pagesDir, 'python.md'), `---
title: Python
type: concept
---

# Python

Python is a high-level programming language used in data science.
`);
  await fs.writeFile(path.join(pagesDir, 'transformer.md'), `---
title: Transformer
type: concept
---

# Transformer

The transformer uses attention over sequences.
`);
  execFileSync('python3', [path.join(REPO_ROOT, 'skill', 'scripts', 'index_wiki.py'), rootDir], {
    stdio: 'pipe',
    timeout: 30_000,
  });
}

function registerProject(rootDir: string): void {
  setConfig({
    projects: new Map([['default', { root: rootDir, layout: discoverLayout(rootDir) }]]),
    defaultProject: 'default',
  });
}

describe('llm_wiki_search — hybrid default (LWM_032/ADR-0020)', () => {
  it('mode omitted → sidecar hybrid_search invoked; _[matched]_ tag formatted', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({
      result: {
        results: [
          { path: 'wiki/concepts/transformer.md', title: 'Transformer',
            snippet: 'The transformer uses attention over sequences.', matched: 'vector' },
          { path: 'wiki/concepts/python.md', title: 'Python',
            snippet: 'Python is a high-level language.', matched: 'both' },
        ],
      },
    });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleSearch({ query: 'attention sequences', top_k: 5 });

    expect(res.isError).toBeFalsy();
    const text = res.content[0].text;
    // Exact hybrid header (the sanctioned default-flip output, LWM_032 AC#4).
    expect(text).toContain('# Hybrid Search Results for "attention sequences" (2)');
    // Matched-row header carries the _[matched]_ provenance tag.
    expect(text).toContain('### 1. Transformer _[vector]_');
    expect(text).toContain('### 2. Python _[both]_');
    expect(text).toContain('**Path:** `wiki/concepts/transformer.md`');
    expect(text).not.toContain('**Score:**'); // hybrid rows carry no BM25 score

    // The sidecar was invoked with the wiki root + query + top_k.
    expect(stub.calls).toHaveLength(1);
    expect(stub.calls[0].method).toBe('hybrid_search');
    expect(stub.calls[0].params).toMatchObject({
      wiki_root: tmpDir,
      query: 'attention sequences',
      top_k: 5,
    });
  });

  it('mode="keyword" → sidecar NOT invoked; keyword path output', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({ result: { results: [] } });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleSearch({ query: 'python', mode: 'keyword' });

    expect(stub.calls).toHaveLength(0); // escape hatch: no sidecar RPC
    const text = res.content[0].text;
    expect(text).toContain('# Search Results for "python"');
    expect(text).not.toContain('Hybrid Search Results');
    expect(text).toContain('**Score:**'); // keyword rows carry the BM25 score
    expect(text).toContain('### 1. Python');
  });

  it('sidecar null → graceful fallthrough to keyword path', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);
    // setSidecar(null) — no sidecar at all.

    const res = await handleSearch({ query: 'python' });
    const text = res.content[0].text;
    expect(text).toContain('# Search Results for "python"');
    expect(text).not.toContain('Hybrid Search Results');
  });

  it('sidecar not running → graceful fallthrough to keyword path', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({ running: false, result: { results: [] } });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleSearch({ query: 'transformer' });
    expect(stub.calls).toHaveLength(0); // never attempted
    const text = res.content[0].text;
    expect(text).toContain('# Search Results for "transformer"');
    expect(text).toContain('### 1. Transformer');
  });

  it('sidecar call error → graceful fallthrough to keyword path', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({ running: true, error: new Error('sidecar died') });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleSearch({ query: 'python' });
    expect(stub.calls).toHaveLength(1); // attempted once, then fell back
    const text = res.content[0].text;
    expect(text).toContain('# Search Results for "python"');
    expect(text).not.toContain('Hybrid Search Results');
  });

  it('hybrid empty results → "No results found" (empty-index fallthrough)', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({ result: { results: [] } });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleSearch({ query: 'zzzznonexistentqqq' });
    const text = res.content[0].text;
    expect(text).toContain('# Search Results');
    expect(text).toContain('No results found');
  });

  it('hybrid output EQUALS the committed snapshot corpus (LWM_025 frozen format)', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({
      result: {
        results: [
          { path: 'wiki/concepts/transformer.md', title: 'Transformer',
            snippet: 'The transformer uses attention over sequences.', matched: 'vector' },
          { path: 'wiki/concepts/python.md', title: 'Python',
            snippet: 'Python is a high-level language.', matched: 'both' },
        ],
      },
    });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleSearch({ query: 'attention sequences', top_k: 5 });
    expect(res.isError).toBeFalsy();
    const text = res.content[0].text;

    // String equality against the committed corpus — the frozen byte contract.
    const corpus = await fs.readFile(HYBRID_SNAPSHOT, 'utf-8');
    expect(text).toBe(corpus);
  });
});
