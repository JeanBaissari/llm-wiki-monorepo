import fs from "node:fs";
import path from "node:path";
import type { Request, Response } from "express";
import type { ServerConfig } from "../config.js";
import { buildGraph, type GraphNode } from "./graph.js";

export interface DerivedEdge {
  source: string; // resolved wiki/<relpath> node id
  target: string;
  weight: number;
  relType: string; // similar_to | co_occurs_with
  directed: boolean;
  layer: "derived";
  provenance: Record<string, unknown>;
}

export interface DerivedGraphData {
  available: boolean;
  layer: "derived";
  nodes: GraphNode[];
  edges: DerivedEdge[];
}

const DERIVED_REL_PATH = path.join(".index", "derived-edges.json");

/**
 * Load the derived-edge layer (LWM_029 artifact) and resolve its stem-based
 * endpoints to `wiki/<relpath>` node ids present in the canonical wikilink
 * graph. Derived edges whose endpoints cannot be resolved are dropped,
 * mirroring buildGraph's unresolved-wikilink drop semantics.
 */
export function loadDerivedEdges(wikiRoot: string): { nodes: GraphNode[]; edges: DerivedEdge[] } {
  const derivedPath = path.join(wikiRoot, DERIVED_REL_PATH);
  if (!fs.existsSync(derivedPath)) return { nodes: [], edges: [] };

  let raw: { edges?: unknown[] };
  try {
    raw = JSON.parse(fs.readFileSync(derivedPath, "utf-8")) as { edges?: unknown[] };
  } catch (err) {
    throw new Error(`failed to parse ${DERIVED_REL_PATH}: ${String(err)}`);
  }

  const rawEdges = raw.edges ?? [];
  if (rawEdges.length === 0) return { nodes: [], edges: [] };

  const graph = buildGraph(wikiRoot);

  // Stem → node-id lookup mirroring buildGraph's byKey aliases.
  const byKey = new Map<string, string>();
  for (const n of graph.nodes) {
    const id = n.id; // wiki/<relpath>
    const relPath = id.replace(/^wiki\//, "").replace(/\.md$/, "");
    byKey.set(n.label, id); // stem, e.g. "Transformers"
    byKey.set(n.label.toLowerCase(), id);
    byKey.set(relPath, id);
    byKey.set(relPath.toLowerCase(), id);
  }

  const resolve = (key: string): string | null =>
    byKey.get(key) ?? byKey.get(key.replace(/\.md$/, "")) ?? byKey.get(key.toLowerCase()) ?? null;

  const edges: DerivedEdge[] = [];
  const endpointIds = new Set<string>();
  for (const e of rawEdges) {
    if (typeof e !== "object" || e === null) continue;
    const rec = e as Record<string, unknown>;
    const src = typeof rec.source === "string" ? resolve(rec.source) : null;
    const tgt = typeof rec.target === "string" ? resolve(rec.target) : null;
    if (!src || !tgt || src === tgt) continue;

    edges.push({
      source: src,
      target: tgt,
      weight: typeof rec.weight === "number" ? rec.weight : 0,
      relType: typeof rec.relType === "string" ? rec.relType : "similar_to",
      directed: rec.directed === true,
      layer: "derived",
      provenance: (rec.provenance as Record<string, unknown>) ?? {},
    });
    endpointIds.add(src);
    endpointIds.add(tgt);
  }

  const nodes = graph.nodes.filter((n) => endpointIds.has(n.id));
  return { nodes, edges };
}

export function handleDerivedGraph(cfg: ServerConfig) {
  return (_req: Request, res: Response) => {
    try {
      const { nodes, edges } = loadDerivedEdges(cfg.wikiRoot);
      res.json({
        available: edges.length > 0,
        layer: "derived",
        nodes,
        edges,
      } satisfies DerivedGraphData);
    } catch (err) {
      res.status(500).json({
        error: "Failed to load derived edges",
        detail: String(err),
      });
    }
  };
}
