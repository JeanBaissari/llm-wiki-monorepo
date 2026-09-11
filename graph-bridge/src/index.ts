// ============================================================
// graph-bridge/src/index.ts — Public API
// ============================================================
//
// Programmatic usage:
//   import {
//     extractSemanticEdges,
//     mergeGraphs,
//     buildUnifiedGraphology,
//   } from "@baissari/llm-wiki-graph-bridge";
//
// v0.6.4: AST extraction (ast-parser.ts) was removed together with the
// @sentropic/graphify dependency and the graph-engine code-analysis surface.
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

// ── Semantic edges ─────────────────────────────────────────

export { extractSemanticEdges } from "./semantic-edges.js";
export type {
  SemanticEdgesOptions,
  SemanticEdgesResult,
} from "./semantic-edges.js";

// ── Merger ──────────────────────────────────────────────────

export { mergeGraphs, buildUnifiedGraphology } from "./merger.js";
export type { MergeOptions, MergeResult } from "./merger.js";
