// Graph Engine — Graph-Based Search / Filtering

import { GraphNode, GraphEdge } from './types.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SearchResult {
  /** Nodes that matched the query tokens. */
  nodes: GraphNode[];
  /** Edges where both source and target are in the matched node set. */
  edges: GraphEdge[];
  /** Set of matched node IDs (Set for efficient lookups). */
  matchedNodeIds: Set<string>;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

/**
 * Token-based graph search.
 *
 * Splits `query` into whitespace-separated tokens and returns only nodes whose
 * label, id, type, or path contains **all** of the tokens (case-insensitive).
 * Edges are filtered to only those connecting two matched nodes.
 *
 * @param nodes  Full list of graph nodes.
 * @param edges  Full list of graph edges.
 * @param query  Search query string.
 * @returns      Filtered nodes, edges, and the set of matched node IDs.
 */
export function applyGraphSearch(
  nodes: GraphNode[],
  edges: GraphEdge[],
  query: string,
): SearchResult {
  // Empty query → return everything
  if (!query || query.trim().length === 0) {
    return {
      nodes: [...nodes],
      edges: [...edges],
      matchedNodeIds: new Set(nodes.map((n) => n.id)),
    };
  }

  const tokens = query
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length > 0);

  if (tokens.length === 0) {
    return {
      nodes: [...nodes],
      edges: [...edges],
      matchedNodeIds: new Set(nodes.map((n) => n.id)),
    };
  }

  // Score each node: count of tokens that appear in its searchable fields.
  const matchedNodeIds = new Set<string>();
  const nodeMap = new Map<string, GraphNode>();

  for (const node of nodes) {
    nodeMap.set(node.id, node);

    const haystack = `${node.label} ${node.id} ${node.type} ${node.path}`.toLowerCase();
    // A node matches if ALL tokens are found somewhere in the haystack.
    const allMatch = tokens.every((token) => haystack.includes(token));

    if (allMatch) {
      matchedNodeIds.add(node.id);
    }
  }

  // Filter edges: both endpoints must be matched
  const filteredEdges = edges.filter(
    (e) => matchedNodeIds.has(e.source) && matchedNodeIds.has(e.target),
  );

  // Filter nodes to matched set
  const filteredNodes = nodes.filter((n) => matchedNodeIds.has(n.id));

  return {
    nodes: filteredNodes,
    edges: filteredEdges,
    matchedNodeIds,
  };
}
