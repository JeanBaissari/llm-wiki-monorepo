// Graph Engine — Shared Types
// Used by relevance.ts, louvain.ts, insights.ts, build.ts, search.ts

export interface GraphNode {
  /** Unique ID — the page slug (e.g., "entities/andrej-karpathy") */
  id: string;
  /** Human-readable label from frontmatter title or H1 */
  label: string;
  /** Page type from frontmatter (entity, concept, source, comparison, synthesis, overview) */
  type: string;
  /** Filesystem path relative to wiki root */
  path: string;
  /** Total inbound + outbound wikilinks */
  linkCount: number;
  /** Community ID from Louvain detection */
  community: number;
}

export interface GraphEdge {
  source: string;  // node id
  target: string;  // node id
  /** Relevance score between source and target (from relevance model) */
  weight: number;
}

export interface CommunityInfo {
  id: number;
  nodeCount: number;
  /** Intra-community edge density (0–1) */
  cohesion: number;
  /** Top nodes by linkCount (labels) */
  topNodes: string[];
}

export interface SurprisingConnection {
  source: GraphNode;
  target: GraphNode;
  score: number;
  reasons: string[];
  /** Stable ID for dismiss tracking */
  key: string;
}

export interface KnowledgeGap {
  type: "isolated-node" | "sparse-community" | "bridge-node";
  title: string;
  description: string;
  nodeIds: string[];
  suggestion: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  communities: CommunityInfo[];
}

export type GraphAction = "build" | "insights" | "search" | "relevance";
