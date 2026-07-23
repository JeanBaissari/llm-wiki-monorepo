// MCP Server — Graph Bridge
//
// Direct imports from graph-engine library (LWM_07).
// Replaces subprocess spawn (node graph-engine/dist/cli.js) with
// in-process function calls — zero fork/exec overhead.
//
// Dynamic imports (tryImport pattern) ensure the MCP server starts
// gracefully even if graph-engine isn't built (Q3).

import { readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import type { GraphNode, GraphEdge } from "../types.js";
import { fileExists, ensureDir } from "../wiki-fs.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const _require = createRequire(import.meta.url);

// ── Graph-engine type imports (mirrors graph-engine's types) ──────────

interface GraphEngineNode {
  id: string;
  label: string;
  type: string;
  path: string;
  linkCount: number;
  community: number;
}

interface GraphEngineEdge {
  source: string;
  target: string;
  weight: number;
}

interface GraphBuildResult {
  nodes: GraphEngineNode[];
  edges: GraphEngineEdge[];
  communities: { id: number; nodeCount: number; cohesion: number; topNodes: string[] }[];
}

// ── Dynamic import helper ─────────────────────────────────────────────

async function tryImport<T>(modulePath: string): Promise<T | null> {
  try {
    return (await import(modulePath)) as T;
  } catch {
    return null;
  }
}

// ── Resolve graph-engine ──────────────────────────────────────────────

let _graphEnginePath: string | null = null;

function resolveGraphEngine(): string {
  if (_graphEnginePath) return _graphEnginePath;

  // Try workspace resolution first (npm workspaces hoist to node_modules)
  // Fall back to relative path from monorepo root
  const candidates = [
    "graph-engine",
    path.resolve(__dirname, "..", "..", "..", "graph-engine", "dist", "index.js"),
    path.resolve(process.cwd(), "..", "graph-engine", "dist", "index.js"),
  ];

  for (const candidate of candidates) {
    try {
      _require.resolve(candidate);
      _graphEnginePath = candidate;
      return candidate;
    } catch {
      // Not resolvable — try next
    }
  }

  // Last resort: relative from __dirname
  _graphEnginePath = path.resolve(__dirname, "..", "..", "..", "graph-engine", "dist", "index.js");
  return _graphEnginePath;
}

// ── Helpers ───────────────────────────────────────────────────────────

/** Where graph-data.json is cached (inside the wiki root) */
function graphDataPath(wikiPath: string): string {
  return path.join(wikiPath, "graph-data.json");
}

function toGraphNode(n: GraphEngineNode): GraphNode {
  return {
    id: n.id,
    label: n.label,
    type: n.type,
    path: n.path,
    linkCount: n.linkCount,
    community: n.community,
  };
}

function toGraphEdge(e: GraphEngineEdge): GraphEdge {
  return { source: e.source, target: e.target, weight: e.weight };
}

// ── Public API ────────────────────────────────────────────────────────

/**
 * Build the wiki knowledge graph and cache it to graph-data.json.
 *
 * Imports buildWikiGraph from graph-engine directly (LWM_07).
 * Zero subprocess — runs in-process.
 */
export async function buildGraph(
  wikiPath: string,
): Promise<{ nodes: GraphNode[]; edges: GraphEdge[]; communities: any[] }> {
  const geMod = await tryImport<{
    buildWikiGraph: (wikiPath: string) => Promise<GraphBuildResult>;
  }>(resolveGraphEngine());

  if (!geMod?.buildWikiGraph) {
    throw new Error(
      "graph-engine not available — run `npm run build` in graph-engine/",
    );
  }

  // Resolve wiki path: if the passed path contains a wiki/ subdir, use it
  const wikiSubdir = path.join(wikiPath, "wiki");
  const resolvedPath = existsSync(wikiSubdir) ? wikiSubdir : wikiPath;

  const raw = await geMod.buildWikiGraph(resolvedPath);

  const nodes = (raw.nodes ?? []).map(toGraphNode);
  const edges = (raw.edges ?? []).map(toGraphEdge);
  const communities = raw.communities ?? [];

  // Cache the result to graph-data.json inside the wiki root
  const dataPath = graphDataPath(wikiPath);
  await ensureDir(path.dirname(dataPath));
  await writeFile(
    dataPath,
    JSON.stringify({ nodes, edges, communities }, null, 2),
    "utf-8",
  );

  return { nodes, edges, communities };
}

/**
 * Get insights (surprising connections & knowledge gaps) for a wiki.
 *
 * Imports findSurprisingConnections and detectKnowledgeGaps directly
 * from graph-engine (LWM_07). Requires graph-data.json to exist.
 * If missing, automatically runs buildGraph first.
 */
export async function getInsights(wikiPath: string): Promise<{
  surprisingConnections: Array<{
    source: any; target: any; score: number; reasons: string[]; key: string;
  }>;
  knowledgeGaps: Array<{
    type: string; title: string; description: string;
    nodeIds: string[]; suggestion: string;
  }>;
}> {
  const dataPath = graphDataPath(wikiPath);
  const hasData = await fileExists(dataPath);

  if (!hasData) {
    await buildGraph(wikiPath);
  }

  // Load cached graph data
  const raw = await readFile(dataPath, "utf-8");
  const graphData = JSON.parse(raw) as {
    nodes: GraphEngineNode[];
    edges: GraphEngineEdge[];
    communities: any[];
  };

  const geMod = await tryImport<{
    findSurprisingConnections: (
      nodes: GraphEngineNode[],
      edges: GraphEngineEdge[],
      communities: any[],
    ) => any[];
    detectKnowledgeGaps: (
      nodes: GraphEngineNode[],
      edges: GraphEngineEdge[],
      communities: any[],
    ) => any[];
  }>(resolveGraphEngine());

  if (!geMod?.findSurprisingConnections || !geMod?.detectKnowledgeGaps) {
    throw new Error(
      "graph-engine insights not available — run `npm run build` in graph-engine/",
    );
  }

  return {
    surprisingConnections: geMod.findSurprisingConnections(
      graphData.nodes,
      graphData.edges,
      graphData.communities,
    ),
    knowledgeGaps: geMod.detectKnowledgeGaps(
      graphData.nodes,
      graphData.edges,
      graphData.communities,
    ),
  };
}

/**
 * Search the graph for nodes matching a query.
 *
 * Imports applyGraphSearch directly from graph-engine (LWM_07).
 * Requires graph-data.json to exist. If missing, auto-builds first.
 */
export async function searchGraph(
  wikiPath: string,
  query: string,
): Promise<{
  nodes: GraphNode[];
  edges: GraphEdge[];
  matchedNodeIds: string[];
}> {
  const dataPath = graphDataPath(wikiPath);
  const hasData = await fileExists(dataPath);

  if (!hasData) {
    await buildGraph(wikiPath);
  }

  const raw = await readFile(dataPath, "utf-8");
  const graphData = JSON.parse(raw) as {
    nodes: GraphEngineNode[];
    edges: GraphEngineEdge[];
  };

  const geMod = await tryImport<{
    applyGraphSearch: (
      nodes: GraphEngineNode[],
      edges: GraphEngineEdge[],
      query: string,
    ) => { nodes: GraphEngineNode[]; edges: GraphEngineEdge[]; matchedNodeIds: Set<string> };
  }>(resolveGraphEngine());

  if (!geMod?.applyGraphSearch) {
    throw new Error(
      "graph-engine search not available — run `npm run build` in graph-engine/",
    );
  }

  const result = geMod.applyGraphSearch(graphData.nodes, graphData.edges, query);

  return {
    nodes: (result.nodes ?? []).map(toGraphNode),
    edges: (result.edges ?? []).map(toGraphEdge),
    matchedNodeIds: Array.from(result.matchedNodeIds ?? []),
  };
}
