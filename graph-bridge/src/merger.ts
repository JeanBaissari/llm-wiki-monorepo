// ============================================================
// graph-bridge/src/merger.ts — Wiki + Code graph merger
// ============================================================
//
// Merges a wiki graph (graph-data.json from graph-engine) with
// a code-structure graph (code-graph.json from buildCodeGraph)
// into a unified view.
//
// Cross-domain edges are created when a code entity's label or
// path matches a wiki page's title or entity name.
// ============================================================

import Graph from "graphology";
import type {
  CodeNode,
  CodeEdge,
  GraphNode,
  GraphEdge,
  UnifiedNode,
  UnifiedEdge,
  UnifiedGraph,
} from "./types.js";

// ── Types ───────────────────────────────────────────────────

export interface MergeOptions {
  /**
   * Minimum similarity threshold for cross-domain matching (0–1).
   * Default: 0.7 — requires reasonably strong label overlap.
   */
  crossDomainThreshold?: number;
  /**
   * When true, also match by path segments (e.g., "src/foo/bar.ts"
   * matches wiki page "foo/bar").
   */
  matchByPath?: boolean;
}

export interface MergeResult {
  graph: UnifiedGraph;
  stats: {
    wikiNodes: number;
    wikiEdges: number;
    codeNodes: number;
    codeEdges: number;
    crossEdges: number;
    mergedNodes: number;
  };
}

// ── Label normalization ─────────────────────────────────────

/**
 * Normalize a label for fuzzy comparison:
 * lowercase, strip non-alphanumeric, collapse whitespace.
 */
function normalizeLabel(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9\s_-]/g, "")
    .replace(/[\s_-]+/g, " ")
    .trim();
}

/**
 * Jaccard-like token overlap between two normalized strings.
 */
function tokenOverlap(a: string, b: string): number {
  const tokensA = new Set(a.split(/\s+/).filter(Boolean));
  const tokensB = new Set(b.split(/\s+/).filter(Boolean));

  if (tokensA.size === 0 || tokensB.size === 0) return 0;

  let intersection = 0;
  for (const t of tokensA) {
    if (tokensB.has(t)) intersection++;
  }

  const union = tokensA.size + tokensB.size - intersection;
  return intersection / union;
}

// ── Path-based matching ─────────────────────────────────────

/**
 * Extract meaningful segments from a file path:
 * "src/components/Button.tsx" → ["src", "components", "button"]
 */
function pathSegments(filePath: string): string[] {
  return filePath
    .replace(/\.[^.]+$/, "") // strip extension
    .split(/[/\\]/)
    .map((s) => s.toLowerCase())
    .filter((s) => s.length > 0 && s !== "src" && s !== "lib" && s !== "index");
}

// ── Cross-domain node matching ──────────────────────────────

interface CrossMatch {
  codeNode: CodeNode;
  wikiNode: GraphNode;
  score: number;
}

/**
 * Find code nodes that correspond to wiki pages.
 *
 * Matching strategy:
 * 1. Exact label match (high confidence)
 * 2. Token overlap on normalized labels
 * 3. Path segment match (optional)
 */
function findCrossMatches(
  codeNodes: CodeNode[],
  wikiNodes: GraphNode[],
  options: MergeOptions,
): CrossMatch[] {
  const { crossDomainThreshold = 0.7, matchByPath = true } = options;
  const matches: CrossMatch[] = [];

  // Build lookup maps
  const wikiByLabel = new Map<string, GraphNode>();
  const wikiByPathSeg = new Map<string, GraphNode[]>();

  for (const wn of wikiNodes) {
    wikiByLabel.set(normalizeLabel(wn.label), wn);

    if (matchByPath) {
      for (const seg of pathSegments(wn.path)) {
        let list = wikiByPathSeg.get(seg);
        if (!list) {
          list = [];
          wikiByPathSeg.set(seg, list);
        }
        list.push(wn);
      }
    }
  }

  // Track which wiki nodes have been matched (to avoid duplicates)
  const matchedWiki = new Set<string>();

  for (const cn of codeNodes) {
    const cnNorm = normalizeLabel(cn.label);

    // Strategy 1: Exact normalized label match
    const exactMatch = wikiByLabel.get(cnNorm);
    if (exactMatch && !matchedWiki.has(exactMatch.id)) {
      matches.push({ codeNode: cn, wikiNode: exactMatch, score: 1.0 });
      matchedWiki.add(exactMatch.id);
      continue;
    }

    // Strategy 2: Token overlap
    let bestScore = 0;
    let bestMatch: GraphNode | null = null;

    for (const wn of wikiNodes) {
      if (matchedWiki.has(wn.id)) continue;
      const score = tokenOverlap(cnNorm, normalizeLabel(wn.label));
      if (score > bestScore && score >= crossDomainThreshold) {
        bestScore = score;
        bestMatch = wn;
      }
    }

    if (bestMatch) {
      matches.push({ codeNode: cn, wikiNode: bestMatch, score: bestScore });
      matchedWiki.add(bestMatch.id);
      continue;
    }

    // Strategy 3: Path segment match
    if (matchByPath) {
      const segs = pathSegments(cn.path);
      for (const seg of segs) {
        const candidates = wikiByPathSeg.get(seg);
        if (!candidates) continue;

        for (const wn of candidates) {
          if (matchedWiki.has(wn.id)) continue;
          // Only if the segment is a good label match
          const score = tokenOverlap(cnNorm, normalizeLabel(wn.label));
          if (score >= crossDomainThreshold) {
            matches.push({ codeNode: cn, wikiNode: wn, score });
            matchedWiki.add(wn.id);
            break;
          }
        }
        if (bestMatch) break; // already matched from this loop
      }
    }
  }

  return matches;
}

// ── Main merge function ─────────────────────────────────────

/**
 * Merge a wiki graph with a code-structure graph into a unified view.
 *
 * @param wikiGraph - GraphData from graph-engine (graph-data.json format)
 * @param codeGraph - CodeNode[] + CodeEdge[] from buildCodeGraph()
 * @param options - Merge configuration
 * @returns UnifiedGraph with wikilinks, codestructure, and merged sub-graphs
 */
export function mergeGraphs(
  wikiGraph: { nodes: GraphNode[]; edges: GraphEdge[] },
  codeGraph: { nodes: CodeNode[]; edges: CodeEdge[] },
  options: MergeOptions = {},
): MergeResult {
  const { nodes: wikiNodes, edges: wikiEdges } = wikiGraph;
  const { nodes: codeNodes, edges: codeEdges } = codeGraph;

  // ── Find cross-domain matches ─────────────────────────────
  const matches = findCrossMatches(codeNodes, wikiNodes, options);
  const matchMap = new Map<string, GraphNode>();
  const reverseMatchMap = new Map<string, CodeNode>();
  for (const m of matches) {
    matchMap.set(m.codeNode.id, m.wikiNode);
    reverseMatchMap.set(m.wikiNode.id, m.codeNode);
  }

  const matchedCodeIds = new Set(matchMap.keys());
  const matchedWikiIds = new Set(reverseMatchMap.keys());

  // ── Build UnifiedNodes ────────────────────────────────────

  const unifiedNodes: UnifiedNode[] = [];
  const unifiedNodeIds = new Set<string>();

  // Wiki-only nodes
  for (const wn of wikiNodes) {
    if (matchedWikiIds.has(wn.id)) continue; // handled as "both"
    const un: UnifiedNode = {
      id: `wiki:${wn.id}`,
      label: wn.label,
      domain: "wiki",
      wikiType: wn.type,
      path: wn.path,
    };
    unifiedNodes.push(un);
    unifiedNodeIds.add(un.id);
  }

  // Code-only nodes
  for (const cn of codeNodes) {
    if (matchedCodeIds.has(cn.id)) continue; // handled as "both"
    const un: UnifiedNode = {
      id: `code:${cn.id}`,
      label: cn.label,
      domain: "code",
      codeType: cn.type,
      path: cn.path,
      language: cn.language,
    };
    unifiedNodes.push(un);
    unifiedNodeIds.add(un.id);
  }

  // Cross-domain nodes (both)
  for (const m of matches) {
    const un: UnifiedNode = {
      id: `both:${m.codeNode.id}`,
      label: m.wikiNode.label, // prefer wiki label
      domain: "both",
      wikiType: m.wikiNode.type,
      codeType: m.codeNode.type,
      path: m.wikiNode.path, // prefer wiki path
      language: m.codeNode.language,
    };
    unifiedNodes.push(un);
    unifiedNodeIds.add(un.id);
  }

  // ── Build UnifiedEdges ────────────────────────────────────

  const unifiedEdges: UnifiedEdge[] = [];

  // Helper to resolve a node ID to its unified ID
  function resolveUnifiedId(
    id: string,
    domain: "wiki" | "code",
  ): string | null {
    if (domain === "wiki") {
      if (matchedWikiIds.has(id)) {
        // Find the matching code node ID
        const cn = reverseMatchMap.get(id);
        return cn ? `both:${cn.id}` : `wiki:${id}`;
      }
      return `wiki:${id}`;
    } else {
      if (matchedCodeIds.has(id)) {
        return `both:${id}`;
      }
      return `code:${id}`;
    }
  }

  // Wiki edges → wikilink domain
  for (const we of wikiEdges) {
    const src = resolveUnifiedId(we.source, "wiki");
    const tgt = resolveUnifiedId(we.target, "wiki");
    if (src && tgt && src !== tgt) {
      unifiedEdges.push({
        source: src,
        target: tgt,
        domain: "wikilink",
        weight: we.weight,
      });
    }
  }

  // Code edges → codestructure domain
  for (const ce of codeEdges) {
    const src = resolveUnifiedId(ce.source, "code");
    const tgt = resolveUnifiedId(ce.target, "code");
    if (src && tgt && src !== tgt) {
      unifiedEdges.push({
        source: src,
        target: tgt,
        domain: "codestructure",
        weight: ce.weight,
        relation: ce.type,
      });
    }
  }

  // Cross-domain edges (between matched node and its wiki neighbors)
  for (const m of matches) {
    const bothId = `both:${m.codeNode.id}`;

    // Connect to wiki nodes that link to the matched wiki page
    for (const we of wikiEdges) {
      if (we.source === m.wikiNode.id || we.target === m.wikiNode.id) {
        const otherId =
          we.source === m.wikiNode.id ? we.target : we.source;
        const otherUnifiedId = resolveUnifiedId(otherId, "wiki");
        if (otherUnifiedId && otherUnifiedId !== bothId) {
          // Check if we already have this edge
          const exists = unifiedEdges.some(
            (e) =>
              e.domain === "cross" &&
              ((e.source === bothId && e.target === otherUnifiedId) ||
                (e.source === otherUnifiedId && e.target === bothId)),
          );
          if (!exists) {
            unifiedEdges.push({
              source: bothId,
              target: otherUnifiedId,
              domain: "cross",
              weight: m.score * we.weight,
              relation: "wiki-to-code",
            });
          }
        }
      }
    }
  }

  // Deduplicate edges
  const edgeSeen = new Set<string>();
  const dedupedEdges: UnifiedEdge[] = [];
  for (const ue of unifiedEdges) {
    const key = [ue.source, ue.target, ue.domain].sort().join("||");
    if (!edgeSeen.has(key)) {
      edgeSeen.add(key);
      dedupedEdges.push(ue);
    }
  }

  return {
    graph: {
      wikilinks: { nodes: wikiNodes, edges: wikiEdges },
      codestructure: { nodes: codeNodes, edges: codeEdges },
      merged: { nodes: unifiedNodes, edges: dedupedEdges },
    },
    stats: {
      wikiNodes: wikiNodes.length,
      wikiEdges: wikiEdges.length,
      codeNodes: codeNodes.length,
      codeEdges: codeEdges.length,
      crossEdges: dedupedEdges.filter((e) => e.domain === "cross").length,
      mergedNodes: matches.length,
    },
  };
}

// ── Graphology integration ──────────────────────────────────

/**
 * Build a graphology Graph from a UnifiedGraph for community detection,
 * layout computation, and other graph algorithms.
 */
export function buildUnifiedGraphology(
  unified: UnifiedGraph,
): Graph {
  const g = new Graph({ multi: false, type: "undirected" });

  for (const node of unified.merged.nodes) {
    g.addNode(node.id, {
      label: node.label,
      domain: node.domain,
      wikiType: node.wikiType,
      codeType: node.codeType,
      path: node.path,
      language: node.language,
    });
  }

  for (const edge of unified.merged.edges) {
    if (!g.hasNode(edge.source) || !g.hasNode(edge.target)) continue;
    // Skip if an edge already exists between these nodes (e.g., wiki edge
    // duplicates a code edge when both endpoints are cross-domain nodes).
    if (g.hasEdge(edge.source, edge.target)) continue;
    g.addEdge(edge.source, edge.target, {
      weight: edge.weight,
      domain: edge.domain,
      relation: edge.relation,
    });
  }

  return g;
}
