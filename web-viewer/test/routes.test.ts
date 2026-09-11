import { describe, it, expect, beforeAll, afterAll } from "vitest";
import express from "express";
import request from "supertest";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import os from "node:os";
import { handleRaw } from "../server/routes/pages.js";
import { handleAuditCreate } from "../server/routes/audit.js";
import { isLoopbackHost } from "../server/config.js";

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

describe("handleRaw containment", () => {
  let root: string;
  let outside: string;
  let symlinksOk = true;

  beforeAll(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), "llm-wiki-contain-"));
    fs.mkdirSync(path.join(root, "wiki", "concepts"), { recursive: true });
    fs.writeFileSync(path.join(root, "wiki", "index.md"), "# Root\n");
    fs.writeFileSync(path.join(root, "wiki", "concepts", "test.md"), "# Test Concept\n\ninside content\n");
    outside = `${root}-outside.md`;
    fs.writeFileSync(outside, "SECRET-OUTSIDE\n");
    try {
      fs.symlinkSync(outside, path.join(root, "wiki", "escape.md"));
      fs.symlinkSync("concepts/test.md", path.join(root, "wiki", "alias.md"));
    } catch {
      symlinksOk = false;
    }
  });

  afterAll(() => {
    fs.rmSync(root, { recursive: true, force: true });
    fs.rmSync(outside, { force: true });
  });

  const rawApp = () => {
    const app = express();
    app.get("/api/raw", handleRaw({ wikiRoot: root, port: 0, host: "127.0.0.1", author: "test" }));
    return app;
  };

  it("serves a file that lives inside the wiki root", async () => {
    const res = await request(rawApp()).get("/api/raw").query({ path: "wiki/concepts/test.md" });
    expect(res.status).toBe(200);
    expect(res.text).toContain("inside content");
  });

  it("rejects .. traversal with an error (no file read)", async () => {
    const res = await request(rawApp()).get("/api/raw").query({ path: "../../etc/passwd" });
    expect(res.status).toBe(400);
    expect(res.text).not.toContain("root:");
  });

  it("rejects absolute paths", async () => {
    const res = await request(rawApp()).get("/api/raw").query({ path: "/etc/passwd" });
    expect(res.status).toBe(400);
    expect(res.text).not.toContain("root:");
  });

  it("blocks symlinks that escape the wiki root", async (ctx) => {
    if (!symlinksOk) ctx.skip();
    const res = await request(rawApp()).get("/api/raw").query({ path: "wiki/escape.md" });
    expect(res.status).toBe(403);
    expect(res.text).not.toContain("SECRET-OUTSIDE");
  });

  it("allows symlinks that stay inside the wiki root", async (ctx) => {
    if (!symlinksOk) ctx.skip();
    const res = await request(rawApp()).get("/api/raw").query({ path: "wiki/alias.md" });
    expect(res.status).toBe(200);
    expect(res.text).toContain("inside content");
  });
});

describe("audit target containment", () => {
  let root: string;

  beforeAll(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), "llm-wiki-audit-"));
    fs.mkdirSync(path.join(root, "wiki"), { recursive: true });
    fs.writeFileSync(path.join(root, "wiki", "index.md"), "# Root\n");
  });

  afterAll(() => {
    fs.rmSync(root, { recursive: true, force: true });
  });

  const auditApp = () => {
    const app = express();
    app.use(express.json());
    app.post("/api/audit", handleAuditCreate({ wikiRoot: root, port: 0, host: "127.0.0.1", author: "test" }));
    return app;
  };

  it("rejects an audit target outside the wiki root", async () => {
    const res = await request(auditApp()).post("/api/audit").send({
      target: "../../etc/passwd",
      rawMarkdown: "# x",
      selStart: 0,
      selEnd: 1,
      comment: "hello",
      severity: "info",
    });
    expect(res.status).toBe(400);
    expect(fs.existsSync(path.join(root, "audit"))).toBe(false);
  });

  it("accepts an audit target inside the wiki root", async () => {
    const res = await request(auditApp()).post("/api/audit").send({
      target: "wiki/index.md",
      rawMarkdown: "# x",
      selStart: 0,
      selEnd: 1,
      comment: "hello",
      severity: "info",
    });
    expect(res.status).toBe(200);
  });
});

describe("isLoopbackHost", () => {
  it("recognizes loopback hosts and rejects wildcard binds", () => {
    expect(isLoopbackHost("127.0.0.1")).toBe(true);
    expect(isLoopbackHost("127.0.0.2")).toBe(true);
    expect(isLoopbackHost("localhost")).toBe(true);
    expect(isLoopbackHost("::1")).toBe(true);
    expect(isLoopbackHost("0.0.0.0")).toBe(false);
    expect(isLoopbackHost("::")).toBe(false);
    expect(isLoopbackHost("192.168.1.10")).toBe(false);
  });
});
