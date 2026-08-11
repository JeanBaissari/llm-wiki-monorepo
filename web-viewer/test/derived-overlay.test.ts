import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import express from "express";
import request from "supertest";
import { fileURLToPath } from "node:url";
import path from "node:path";
import os from "node:os";
import fs from "node:fs";
import { handleGraph } from "../server/routes/graph.js";
import { handleDerivedGraph, loadDerivedEdges } from "../server/routes/derived.js";
import { renderGraph, renderDerivedOverlay, type GraphData, type DerivedOverlayData } from "../client/graph.js";
import { createSvg, serialize } from "./helpers/dom.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

let TEST_WIKI = "";
let DERIVED_DIR = "";
let DERIVED_FILE = "";
let cfg: { wikiRoot: string; port: number; host: string; author: string } = {
  wikiRoot: "",
  port: 4175,
  host: "127.0.0.1",
  author: "test",
};

function buildApp() {
  const app = express();
  app.get("/api/graph", handleGraph(cfg));
  app.get("/api/graph/derived", handleDerivedGraph(cfg));
  return app;
}

const FIXTURE = {
  version: 1,
  generator: "derived-v1",
  params: { tau: 0.8, top_m: 5 },
  edges: [
    {
      source: "index",
      target: "test",
      weight: 0.9,
      relType: "similar_to",
      directed: false,
      layer: "derived",
      provenance: { cosine: 0.9 },
    },
    {
      source: "index",
      target: "missing-page",
      weight: 0.5,
      relType: "co_occurs_with",
      directed: false,
      layer: "derived",
      provenance: { shared_sources: 1 },
    },
  ],
};

const CANONICAL: GraphData = {
  nodes: [
    { id: "wiki/index.md", label: "index", path: "wiki/index.md", group: "other", degree: 1, title: "Test Wiki" },
    { id: "wiki/concepts/test.md", label: "test", path: "wiki/concepts/test.md", group: "concepts", degree: 1, title: "Test Concept" },
  ],
  edges: [{ source: "wiki/index.md", target: "wiki/concepts/test.md" }],
};

const DERIVED: DerivedOverlayData = {
  available: true,
  layer: "derived",
  nodes: [],
  edges: [
    { source: "wiki/index.md", target: "wiki/concepts/test.md", layer: "derived", relType: "similar_to", weight: 0.9 },
  ],
};

beforeAll(() => {
  TEST_WIKI = fs.mkdtempSync(path.join(os.tmpdir(), "llm-wiki-derived-overlay-"));
  DERIVED_DIR = path.join(TEST_WIKI, ".index");
  DERIVED_FILE = path.join(DERIVED_DIR, "derived-edges.json");
  cfg = { wikiRoot: TEST_WIKI, port: 4175, host: "127.0.0.1", author: "test" };
  fs.mkdirSync(path.join(TEST_WIKI, "wiki"), { recursive: true });
  fs.mkdirSync(path.join(TEST_WIKI, "wiki", "concepts"), { recursive: true });
  fs.writeFileSync(path.join(TEST_WIKI, "wiki", "index.md"), "---\ntitle: Test Wiki\n---\n\n# Test Wiki\n");
  fs.writeFileSync(path.join(TEST_WIKI, "wiki", "concepts", "test.md"), "---\ntitle: Test Concept\n---\n\n# Test Concept\n");
});

afterEach(() => {
  fs.rmSync(DERIVED_DIR, { recursive: true, force: true });
});

afterAll(() => {
  fs.rmSync(TEST_WIKI, { recursive: true, force: true });
});

describe("derived-edge overlay — server", () => {
  it("test_overlay_off_byte_identical: /api/graph payload is identical with and without the derived file", async () => {
    fs.mkdirSync(DERIVED_DIR, { recursive: true });
    fs.writeFileSync(DERIVED_FILE, JSON.stringify(FIXTURE));
    const withLayer = await request(buildApp()).get("/api/graph");
    expect(withLayer.status).toBe(200);

    fs.rmSync(DERIVED_DIR, { recursive: true, force: true });
    const withoutLayer = await request(buildApp()).get("/api/graph");
    expect(withoutLayer.status).toBe(200);

    expect(withLayer.body).toEqual(withoutLayer.body);
  });

  it("returns available:false when the derived file is absent", async () => {
    const res = await request(buildApp()).get("/api/graph/derived");
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ available: false, layer: "derived", nodes: [], edges: [] });
  });

  it("test_overlay_on_derived_edges_distinct: derived edges present, layer=derived, stems resolved to node ids", async () => {
    fs.mkdirSync(DERIVED_DIR, { recursive: true });
    fs.writeFileSync(DERIVED_FILE, JSON.stringify(FIXTURE));

    const res = await request(buildApp()).get("/api/graph/derived");
    expect(res.status).toBe(200);
    expect(res.body.available).toBe(true);
    expect(res.body.layer).toBe("derived");
    expect(res.body.edges).toHaveLength(1);
    const e = res.body.edges[0];
    expect(e.layer).toBe("derived");
    expect(e.relType).toBe("similar_to");
    expect(e.weight).toBe(0.9);
    expect(e.source).toBe("wiki/index.md");
    expect(e.target).toBe("wiki/concepts/test.md");
    expect(e.provenance).toEqual({ cosine: 0.9 });
  });

  it("test_unresolvable_stem_dropped: stems not in the wikilink graph are dropped", async () => {
    fs.mkdirSync(DERIVED_DIR, { recursive: true });
    fs.writeFileSync(DERIVED_FILE, JSON.stringify(FIXTURE));

    const res = await request(buildApp()).get("/api/graph/derived");
    expect(res.status).toBe(200);
    const targets = res.body.edges.map((e: { target: string }) => e.target);
    expect(targets).not.toContain("missing-page");
    expect(targets).toEqual(["wiki/concepts/test.md"]);
  });

  it("loadDerivedEdges drops endpoints that resolve to the same node", () => {
    fs.mkdirSync(DERIVED_DIR, { recursive: true });
    fs.writeFileSync(
      DERIVED_FILE,
      JSON.stringify({
        version: 1,
        generator: "derived-v1",
        params: {},
        edges: [{ source: "index", target: "index", weight: 1, relType: "similar_to", directed: false, layer: "derived", provenance: {} }],
      }),
    );
    const { edges } = loadDerivedEdges(TEST_WIKI);
    expect(edges).toHaveLength(0);
  });
});

describe("derived-edge overlay — client rendering", () => {
  it("renders byte-identical DOM when disabled", () => {
    const svg1 = createSvg();
    const teardown1 = renderGraph(svg1, CANONICAL);
    const baseline = serialize(svg1);
    teardown1();

    const svg2 = createSvg();
    const teardown2 = renderDerivedOverlay(svg2, CANONICAL, DERIVED, false);
    expect(serialize(svg2)).toBe(baseline);
    expect(serialize(svg2)).not.toContain("derived-links");
    teardown2();
  });

  it("renders derived edges as a distinct dashed layer on top when enabled", () => {
    const svg = createSvg();
    const teardown = renderDerivedOverlay(svg, CANONICAL, DERIVED, true);
    const out = serialize(svg);

    expect(out).toContain("derived-links");
    expect(out).toContain("link-derived");
    // Canonical edges are untouched / still present
    expect(out).toContain("link-wikilink");
    // Canonical node rendering unchanged (node groups still present)
    expect(out).toContain("node-main");
    teardown();
  });

  it("no-ops when the derived layer is unavailable", () => {
    const svg = createSvg();
    const teardown = renderDerivedOverlay(svg, CANONICAL, null, true);
    const out = serialize(svg);
    expect(out).not.toContain("derived-links");
    expect(out).not.toContain("link-derived");
    teardown();
  });
});
