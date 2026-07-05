// ============================================================
// graph-bridge/src/index.ts — Public API
// ============================================================
//
// Programmatic usage:
//   import {
//     buildCodeGraph,
//     extractSemanticEdges,
//     mergeGraphs,
//     buildUnifiedGraphology,
//   } from "@baissari/llm-wiki-graph-bridge";
//
// CLI usage (future):
//   node dist/index.js --code /path/to/repo --wiki /path/to/wiki --action merge
// ============================================================

// ── Types ───────────────────────────────────────────────────

export type {
  CodeNode,
  CodeEdge,
  GraphNode,
  GraphEdge,
  UnifiedNode,
  UnifiedEdge,
  UnifiedGraph,
} from "./types.js";

// ── AST parser ──────────────────────────────────────────────

export { buildCodeGraph } from "./ast-parser.js";
export type {
  BuildCodeGraphOptions,
  CodeGraphResult,
} from "./ast-parser.js";

// ── Semantic edges ─────────────────────────────────────────

export { extractSemanticEdges } from "./semantic-edges.js";
export type {
  SemanticEdgesOptions,
  SemanticEdgesResult,
} from "./semantic-edges.js";

// ── Merger ──────────────────────────────────────────────────

export { mergeGraphs, buildUnifiedGraphology } from "./merger.js";
export type { MergeOptions, MergeResult } from "./merger.js";
