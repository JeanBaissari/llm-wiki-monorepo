// ============================================================
// graph-bridge/src/semantic-edges.ts — Semantic relationship extraction
// ============================================================
//
// Derives higher-level relationships from raw AST nodes and edges.
// Operates on CodeNode[]/CodeEdge[] already produced by ast-parser.ts.
// ============================================================

import type { CodeNode, CodeEdge } from "./types.js";

// ── Types ───────────────────────────────────────────────────

export interface SemanticEdgesOptions {
  /** When true, infer cross-file "references" edges for matching labels */
  crossFileReferences?: boolean;
  /** Minimum weight threshold for including an edge */
  minWeight?: number;
}

export interface SemanticEdgesResult {
  /** Original edges + newly inferred edges */
  edges: CodeEdge[];
  /** Statistics about what was added */
  added: {
    callChains: number;
    classHierarchies: number;
    crossReferences: number;
  };
}

// ── Graph helpers ───────────────────────────────────────────

function buildNodeMap(nodes: CodeNode[]): Map<string, CodeNode> {
  const map = new Map<string, CodeNode>();
  for (const n of nodes) map.set(n.id, n);
  return map;
}

function buildEdgeIndex(edges: CodeEdge[]): Set<string> {
  const set = new Set<string>();
  for (const e of edges) {
    // Normalize: store sorted key so A→B and B→A collide
    const key = e.source < e.target
      ? `${e.source}::${e.target}::${e.type}`
      : `${e.target}::${e.source}::${e.type}`;
    set.add(key);
  }
  return set;
}

function hasEdge(
  source: string,
  target: string,
  type: CodeEdge["type"],
  index: Set<string>,
): boolean {
  const key = source < target
    ? `${source}::${target}::${type}`
    : `${target}::${source}::${type}`;
  return index.has(key);
}

function addEdge(
  source: string,
  target: string,
  type: CodeEdge["type"],
  weight: number,
  edges: CodeEdge[],
  index: Set<string>,
): boolean {
  if (source === target) return false;
  if (hasEdge(source, target, type, index)) return false;

  const key = source < target
    ? `${source}::${target}::${type}`
    : `${target}::${source}::${type}`;
  index.add(key);

  edges.push({ source, target, type, weight });
  return true;
}

// ── Call chain detection ────────────────────────────────────

/**
 * If function A calls function B, and B calls function C,
 * infer a weaker edge A → C (transitive call chain).
 */
function extractCallChains(
  nodes: CodeNode[],
  edges: CodeEdge[],
  index: Set<string>,
  newEdges: CodeEdge[],
  minWeight: number,
): number {
  let added = 0;

  // Build call graph: function → set of callees
  const calls = new Map<string, Set<string>>();
  for (const e of edges) {
    if (e.type === "calls" && e.weight >= minWeight) {
      let callees = calls.get(e.source);
      if (!callees) {
        callees = new Set();
        calls.set(e.source, callees);
      }
      callees.add(e.target);
    }
  }

  // For each function, find 2-hop transitive calls
  for (const [caller, directCallees] of calls) {
    for (const callee of directCallees) {
      const transitiveCallees = calls.get(callee);
      if (!transitiveCallees) continue;
      for (const transitive of transitiveCallees) {
        if (transitive === caller) continue;
        if (!directCallees.has(transitive)) {
          // Lower weight for transitive edge
          if (addEdge(caller, transitive, "calls", 0.3, newEdges, index)) {
            added++;
          }
        }
      }
    }
  }

  return added;
}

// ── Class hierarchy detection ───────────────────────────────

/**
 * Build class inheritance chains from extends/implements edges.
 * If A extends B and B extends C, infer A → C with lower weight.
 */
function extractClassHierarchies(
  nodes: CodeNode[],
  edges: CodeEdge[],
  index: Set<string>,
  newEdges: CodeEdge[],
  minWeight: number,
): number {
  let added = 0;

  // Build parent map: child → parent
  const parents = new Map<string, string>();
  for (const e of edges) {
    if (
      (e.type === "extends" || e.type === "implements") &&
      e.weight >= minWeight
    ) {
      parents.set(e.source, e.target);
    }
  }

  // Walk up the hierarchy for each class, adding transitive edges
  const nodeMap = buildNodeMap(nodes);
  for (const node of nodes) {
    if (node.type !== "class") continue;

    let current = node.id;
    const visited = new Set<string>();
    visited.add(current);

    while (parents.has(current)) {
      const parent = parents.get(current)!;
      if (visited.has(parent)) break; // cycle guard
      visited.add(parent);

      if (parent !== node.id) {
        if (addEdge(node.id, parent, "extends", 0.3, newEdges, index)) {
          added++;
        }
      }
      current = parent;
    }
  }

  return added;
}

// ── Cross-file reference detection ──────────────────────────

/**
 * When two nodes in different files share the same label (or fuzzy match),
 * infer a "references" edge between them.
 */
function extractCrossReferences(
  nodes: CodeNode[],
  edges: CodeEdge[],
  index: Set<string>,
  newEdges: CodeEdge[],
  minWeight: number,
): number {
  let added = 0;

  // Group nodes by normalized label
  const byLabel = new Map<string, CodeNode[]>();
  for (const node of nodes) {
    const normalized = node.label.toLowerCase().replace(/[^a-z0-9_]/g, "");
    if (normalized.length < 3) continue; // skip very short labels

    let group = byLabel.get(normalized);
    if (!group) {
      group = [];
      byLabel.set(normalized, group);
    }
    group.push(node);
  }

  // Connect nodes with the same label but in different files
  for (const [, group] of byLabel) {
    if (group.length < 2) continue;

    for (let i = 0; i < group.length; i++) {
      for (let j = i + 1; j < group.length; j++) {
        const a = group[i];
        const b = group[j];

        // Only cross-file
        if (a.path === b.path) continue;

        if (addEdge(a.id, b.id, "references", 0.4, newEdges, index)) {
          added++;
        }
      }
    }
  }

  return added;
}

// ── Public API ──────────────────────────────────────────────

/**
 * Extract semantic relationships from a code graph.
 *
 * Augments the edge list with:
 * - Call chains: transitive function calls (A→B, B→C → A→C)
 * - Class hierarchies: transitive extends/implements
 * - Cross-file references: same-named symbols across files
 *
 * @param nodes - Code nodes from buildCodeGraph()
 * @param edges - Code edges from buildCodeGraph()
 * @param options - Extraction options
 * @returns Enriched edges + statistics
 */
export function extractSemanticEdges(
  nodes: CodeNode[],
  edges: CodeEdge[],
  options: SemanticEdgesOptions = {},
): SemanticEdgesResult {
  const { crossFileReferences = true, minWeight = 0.1 } = options;

  const index = buildEdgeIndex(edges);
  const newEdges: CodeEdge[] = [];

  const callChains = extractCallChains(nodes, edges, index, newEdges, minWeight);
  const classHierarchies = extractClassHierarchies(
    nodes,
    edges,
    index,
    newEdges,
    minWeight,
  );
  const crossReferences = crossFileReferences
    ? extractCrossReferences(nodes, edges, index, newEdges, minWeight)
    : 0;

  return {
    edges: [...edges, ...newEdges],
    added: { callChains, classHierarchies, crossReferences },
  };
}
