// ============================================================
// graph-bridge/src/types.ts — Shared type definitions
// ============================================================

// ── Code structure types ────────────────────────────────────

export interface CodeNode {
  /** Unique ID — e.g. "src/build.ts:buildWikiGraph" */
  id: string;
  /** Human-readable label */
  label: string;
  /** AST node kind */
  type: "file" | "class" | "function" | "import" | "dependency";
  /** Filesystem path relative to project root */
  path: string;
  /** Programming language */
  language: string;
}

export interface CodeEdge {
  source: string;
  target: string;
  /** Semantic relationship kind */
  type: "imports" | "extends" | "implements" | "calls" | "references";
  /** Edge weight (0–1) */
  weight: number;
}

// ── Wiki graph types (compatible with graph-engine) ─────────

export interface GraphNode {
  /** Unique ID — page slug */
  id: string;
  /** Human-readable label */
  label: string;
  /** Page type from frontmatter */
  type: string;
  /** Relative path */
  path: string;
  /** Total inbound + outbound wikilinks */
  linkCount: number;
  /** Community ID */
  community: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  /** Relevance weight (0–1) */
  weight: number;
}

// ── Unified graph types ─────────────────────────────────────

export interface UnifiedNode {
  id: string;
  label: string;
  /** Which graph(s) this node belongs to */
  domain: "wiki" | "code" | "both";
  /** Wiki page type (when domain includes wiki) */
  wikiType?: string;
  /** Code node type (when domain includes code) */
  codeType?: CodeNode["type"];
  /** Best available path */
  path: string;
  /** Programming language (when domain includes code) */
  language?: string;
}

export interface UnifiedEdge {
  source: string;
  target: string;
  /** Which graph this edge comes from, or "cross" for merged edges */
  domain: "wikilink" | "codestructure" | "cross";
  weight: number;
  /** Semantic relation (for code-structure / cross edges) */
  relation?: string;
}

export interface UnifiedGraph {
  /** Wiki-only nodes and edges (from graph-data.json) */
  wikilinks: { nodes: GraphNode[]; edges: GraphEdge[] };
  /** Code-only nodes and edges (from code-graph.json) */
  codestructure: { nodes: CodeNode[]; edges: CodeEdge[] };
  /** Merged nodes and edges — unified view */
  merged: { nodes: UnifiedNode[]; edges: UnifiedEdge[] };
}
