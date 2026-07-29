// ── Graph types (canonical from graph-engine) ──────────────────────────

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  path: string;
  linkCount: number;
  community: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}

export interface CommunityInfo {
  id: number;
  nodeCount: number;
  cohesion: number;
  topNodes: string[];
}

export interface SurprisingConnection {
  source: GraphNode;
  target: GraphNode;
  score: number;
  reasons: string[];
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

// ── Code-structure types (canonical from graph-bridge) ─────────────────

export interface CodeNode {
  id: string;
  label: string;
  type: "file" | "class" | "function" | "import" | "dependency";
  path: string;
  language: string;
}

export interface CodeEdge {
  source: string;
  target: string;
  type: "imports" | "extends" | "implements" | "calls" | "references";
  weight: number;
}

// ── Unified graph types (canonical from graph-bridge) ──────────────────

export interface UnifiedNode {
  id: string;
  label: string;
  domain: "wiki" | "code" | "both";
  wikiType?: string;
  codeType?: CodeNode["type"];
  path: string;
  language?: string;
}

export interface UnifiedEdge {
  source: string;
  target: string;
  domain: "wikilink" | "codestructure" | "cross";
  weight: number;
  relation?: string;
}

export interface UnifiedGraph {
  wikilinks: { nodes: GraphNode[]; edges: GraphEdge[] };
  codestructure: { nodes: CodeNode[]; edges: CodeEdge[] };
  merged: { nodes: UnifiedNode[]; edges: UnifiedEdge[] };
}

// ── MCP types (canonical from mcp-server) ──────────────────────────────

export interface WikiProject {
  path: string;
  name: string;
}

export interface FileNode {
  name: string;
  path: string;
  is_dir: boolean;
  children?: FileNode[];
}

export interface SearchResult {
  path: string;
  title: string;
  snippet: string;
  score: number;
}

export interface ReviewItem {
  id: string;
  target: string;
  type: "missing-page" | "duplicate-page" | "contradiction" | "suggestion";
  title: string;
  description: string;
  severity: "info" | "suggest" | "warn" | "error";
  status: "open" | "resolved";
  author: string;
  created: string;
  affectedPages?: string[];
}

export interface LintIssue {
  type: string;
  severity: string;
  page: string;
  detail: string;
}

export interface HealthStatus {
  ok: boolean;
  wikiPath: string;
  pageCount: number;
  lastIngest: string | null;
  openReviews: number;
}
