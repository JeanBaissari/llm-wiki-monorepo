import type { Request, Response } from "express";
import type { ServerConfig } from "../config.js";
import { buildGraph, type GraphData, type GraphNode } from "./graph.js";
import { loadDerivedEdges, type DerivedEdge } from "./derived.js";

// ── JSON Canvas 1.0 ────────────────────────────────────────────────────────

export interface JsonCanvasNode {
  id: string;
  type: string;
  label: string;
}

export interface JsonCanvasEdge {
  id: string;
  fromNode: string;
  toNode: string;
  label: string;
  color: string;
  line: "solid" | "dashed";
}

export interface JsonCanvasDocument {
  nodes: JsonCanvasNode[];
  edges: JsonCanvasEdge[];
}

export interface LayerSeparatedCanvas {
  layers: { layer: string; nodes: JsonCanvasNode[]; edges: JsonCanvasEdge[] }[];
}

const CANONICAL_COLOR = "#7f849c";
const DERIVED_COLOR = "#cba6f7";

function canvasNodes(nodes: GraphNode[]): JsonCanvasNode[] {
  return nodes.map((n) => ({ id: n.id, type: "text", label: n.label }));
}

function canvasEdges(data: GraphData, derived: DerivedEdge[]): JsonCanvasEdge[] {
  const out: JsonCanvasEdge[] = [];
  data.edges.forEach((e, i) => {
    out.push({
      id: `wikilink:e-${i}`,
      fromNode: e.source,
      toNode: e.target,
      label: "wikilink",
      color: CANONICAL_COLOR,
      line: "solid",
    });
  });
  derived.forEach((e, i) => {
    out.push({
      id: `derived:e-${i}`,
      fromNode: e.source,
      toNode: e.target,
      label: `derived · ${e.relType}`,
      color: DERIVED_COLOR,
      line: "dashed",
    });
  });
  return out;
}

export function buildJsonCanvas(
  data: GraphData,
  derived: DerivedEdge[],
  layersSeparate: boolean,
): JsonCanvasDocument | LayerSeparatedCanvas {
  if (layersSeparate) {
    const derivedEndpointIds = new Set<string>();
    for (const e of derived) {
      derivedEndpointIds.add(e.source);
      derivedEndpointIds.add(e.target);
    }
    const derivedNodes = data.nodes.filter((n) => derivedEndpointIds.has(n.id));
    return {
      layers: [
        { layer: "wikilink", nodes: canvasNodes(data.nodes), edges: canvasEdges(data, []) },
        { layer: "derived", nodes: canvasNodes(derivedNodes), edges: canvasEdges({ nodes: [], edges: [] }, derived) },
      ],
    };
  }
  return {
    nodes: canvasNodes(data.nodes),
    edges: canvasEdges(data, derived),
  };
}

// ── JSON-LD (pinned, offline-verifiable @context) ──────────────────────────

export const LLM_WIKI_CONTEXT = "https://w3id.org/llm-wiki/graph/v1";

export function buildJsonLd(
  data: GraphData,
  derived: DerivedEdge[],
  layersSeparate: boolean,
): Record<string, unknown> {
  const context = {
    "@version": 1.1,
    "llmwiki": `${LLM_WIKI_CONTEXT}#`,
    "@vocab": "llmwiki:",
  };

  const graphNode = (n: GraphNode): Record<string, unknown> => ({
    "@id": `llmwiki:node/${n.id}`,
    "@type": "Node",
    label: n.label,
    group: n.group,
    path: n.path,
    degree: n.degree,
  });

  const edgeNode = (e: DerivedEdge | { source: string; target: string }, layer: string, index: number): Record<string, unknown> => {
    const out: Record<string, unknown> = {
      "@id": `llmwiki:edge/${layer}/${index}`,
      "@type": "Edge",
      layer,
      source: `llmwiki:node/${e.source}`,
      target: `llmwiki:node/${e.target}`,
      weight: "weight" in e && typeof e.weight === "number" ? e.weight : 1,
    };
    if (layer === "derived" && "relType" in e) out.relType = e.relType;
    return out;
  };

  const canonicalEdges = data.edges.map((e, i) => edgeNode(e, "wikilink", i));
  const derivedEdgeNodes = derived.map((e, i) => edgeNode(e, "derived", i));

  const doc: Record<string, unknown> = {
    "@context": context,
    "@id": `${LLM_WIKI_CONTEXT}/graph`,
    "@type": "Graph",
    layer: layersSeparate ? "separate" : "both",
  };

  if (layersSeparate) {
    doc.layers = [
      {
        "@id": `${LLM_WIKI_CONTEXT}/layer/wikilink`,
        "@type": "Layer",
        layer: "wikilink",
        nodes: data.nodes.map(graphNode),
        edges: canonicalEdges,
      },
      {
        "@id": `${LLM_WIKI_CONTEXT}/layer/derived`,
        "@type": "Layer",
        layer: "derived",
        nodes: [],
        edges: derivedEdgeNodes,
      },
    ];
  } else {
    doc.nodes = data.nodes.map(graphNode);
    doc.edges = [...canonicalEdges, ...derivedEdgeNodes];
  }

  return doc;
}

// ── Route ──────────────────────────────────────────────────────────────────

export function handleExport(cfg: ServerConfig) {
  return (req: Request, res: Response) => {
    const format = typeof req.query.format === "string" ? req.query.format : "jsoncanvas";
    const layersSeparate = req.query.layers === "separate";

    try {
      const data = buildGraph(cfg.wikiRoot);
      const { edges: derived } = loadDerivedEdges(cfg.wikiRoot);

      if (format === "jsonld") {
        res.setHeader("Content-Type", "application/ld+json; charset=utf-8");
        res.json(buildJsonLd(data, derived, layersSeparate));
        return;
      }
      if (format === "jsoncanvas") {
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.json(buildJsonCanvas(data, derived, layersSeparate));
        return;
      }
      res.status(400).json({ error: `unsupported export format: ${format}` });
    } catch (err) {
      res.status(500).json({ error: "Failed to build graph export", detail: String(err) });
    }
  };
}
