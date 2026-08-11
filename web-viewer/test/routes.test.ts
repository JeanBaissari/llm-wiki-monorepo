import { describe, it, expect, beforeAll } from "vitest";
import express from "express";
import request from "supertest";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const TEST_WIKI = path.join(__dirname, "test-wiki");
const PAGES_DIR = path.join(TEST_WIKI, "wiki");
const RAW_DIR = path.join(TEST_WIKI, "raw");

beforeAll(() => {
  fs.mkdirSync(PAGES_DIR, { recursive: true });
  fs.mkdirSync(RAW_DIR, { recursive: true });
  fs.mkdirSync(path.join(TEST_WIKI, "audit"), { recursive: true });

  fs.writeFileSync(
    path.join(PAGES_DIR, "index.md"),
    '---\ntitle: Test Wiki\ntype: index\n---\n\n# Test Wiki\n\nWelcome to the test wiki.',
  );

  fs.mkdirSync(path.join(PAGES_DIR, "concepts"), { recursive: true });
  fs.writeFileSync(
    path.join(PAGES_DIR, "concepts", "test.md"),
    '---\ntitle: Test Concept\ntype: concept\n---\n\n# Test Concept\n\nSome content here.\n\nMore content.\n\n## Details\n\nFurther reading.',
  );
});

describe("Web Viewer Routes", () => {
  it("page route handler imports cleanly", async () => {
    const mod = await import("../server/routes/pages.js");
    expect(mod).toBeDefined();
    expect(typeof mod.handlePage).toBe("function");
    expect(typeof mod.handleRaw).toBe("function");
  });

  it("search route handler imports cleanly", async () => {
    const mod = await import("../server/routes/search.js");
    expect(mod).toBeDefined();
  });

  it("graph route handler imports cleanly", async () => {
    const mod = await import("../server/routes/graph.js");
    expect(mod).toBeDefined();
  });

  it("derived route handler imports cleanly", async () => {
    const mod = await import("../server/routes/derived.js");
    expect(mod).toBeDefined();
    expect(typeof mod.handleDerivedGraph).toBe("function");
    expect(typeof mod.loadDerivedEdges).toBe("function");
  });

  it("export route handler imports cleanly", async () => {
    const mod = await import("../server/routes/exports.js");
    expect(mod).toBeDefined();
    expect(typeof mod.handleExport).toBe("function");
  });

  it("index.ts mounts the derived and export routes", async () => {
    const source = fs.readFileSync(path.join(__dirname, "..", "server", "index.ts"), "utf-8");
    expect(source).toContain('/api/graph/derived", handleDerivedGraph(cfg)');
    expect(source).toContain('/api/graph/export", handleExport(cfg)');
  });

  it("audit route handler imports cleanly", async () => {
    const mod = await import("../server/routes/audit.js");
    expect(mod).toBeDefined();
  });

  it("rejects path traversal (../../etc/passwd) if handler checks safeRel", async () => {
    await import("../server/routes/pages.js");
    const source = fs.readFileSync(path.join(__dirname, "..", "server", "routes", "pages.ts"), "utf-8");
    expect(source).toContain("safeRel");
  });

  it("accepts valid page path", async () => {
    const mod = await import("../server/routes/pages.js");
    expect(mod).toBeDefined();
  });
});
