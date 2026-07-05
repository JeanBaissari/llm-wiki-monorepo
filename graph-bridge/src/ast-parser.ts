// ============================================================
// graph-bridge/src/ast-parser.ts — AST extraction wrapper
// ============================================================
//
// Wraps @sentropic/graphify for deterministic structural extraction
// from source code using tree-sitter. graphify is an optional peer
// dependency (42 MB) — callers must install it explicitly.
//
// Produces CodeNode[] and CodeEdge[] in the graph-bridge type system.
// ============================================================

import type { CodeNode, CodeEdge } from "./types.js";

// ── Language extension → label mapping ──────────────────────

const EXT_LANGUAGE: Record<string, string> = {
  ".py": "Python",
  ".js": "JavaScript",
  ".jsx": "JavaScript",
  ".mjs": "JavaScript",
  ".ts": "TypeScript",
  ".tsx": "TypeScript",
  ".go": "Go",
  ".rs": "Rust",
  ".java": "Java",
  ".c": "C",
  ".h": "C",
  ".cpp": "C++",
  ".cc": "C++",
  ".cxx": "C++",
  ".hpp": "C++",
  ".rb": "Ruby",
  ".cs": "C#",
  ".kt": "Kotlin",
  ".kts": "Kotlin",
  ".scala": "Scala",
  ".php": "PHP",
  ".swift": "Swift",
  ".lua": "Lua",
  ".zig": "Zig",
  ".jl": "Julia",
  ".ex": "Elixir",
  ".exs": "Elixir",
  ".dart": "Dart",
  ".r": "R",
  ".sql": "SQL",
  ".md": "Markdown",
  ".mdx": "Markdown",
};

function languageFromPath(filePath: string): string {
  const dot = filePath.lastIndexOf(".");
  if (dot === -1) return "unknown";
  const ext = filePath.slice(dot).toLowerCase();
  return EXT_LANGUAGE[ext] ?? ext.slice(1);
}

// ── Node type mapping ───────────────────────────────────────

/**
 * Map graphify node_type to our CodeNode.type.
 * graphify node_type values: "file", "class", "function", "import", "call", etc.
 */
function mapNodeType(graphifyType: string): CodeNode["type"] {
  switch (graphifyType) {
    case "file":
      return "file";
    case "class":
      return "class";
    case "function":
    case "method":
      return "function";
    case "import":
      return "import";
    default:
      return "dependency";
  }
}

// ── Edge type mapping ───────────────────────────────────────

/**
 * Map graphify relation string to our CodeEdge.type.
 */
function mapEdgeType(relation: string): CodeEdge["type"] {
  const r = relation.toLowerCase();
  if (r.includes("import")) return "imports";
  if (r.includes("extend")) return "extends";
  if (r.includes("implement")) return "implements";
  if (r.includes("call") || r.includes("invoke")) return "calls";
  return "references";
}

// ── Graphify module shape (used for type annotation only) ───

interface GraphifyModule {
  collectFiles(target: string, opts?: { followSymlinks?: boolean }): string[];
  extract(paths: string[]): Promise<{
    nodes: Array<{
      id: string;
      label: string;
      node_type: string;
      source_file: string;
      source_location?: string;
      confidence?: number;
    }>;
    edges: Array<{
      source: string;
      target: string;
      relation: string;
      source_file: string;
      source_location?: string;
      confidence?: number;
      weight?: number;
    }>;
  }>;
}

// ── Public API ──────────────────────────────────────────────

export interface BuildCodeGraphOptions {
  /** Project root for resolving relative paths */
  rootDir?: string;
  /** Whether to follow symlinks when collecting files */
  followSymlinks?: boolean;
}

export interface CodeGraphResult {
  nodes: CodeNode[];
  edges: CodeEdge[];
  /** Number of files scanned */
  fileCount: number;
}

/**
 * Build a code-structure graph from a source directory.
 *
 * Dynamically imports `@sentropic/graphify` — the caller must
 * have it installed as a dependency.
 *
 * @param target - Path to a source file or directory
 * @param options.rootDir - Project root for relative path resolution
 * @returns CodeNode[] and CodeEdge[] in graph-bridge format
 * @throws {Error} If @sentropic/graphify is not installed
 */
export async function buildCodeGraph(
  target: string,
  options: BuildCodeGraphOptions = {},
): Promise<CodeGraphResult> {
  const { rootDir, followSymlinks = false } = options;

  // ── Dynamic import — graphify is optional ─────────────────
  // Use a computed module specifier so tsc doesn't try to resolve it.
  const MODULE_NAME = "@sentropic/graphify";
  let graphify: GraphifyModule;

  try {
    graphify = await import(MODULE_NAME) as GraphifyModule;
  } catch {
    throw new Error(
      "@sentropic/graphify is not installed. Install it with:\n" +
        "  npm install @sentropic/graphify\n" +
        "It is an optional peer dependency of @baissari/llm-wiki-graph-bridge.",
    );
  }

  // ── Collect source files ──────────────────────────────────
  const files = graphify.collectFiles(target, { followSymlinks });
  if (files.length === 0) {
    return { nodes: [], edges: [], fileCount: 0 };
  }

  // ── Run extraction ────────────────────────────────────────
  const extraction = await graphify.extract(files);

  // ── Convert to our types ──────────────────────────────────
  const nodes: CodeNode[] = extraction.nodes.map((n) => ({
    id: n.id,
    label: n.label,
    type: mapNodeType(n.node_type),
    path: rootDir
      ? n.source_file.startsWith(rootDir)
        ? n.source_file.slice(rootDir.length).replace(/^\//, "")
        : n.source_file
      : n.source_file,
    language: languageFromPath(n.source_file),
  }));

  const edges: CodeEdge[] = extraction.edges.map((e) => ({
    source: e.source,
    target: e.target,
    type: mapEdgeType(e.relation),
    weight: e.weight ?? 0.5,
  }));

  return { nodes, edges, fileCount: files.length };
}
