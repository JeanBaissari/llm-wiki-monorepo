import { describe, it, expect, beforeAll, afterAll } from "vitest";
import express from "express";
import request from "supertest";
import { fileURLToPath } from "node:url";
import path from "node:path";
import os from "node:os";
import fs from "node:fs";
import { handleExport } from "../server/routes/exports.js";
import { LLM_WIKI_CONTEXT } from "../server/routes/exports.js";

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
  app.get("/api/graph/export", handleExport(cfg));
  return app;
}

beforeAll(() => {
  TEST_WIKI = fs.mkdtempSync(path.join(os.tmpdir(), "llm-wiki-exports-"));
  DERIVED_DIR = path.join(TEST_WIKI, ".index");
  DERIVED_FILE = path.join(DERIVED_DIR, "derived-edges.json");
  cfg = { wikiRoot: TEST_WIKI, port: 4175, host: "127.0.0.1", author: "test" };
  fs.mkdirSync(path.join(TEST_WIKI, "wiki", "concepts"), { recursive: true });
  fs.writeFileSync(path.join(TEST_WIKI, "wiki", "index.md"), "---\ntitle: Test Wiki\n---\n\n# Test Wiki\n");
  fs.writeFileSync(
    path.join(TEST_WIKI, "wiki", "concepts", "test.md"),
    "---\ntitle: Test Concept\n---\n\n# Test Concept\n[[index]]\n",
  );
  fs.mkdirSync(DERIVED_DIR, { recursive: true });
  fs.writeFileSync(
    DERIVED_FILE,
    JSON.stringify({
      version: 1,
      generator: "derived-v1",
      params: {},
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
      ],
    }),
  );
});

afterAll(() => {
  fs.rmSync(TEST_WIKI, { recursive: true, force: true });
});

interface CanvasEdge {
  id: string;
  fromNode: string;
  toNode: string;
  label: string;
  color: string;
  line: string;
}

function assertJsonCanvasDocument(doc: { nodes: { id: string; type: string; label: string }[]; edges: CanvasEdge[] }): void {
  const nodeIds = new Set<string>();
  for (const n of doc.nodes) {
    expect(typeof n.id).toBe("string");
    expect(typeof n.type).toBe("string");
    expect(typeof n.label).toBe("string");
    expect(nodeIds.has(n.id)).toBe(false); // ids unique
    nodeIds.add(n.id);
  }
  const edgeIds = new Set<string>();
  for (const e of doc.edges) {
    expect(typeof e.id).toBe("string");
    expect(typeof e.fromNode).toBe("string");
    expect(typeof e.toNode).toBe("string");
    expect(typeof e.label).toBe("string");
    expect(edgeIds.has(e.id)).toBe(false);
    edgeIds.add(e.id);
    // 1.0 schema: every edge endpoint must reference a node
    expect(nodeIds.has(e.fromNode)).toBe(true);
    expect(nodeIds.has(e.toNode)).toBe(true);
  }
}

describe("graph exports", () => {
  it("test_json_canvas_schema_valid: JSON Canvas 1.0 structure, both layers labeled", async () => {
    const res = await request(buildApp()).get("/api/graph/export?format=jsoncanvas");
    expect(res.status).toBe(200);
    const body = res.body as { nodes: { id: string; type: string; label: string }[]; edges: CanvasEdge[] };
    assertJsonCanvasDocument(body);

    // Node schema per JSON Canvas 1.0: id / type / label
    expect(body.nodes.every((n) => n.type === "text")).toBe(true);

    // Both layers present and labeled derived vs canonical
    const labels = body.edges.map((e) => e.label);
    expect(labels).toContain("wikilink");
    expect(labels).toContain("derived · similar_to");
    const derivedEdge = body.edges.find((e) => e.label.startsWith("derived"));
    expect(derivedEdge).toBeDefined();
    expect(derivedEdge!.line).toBe("dashed");
  });

  it("test_json_ld_context_valid: pinned @context, layer-labeled edges", async () => {
    const res = await request(buildApp()).get("/api/graph/export?format=jsonld");
    expect(res.status).toBe(200);
    expect(res.headers["content-type"]).toContain("application/ld+json");

    const body = res.body as Record<string, unknown> & {
      "@context": Record<string, unknown>;
      nodes: { "@id": string; "@type": string; label: string }[];
      edges: { "@id": string; "@type": string; layer: string; source: string; target: string; weight: number; relType?: string }[];
    };

    // Pinned, offline-verifiable @context (llmwiki prefix → llm-wiki IRI)
    expect(body["@context"]).toBeDefined();
    const ctx = body["@context"] as { llmwiki?: string };
    expect(ctx.llmwiki).toBe(`${LLM_WIKI_CONTEXT}#`);
    expect(body["@type"]).toBe("Graph");

    const layers = new Set(body.edges.map((e) => e.layer));
    expect(layers.has("wikilink")).toBe(true);
    expect(layers.has("derived")).toBe(true);

    const derived = body.edges.find((e) => e.layer === "derived")!;
    expect(derived.relType).toBe("similar_to");
    expect(derived.weight).toBe(0.9);
    const canonical = body.edges.find((e) => e.layer === "wikilink")!;
    expect(canonical.relType).toBeUndefined();

    // Every edge points at a node @id
    const nodeIds = new Set(body.nodes.map((n) => n["@id"]));
    for (const e of body.edges) {
      expect(nodeIds.has(e.source)).toBe(true);
      expect(nodeIds.has(e.target)).toBe(true);
    }
  });

  it("supports layers=separate for JSON Canvas", async () => {
    const res = await request(buildApp()).get("/api/graph/export?format=jsoncanvas&layers=separate");
    expect(res.status).toBe(200);
    const body = res.body as { layers: { layer: string; nodes: { id: string }[]; edges: CanvasEdge[] }[] };
    expect(body.layers).toHaveLength(2);
    const wikilinkLayer = body.layers.find((l) => l.layer === "wikilink")!;
    const derivedLayer = body.layers.find((l) => l.layer === "derived")!;
    expect(wikilinkLayer).toBeDefined();
    expect(derivedLayer).toBeDefined();
    assertJsonCanvasDocument({ nodes: wikilinkLayer.nodes, edges: wikilinkLayer.edges });
    assertJsonCanvasDocument({ nodes: derivedLayer.nodes, edges: derivedLayer.edges });
    expect(wikilinkLayer.edges.every((e) => e.label === "wikilink")).toBe(true);
    expect(derivedLayer.edges.every((e) => e.label.startsWith("derived"))).toBe(true);
  });

  it("supports layers=separate for JSON-LD", async () => {
    const res = await request(buildApp()).get("/api/graph/export?format=jsonld&layers=separate");
    expect(res.status).toBe(200);
    const body = res.body as { layers: { layer: string; nodes: unknown[]; edges: { layer: string }[] }[] };
    expect(body.layers).toHaveLength(2);
    const wikilinkLayer = body.layers.find((l) => l.layer === "wikilink")!;
    const derivedLayer = body.layers.find((l) => l.layer === "derived")!;
    expect(wikilinkLayer.edges.every((e) => e.layer === "wikilink")).toBe(true);
    expect(derivedLayer.edges.every((e) => e.layer === "derived")).toBe(true);
  });

  it("rejects unknown formats with 400", async () => {
    const res = await request(buildApp()).get("/api/graph/export?format=nope");
    expect(res.status).toBe(400);
    expect(res.body.error).toContain("unsupported export format");
  });

  it("defaults to jsoncanvas when format is omitted", async () => {
    const res = await request(buildApp()).get("/api/graph/export");
    expect(res.status).toBe(200);
    const body = res.body as { nodes: unknown[]; edges: unknown[] };
    expect(Array.isArray(body.nodes)).toBe(true);
    expect(Array.isArray(body.edges)).toBe(true);
  });
});
