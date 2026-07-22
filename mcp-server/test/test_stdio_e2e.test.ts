import { describe, it, expect, beforeAll, afterAll } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import * as os from "node:os";
import { spawn, type ChildProcess } from "node:child_process";

// ── Helpers ──────────────────────────────────────────────────────────────

function createTempWiki(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "mcp-e2e-"));
  fs.mkdirSync(path.join(dir, "wiki"), { recursive: true });
  fs.writeFileSync(
    path.join(dir, "wiki", "index.md"),
    `---
title: Home
type: overview
---

# Home

Welcome to the test wiki.
`,
    "utf-8",
  );
  fs.writeFileSync(
    path.join(dir, "wiki", "test-page.md"),
    `---
title: Test Page
type: concept
---

# Test Page

A test page with [[Home]] link.
`,
    "utf-8",
  );
  fs.writeFileSync(path.join(dir, "PURPOSE.md"), "# Test Wiki\n\nFor E2E testing.\n", "utf-8");
  fs.writeFileSync(path.join(dir, "CLAUDE.md"), "# Agent Instructions\n\nTest.\n", "utf-8");
  return dir;
}

function sendRequest(proc: ChildProcess, request: unknown): Promise<any> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("Response timeout")), 10000);

    let buffer = "";
    const onData = (chunk: Buffer) => {
      buffer += chunk.toString();
      try {
        const result = JSON.parse(buffer);
        clearTimeout(timeout);
        proc.stdout?.removeListener("data", onData);
        resolve(result);
      } catch {
        // incomplete JSON — keep buffering
      }
    };

    proc.stdout?.on("data", onData);
    proc.stdin?.write(JSON.stringify(request) + "\n");
  });
}

// ── Server lifecycle ─────────────────────────────────────────────────────

let wikiDir: string;
let server: ChildProcess;

beforeAll(async () => {
  wikiDir = createTempWiki();

  // Resolve mcp-server dist/index.js
  const serverPath = path.resolve(__dirname, "..", "dist", "index.js");

  server = spawn("node", [serverPath, "--wiki", wikiDir], {
    stdio: ["pipe", "pipe", "pipe"],
    env: { ...process.env },
  });

  // Collect stderr for debugging
  server.stderr?.on("data", () => {});

  // Wait for server to be ready
  await new Promise<void>((resolve) => setTimeout(resolve, 1500));
});

afterAll(() => {
  if (server && !server.killed) {
    server.kill("SIGTERM");
  }
  if (wikiDir) {
    fs.rmSync(wikiDir, { recursive: true, force: true });
  }
});

// ══════════════════════════════════════════════════════════════════════════
// Tests
// ══════════════════════════════════════════════════════════════════════════

describe("MCP stdio E2E", () => {
  it("tools/list returns tool definitions with side-effect metadata", async () => {
    const response = await sendRequest(server, {
      jsonrpc: "2.0",
      id: 1,
      method: "tools/list",
    });

    expect(response.jsonrpc).toBe("2.0");
    expect(response.id).toBe(1);
    expect(response.result).toBeDefined();
    expect(response.result.tools).toBeInstanceOf(Array);

    const tools = response.result.tools as Array<{ name: string; description: string }>;
    expect(tools.length).toBeGreaterThan(0);

    // Check that side-effect metadata is present
    for (const tool of tools) {
      expect(tool.description).toMatch(/\[side_effect:/);
    }

    // Verify known tool names
    const names = tools.map((t) => t.name);
    expect(names).toContain("llm_wiki_status");
    expect(names).toContain("llm_wiki_read_file");
    expect(names).toContain("llm_wiki_graph_build");
    expect(names).toContain("llm_wiki_backup");
  });

  it("llm_wiki_status succeeds", async () => {
    const response = await sendRequest(server, {
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: {
        name: "llm_wiki_status",
        arguments: {},
      },
    });

    expect(response.jsonrpc).toBe("2.0");
    expect(response.id).toBe(2);
    expect(response.result).toBeDefined();
    expect(response.result.isError).toBeFalsy();
    const text = response.result.content[0].text;
    expect(text).toContain("LLM Wiki Status");
    expect(text).toContain("Page Count");
  });

  it("llm_wiki_read_file succeeds for valid project-relative path", async () => {
    const response = await sendRequest(server, {
      jsonrpc: "2.0",
      id: 3,
      method: "tools/call",
      params: {
        name: "llm_wiki_read_file",
        arguments: { path: "PURPOSE.md" },
      },
    });

    expect(response.result).toBeDefined();
    expect(response.result.isError).toBeFalsy();
    const text = response.result.content[0].text;
    expect(text).toContain("Test Wiki");
  });

  it("llm_wiki_read_file rejects absolute path", async () => {
    const response = await sendRequest(server, {
      jsonrpc: "2.0",
      id: 4,
      method: "tools/call",
      params: {
        name: "llm_wiki_read_file",
        arguments: { path: "/etc/passwd" },
      },
    });

    expect(response.result).toBeDefined();
    expect(response.result.isError).toBe(true);
    const text = response.result.content[0].text;
    expect(text).toContain("Absolute paths are not allowed");
  });

  it("llm_wiki_read_file rejects path escaping project root", async () => {
    const response = await sendRequest(server, {
      jsonrpc: "2.0",
      id: 5,
      method: "tools/call",
      params: {
        name: "llm_wiki_read_file",
        arguments: { path: "../outside" },
      },
    });

    expect(response.result).toBeDefined();
    // Should either reject traversal or reject the non-allow-listed path
    const text = response.result.content[0].text;
    expect(response.result.isError).toBe(true);
  });

  it("unknown tool returns error", async () => {
    const response = await sendRequest(server, {
      jsonrpc: "2.0",
      id: 6,
      method: "tools/call",
      params: {
        name: "nonexistent_tool",
        arguments: {},
      },
    });

    expect(response.result).toBeDefined();
    expect(response.result.isError).toBe(true);
    const text = response.result.content[0].text;
    expect(text).toContain("Unknown tool");
  });
});
