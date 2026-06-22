// MCP Server — Graph Bridge
// Bridges to graph-engine (Node.js CLI) for graph operations.

import { execFile } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import type { GraphNode, GraphEdge } from "./types.js";
import { fileExists, ensureDir } from "./wiki-fs.js";

const execFileAsync = promisify(execFile);

// Monorepo root is the parent of the mcp-server/ directory
const MONOREPO_ROOT = path.resolve(process.cwd(), "..");

/** Path to the graph-engine CLI entry point */
function graphEnginePath(): string {
  return path.resolve(
    MONOREPO_ROOT,
    "graph-engine",
    "dist",
    "index.js",
  );
}

/** Where graph-data.json is cached (inside the wiki root) */
function graphDataPath(wikiPath: string): string {
  return path.join(wikiPath, "graph-data.json");
}

// ---------------------------------------------------------------------------
// Types returned by graph-engine CLI (JSON on stdout)
// ---------------------------------------------------------------------------

interface GraphEngineBuildResult {
  nodes: GraphEngineNode[];
  edges: GraphEngineEdge[];
  communities: GraphEngineCommunity[];
}

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

interface GraphEngineCommunity {
  id: number;
  nodeCount: number;
  cohesion: number;
  topNodes: string[];
}

interface GraphEngineInsights {
  surprisingConnections: Array<{
    source: GraphEngineNode;
    target: GraphEngineNode;
    score: number;
    reasons: string[];
    key: string;
  }>;
  knowledgeGaps: Array<{
    type: "isolated-node" | "sparse-community" | "bridge-node";
    title: string;
    description: string;
    nodeIds: string[];
    suggestion: string;
  }>;
}

interface GraphEngineSearch {
  nodes: GraphEngineNode[];
  edges: GraphEngineEdge[];
  matchedNodeIds: string[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map graph-engine node type to the MCP server's GraphNode type */
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

/** Map graph-engine edge type to the MCP server's GraphEdge type */
function toGraphEdge(e: GraphEngineEdge): GraphEdge {
  return { source: e.source, target: e.target, weight: e.weight };
}

/**
 * Call the graph-engine CLI and return parsed JSON.
 *
 * The graph-engine writes result JSON to stdout and error JSON to stderr.
 * We capture both and parse stdout on success.
 */
async function callGraphEngine(
  wikiPath: string,
  action: string,
  extraArgs: string[] = [],
): Promise<unknown> {
  const enginePath = graphEnginePath();

  const args = ["--wiki", wikiPath, "--action", action, ...extraArgs];

  try {
    const { stdout } = await execFileAsync("node", [enginePath, ...args], {
      maxBuffer: 10 * 1024 * 1024,
    });
    return JSON.parse(stdout);
  } catch (err: unknown) {
    const execErr = err as NodeJS.ErrnoException & {
      stdout?: string;
      stderr?: string;
    };

    // If stdout has JSON, try to parse it (some errors still emit JSON)
    if (execErr.stdout) {
      try {
        return JSON.parse(execErr.stdout);
      } catch {
        // Not JSON — fall through
      }
    }

    // Build a descriptive error
    const stderr = execErr.stderr?.trim() ?? "";
    const message = stderr || execErr.message || `graph-engine ${action} failed`;
    throw new Error(message);
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Build the wiki knowledge graph and cache it to graph-data.json.
 *
 * Calls: `node graph-engine/dist/index.js --wiki <path> --action build`
 *
 * The result is written to `<wikiPath>/graph-data.json` for subsequent calls.
 */
export async function buildGraph(
  wikiPath: string,
): Promise<{ nodes: GraphNode[]; edges: GraphEdge[]; communities: any[] }> {
  const raw = (await callGraphEngine(wikiPath, "build")) as GraphEngineBuildResult;

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
 * Calls: `node graph-engine/dist/index.js --wiki <path> --action insights`
 *
 * Requires graph-data.json to exist. If missing, automatically runs `buildGraph`
 * first.
 */
export async function getInsights(wikiPath: string): Promise<any> {
  const dataPath = graphDataPath(wikiPath);
  const hasData = await fileExists(dataPath);

  if (!hasData) {
    // Auto-build before fetching insights
    await buildGraph(wikiPath);
  }

  const raw = await callGraphEngine(wikiPath, "insights");
  return raw;
}

/**
 * Search the graph for nodes matching a query.
 *
 * Calls: `node graph-engine/dist/index.js --wiki <path> --action search --query <q>`
 *
 * Requires graph-data.json to exist. If missing, automatically runs `buildGraph`
 * first.
 */
export async function searchGraph(
  wikiPath: string,
  query: string,
): Promise<any> {
  const dataPath = graphDataPath(wikiPath);
  const hasData = await fileExists(dataPath);

  if (!hasData) {
    // Auto-build before searching
    await buildGraph(wikiPath);
  }

  const raw = (await callGraphEngine(wikiPath, "search", [
    "--query",
    query,
  ])) as GraphEngineSearch;

  if (!raw || typeof raw !== "object") {
    return { nodes: [], edges: [], matchedNodeIds: [] };
  }

  return {
    nodes: (raw.nodes ?? []).map(toGraphNode),
    edges: (raw.edges ?? []).map(toGraphEdge),
    matchedNodeIds: Array.from(raw.matchedNodeIds ?? []),
  };
}
