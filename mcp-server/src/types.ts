// MCP Server — Shared Types

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
