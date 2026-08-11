/**
 * mcp-server/test/test_ask.test.ts — MCP llm_wiki_ask tool (LWM_033 / ADR-0029)
 *
 * Mirrors test_search_hybrid.test.ts's sidecar-stub pattern:
 *   1. default → sidecar.call("ask", {wiki_root, question, top_k}) invoked and
 *      the grounded-passage output is formatted (and frozen as the committed
 *      snapshot corpus test/fixtures/ask.snapshot.txt)
 *   2. answer present → the "**Answer:**" line renders
 *   3. sidecar null / not running / RPC error / sidecar error → graceful error
 *   4. missing question → error without invoking the sidecar
 *
 * The sidecar is a pure stub (no real process). The sanctioned no_llm output is
 * additionally frozen as a committed content snapshot (string equality).
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs/promises';
import * as fsSync from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { setConfig } from '../dist/projects/config.js';
import { discoverLayout } from '../dist/projects/discover.js';
import { setSidecar } from '../dist/registry.js';
import type { PythonSidecar } from '../dist/adapters/sidecar.js';
import { handleAsk } from '../dist/tools/ask.js';

const ASK_SNAPSHOT = path.join(import.meta.dirname, 'fixtures', 'ask.snapshot.txt');

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

/** Canned sidecar result (no_llm — what the real sidecar always returns). */
function cannedAskResult(): Record<string, unknown> {
  return {
    result: {
      question: 'What is deep learning?',
      mode: 'hybrid',
      no_llm: true,
      answer: null,
      citations: ['community_ml', 'deep_learning', 'neural_network'],
      confidence: 0.9,
      faithfulness: 1.0,
      note: '',
      summary_pages: 1,
      passages: [
        { stem: 'community_ml', title: 'Machine Learning Community',
          path: 'wiki/communities/community_ml.md', type: 'community-summary',
          matched: 'both',
          excerpt: 'The machine learning community covers neural networks, deep learning, backpropagation, layers, and gradient descent.' },
        { stem: 'deep_learning', title: 'deep_learning',
          path: 'wiki/deep_learning.md', type: 'concept', matched: 'keyword',
          excerpt: 'Deep learning stacks many neural network layers.' },
        { stem: 'neural_network', title: 'neural_network',
          path: 'wiki/neural_network.md', type: 'concept', matched: 'vector',
          excerpt: 'A neural network learns weights via backpropagation.' },
      ],
    },
  };
}

let tmpDir: string;

beforeEach(async () => {
  tmpDir = fsSync.mkdtempSync(path.join(os.tmpdir(), 'ask-test-'));
  setSidecar(null);
});

afterEach(async () => {
  setSidecar(null);
  await fs.rm(tmpDir, { recursive: true, force: true });
});

async function setupWiki(rootDir: string): Promise<void> {
  const pagesDir = path.join(rootDir, 'wiki');
  await fs.mkdir(pagesDir, { recursive: true });
  await fs.writeFile(path.join(pagesDir, 'index.md'), `---
title: Test Wiki
type: index
---

# Test Wiki
`);
}

function registerProject(rootDir: string): void {
  setConfig({
    projects: new Map([['default', { root: rootDir, layout: discoverLayout(rootDir) }]]),
    defaultProject: 'default',
  });
}

describe('llm_wiki_ask (LWM_033/ADR-0029)', () => {
  it('invokes the ask sidecar RPC and formats the grounded-passage output', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({ result: cannedAskResult() });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleAsk({ question: 'What is deep learning?', top_k: 5 });

    expect(res.isError).toBeFalsy();
    const text = res.content[0].text;
    expect(text).toContain('# Ask: "What is deep learning?" (3 grounded passages, no_llm)');
    expect(text).toContain('**Answer:** (not synthesized — deterministic no_llm retrieval)');
    expect(text).toContain('**Citations:** [[community_ml]], [[deep_learning]], [[neural_network]]');
    expect(text).toContain('**Confidence:** 0.9  **Faithfulness:** 1');
    expect(text).toContain('### 1. Machine Learning Community (community_ml) _[both]_');
    expect(text).toContain('**Path:** `wiki/communities/community_ml.md`');

    expect(stub.calls).toHaveLength(1);
    expect(stub.calls[0].method).toBe('ask');
    expect(stub.calls[0].params).toMatchObject({
      wiki_root: tmpDir,
      question: 'What is deep learning?',
      top_k: 5,
    });
  });

  it('renders an LLM-provided answer when the sidecar returns one', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const result = cannedAskResult();
    (result as { result: Record<string, unknown> }).result.answer =
      'Deep learning stacks many neural network layers.';
    (result as { result: Record<string, unknown> }).result.no_llm = false;
    const stub = makeStub({ result });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleAsk({ question: 'What is deep learning?' });
    const text = res.content[0].text;
    expect(text).toContain('**Answer:** Deep learning stacks many neural network layers.');
    expect(text).toContain('# Ask: "What is deep learning?" (3 grounded passages, no_llm)');
  });

  it('renders the flat-retrieval note when the wiki has no summaries', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const result = cannedAskResult();
    (result as { result: Record<string, unknown> }).result.note =
      'no summaries yet — flat retrieval';
    (result as { result: Record<string, unknown> }).result.summary_pages = 0;
    (result as { result: Record<string, unknown> }).result.citations = ['neural_network'];
    (result as { result: Record<string, unknown> }).result.passages =
      (result as { result: Record<string, unknown> }).result.passages.slice(2);
    const stub = makeStub({ result });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleAsk({ question: 'What is deep learning?' });
    const text = res.content[0].text;
    expect(text).toContain('**Note:** no summaries yet — flat retrieval');
    expect(text).toContain('(1 grounded passages, no_llm)');
  });

  it('sidecar null → graceful error (no TS-side fallback)', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);
    // setSidecar(null) — no sidecar at all.

    const res = await handleAsk({ question: 'What is deep learning?' });
    expect(res.isError).toBe(true);
    expect(res.content[0].text).toContain('no sidecar is running');
  });

  it('sidecar not running → graceful error', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({ running: false, result: cannedAskResult() });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleAsk({ question: 'What is deep learning?' });
    expect(stub.calls).toHaveLength(0); // never attempted
    expect(res.isError).toBe(true);
    expect(res.content[0].text).toContain('no sidecar is running');
  });

  it('sidecar RPC error → graceful error', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({ running: true, error: new Error('sidecar died') });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleAsk({ question: 'What is deep learning?' });
    expect(stub.calls).toHaveLength(1);
    expect(res.isError).toBe(true);
    expect(res.content[0].text).toContain('Ask sidecar RPC failed');
  });

  it('sidecar method error result → graceful error', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({ result: { error: 'ask module not available' } });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleAsk({ question: 'What is deep learning?' });
    expect(res.isError).toBe(true);
    expect(res.content[0].text).toContain('ask module not available');
  });

  it('missing question → error without invoking the sidecar', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({ result: cannedAskResult() });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleAsk({ top_k: 5 });
    expect(stub.calls).toHaveLength(0);
    expect(res.isError).toBe(true);
    expect(res.content[0].text).toContain('Missing required argument: question');
  });

  it('ask output EQUALS the committed snapshot corpus (LWM_033 frozen format)', async () => {
    await setupWiki(tmpDir);
    registerProject(tmpDir);

    const stub = makeStub({ result: cannedAskResult() });
    setSidecar(stub as unknown as PythonSidecar);

    const res = await handleAsk({ question: 'What is deep learning?', top_k: 5 });
    expect(res.isError).toBeFalsy();
    const text = res.content[0].text;

    const corpus = await fs.readFile(ASK_SNAPSHOT, 'utf-8');
    expect(text).toBe(corpus);
  });
});
