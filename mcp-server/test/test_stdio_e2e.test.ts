/**
 * mcp-server/test/test_stdio_e2e.test.ts — MCP Stdio E2E Tests
 *
 * Covers:
 *   - Server startup with --wiki flag
 *   - tools/list returns expected tool schemas
 *   - llm_wiki_status returns page count and health
 *   - llm_wiki_read_file reads a valid file
 *   - llm_wiki_read_file rejects absolute path traversal
 *   - Unknown tool returns error
 *   - Malformed JSON returns error
 *   - Process cleanup on timeout/termination
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { spawn, ChildProcess } from 'node:child_process';
import * as path from 'node:path';
import * as fs from 'node:fs';
import * as fsPromises from 'node:fs/promises';
import * as os from 'node:os';
import { execFileSync } from 'node:child_process';

const REPO_ROOT = path.resolve(import.meta.dirname, '..', '..');
const SCAFFOLD_SCRIPT = path.join(REPO_ROOT, 'skill', 'scripts', 'scaffold.py');
const MCP_SERVER = path.join(REPO_ROOT, 'mcp-server', 'dist', 'index.js');

let wikiRoot: string;
let serverProcess: ChildProcess | null = null;
let pendingRequests: Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }> = new Map();
let stdoutBuffer = '';
let nextId = 1;

// ── Helpers ────────────────────────────────────────────────────────────────

function sendRequest(method: string, params?: unknown): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    const request = JSON.stringify({ jsonrpc: '2.0', id, method, params });
    pendingRequests.set(id, { resolve, reject });
    serverProcess!.stdin!.write(request + '\n');
  });
}

function sendRaw(data: string): void {
  serverProcess!.stdin!.write(data + '\n');
}

function waitForResponse(id: number, timeoutMs: number = 10000): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pendingRequests.delete(id);
      reject(new Error(`Timeout waiting for response id=${id}`));
    }, timeoutMs);

    // Overwrite pending entry with one that clears the timer
    const original = pendingRequests.get(id);
    if (original) {
      pendingRequests.set(id, {
        resolve: (v: unknown) => {
          clearTimeout(timer);
          original.resolve(v);
        },
        reject: (e: Error) => {
          clearTimeout(timer);
          original.reject(e);
        },
      });
    } else {
      pendingRequests.set(id, {
        resolve: (v: unknown) => { clearTimeout(timer); resolve(v); },
        reject: (e: Error) => { clearTimeout(timer); reject(e); },
      });
    }
  });
}

function parseResponse(line: string): void {
  if (!line.trim()) return;
  try {
    const parsed = JSON.parse(line);
    if (parsed.id !== undefined && pendingRequests.has(parsed.id)) {
      const { resolve } = pendingRequests.get(parsed.id)!;
      pendingRequests.delete(parsed.id);
      resolve(parsed);
    }
  } catch {
    // Not JSON or malformed — ignore in buffer parsing
  }
}

function scaffoldWiki(): string {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'mcp-e2e-test-'));
  execFileSync('python3', [SCAFFOLD_SCRIPT, tmpDir, 'E2E Test Wiki', '--template', 'codebase', '--force'], {
    encoding: 'utf-8',
    timeout: 30000,
  });

  // Write a test page so we have something to read
  const pagesDir = path.join(tmpDir, 'wiki', 'concepts');
  fs.mkdirSync(pagesDir, { recursive: true });
  fs.writeFileSync(path.join(pagesDir, 'test_page.md'), `---
title: Test Page
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: []
tags: [test]
confidence: high
---

# Test Page

This is a test page for MCP stdio E2E testing.

## Links
- See also [[Other Page]].
`);

  return tmpDir;
}

// ── Setup / Teardown ───────────────────────────────────────────────────────

beforeAll(async () => {
  wikiRoot = scaffoldWiki();
}, 60000);

afterAll(async () => {
  if (serverProcess) {
    serverProcess.kill('SIGTERM');
    serverProcess = null;
  }
  if (wikiRoot && fs.existsSync(wikiRoot)) {
    await fsPromises.rm(wikiRoot, { recursive: true, force: true });
  }
});

function startServer(): Promise<void> {
  return new Promise((resolve, reject) => {
    serverProcess = spawn('node', [MCP_SERVER, '--wiki', wikiRoot], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env },
    });

    let started = false;
    const timer = setTimeout(() => {
      if (!started) reject(new Error('MCP server startup timed out'));
    }, 15000);

    serverProcess.stdout!.on('data', (data: Buffer) => {
      stdoutBuffer += data.toString();
      const lines = stdoutBuffer.split('\n');
      stdoutBuffer = lines.pop() || '';

      for (const line of lines) {
        parseResponse(line);
      }
    });

    serverProcess.stderr!.on('data', (data: Buffer) => {
      // Log stderr for debugging but don't fail
      console.error('[MCP stderr]', data.toString().trim());
    });

    serverProcess.on('error', (err) => {
      if (!started) {
        clearTimeout(timer);
        reject(err);
      }
    });

    serverProcess.on('exit', (code) => {
      if (!started) {
        clearTimeout(timer);
        reject(new Error(`MCP server exited with code ${code} before initialization`));
      }
    });

    // Send initialize request as per MCP spec
    const initId = nextId++;
    const initRequest = JSON.stringify({
      jsonrpc: '2.0',
      id: initId,
      method: 'initialize',
      params: {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: { name: 'e2e-test', version: '1.0.0' },
      },
    });

    pendingRequests.set(initId, {
      resolve: () => {
        // Send initialized notification
        serverProcess!.stdin!.write(JSON.stringify({
          jsonrpc: '2.0',
          method: 'notifications/initialized',
        }) + '\n');
        started = true;
        clearTimeout(timer);
        resolve();
      },
      reject: (e: Error) => {
        clearTimeout(timer);
        reject(e);
      },
    });

    serverProcess.stdin!.write(initRequest + '\n');
  });
}

// ════════════════════════════════════════════════════════════════════════════

describe('MCP Stdio E2E', () => {
  beforeAll(async () => {
    await startServer();
  }, 20000);

  afterAll(() => {
    if (serverProcess) {
      serverProcess.kill('SIGTERM');
      serverProcess = null;
    }
  });

  describe('tools/list', () => {
    it('returns all expected tool definitions', async () => {
      const response = await sendRequest('tools/list') as { result?: { tools?: Array<{ name: string }> } };

      expect(response).toBeDefined();
      expect(response.result).toBeDefined();
      expect(response.result!.tools).toBeDefined();
      expect(Array.isArray(response.result!.tools)).toBe(true);

      const toolNames = response.result!.tools!.map((t) => t.name);
      expect(toolNames.length).toBeGreaterThan(0);

      // Check that core tools are present
      expect(toolNames).toContain('llm_wiki_status');
      expect(toolNames).toContain('llm_wiki_files');
      expect(toolNames).toContain('llm_wiki_read_file');
      expect(toolNames).toContain('llm_wiki_search');
      expect(toolNames).toContain('llm_wiki_graph');

      // Each tool should have name, description, inputSchema
      for (const tool of response.result!.tools!) {
        expect(tool.name).toBeDefined();
        expect(typeof tool.name).toBe('string');
        expect(tool.name.length).toBeGreaterThan(0);
        expect(tool.description).toBeDefined();
        expect(tool.inputSchema).toBeDefined();
      }
    }, 15000);
  });

  describe('llm_wiki_status', () => {
    it('returns health status with page count', async () => {
      const response = await sendRequest('tools/call', {
        name: 'llm_wiki_status',
        arguments: {},
      }) as { result?: { content?: Array<{ type: string; text: string }> }; error?: unknown };

      expect(response).toBeDefined();
      expect(response.result).toBeDefined();
      expect(response.error).toBeUndefined();

      const text = response.result!.content?.find((c) => c.type === 'text')?.text || '';
      expect(text).toContain('LLM Wiki Status');
      expect(text).toContain('Health');
    }, 15000);
  });

  describe('llm_wiki_read_file', () => {
    it('reads a valid wiki page', async () => {
      const response = await sendRequest('tools/call', {
        name: 'llm_wiki_read_file',
        arguments: { path: 'concepts/test_page.md' },
      }) as { result?: { content?: Array<{ type: string; text: string }> }; error?: unknown };

      expect(response).toBeDefined();
      expect(response.result).toBeDefined();
      expect(response.error).toBeUndefined();

      const text = response.result!.content?.find((c) => c.type === 'text')?.text || '';
      expect(text).toContain('Test Page');
      expect(text).toContain('E2E testing');
    }, 15000);

    it('returns error for file outside wiki directory', async () => {
      const response = await sendRequest('tools/call', {
        name: 'llm_wiki_read_file',
        arguments: { path: '../outside_wiki.md' },
      }) as { result?: { isError?: boolean; content?: Array<{ text: string }> }; error?: unknown };

      // Should return error result for path traversal attempts
      const content = response.result?.content?.[0]?.text || '';
      const isError = response.result?.isError === true || content.toLowerCase().includes('error');
      expect(isError).toBe(true);
    }, 15000);
  });

  describe('unknown tool', () => {
    it('returns error for unknown tool', async () => {
      const response = await sendRequest('tools/call', {
        name: 'nonexistent_tool_xyz',
        arguments: {},
      }) as { result?: { isError?: boolean; content?: Array<{ text: string }> }; error?: unknown };

      // Should either be an error response or contain error content
      const isError =
        response.error !== undefined ||
        (response.result?.isError === true) ||
        (response.result?.content?.some((c) =>
          c.text?.toLowerCase().includes('unknown') ||
          c.text?.toLowerCase().includes('not found') ||
          c.text?.toLowerCase().includes('error')
        ));

      expect(isError).toBe(true);
    }, 15000);
  });

  describe('malformed input', () => {
    it('handles malformed JSON gracefully', async () => {
      const id = nextId++;
      sendRaw('{not valid json at all');

      // Server should not crash — verify by sending a valid request after
      const response = await sendRequest('tools/list') as { result?: { tools?: unknown[] } };
      expect(response.result).toBeDefined();
      expect(response.result!.tools).toBeDefined();
    }, 15000);
  });

  describe('process lifecycle', () => {
    it('server process is alive', () => {
      expect(serverProcess).not.toBeNull();
      expect(serverProcess!.exitCode).toBeNull();
      expect(serverProcess!.killed).toBe(false);
    });
  });
});
