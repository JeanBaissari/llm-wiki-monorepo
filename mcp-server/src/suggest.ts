// MCP Server — Suggest Links Bridge
//
// Delegates to link_suggest.py via the Python sidecar (LWM_07).
// Zero subprocess — uses sidecar.call("suggest_links", ...).

import type { PythonSidecar } from "./adapters/sidecar.js";

// ── Types ────────────────────────────────────────────────────────────────────

export interface Suggestion {
  source: string;
  source_stem: string;
  source_title: string;
  source_type: string;
  target: string;
  target_stem: string;
  target_title: string;
  target_type: string;
  entity: string;
  score: number;
  reason: string;
}

export interface SuggestResult {
  suggestions: Suggestion[];
  total: number;
}

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * Suggest missing wikilinks for wiki pages.
 *
 * Uses the Python sidecar for zero-subprocess execution.
 * Delegates to link_suggest.py's entity registry + inverted index pipeline.
 *
 * @param sidecar     PythonSidecar instance
 * @param wikiPath    Absolute path to wiki root
 * @param options     threshold, limit, pages
 */
export async function suggestLinks(
  sidecar: PythonSidecar,
  wikiPath: string,
  options: {
    threshold?: number;
    limit?: number;
    pages?: string[];
  } = {},
): Promise<SuggestResult> {
  if (!sidecar.isRunning()) {
    throw new Error("Python sidecar is not running — cannot suggest links");
  }

  const result = (await sidecar.call("suggest_links", {
    wiki_root: wikiPath,
    threshold: options.threshold,
    limit: options.limit,
    pages: options.pages,
  })) as SuggestResult;

  return {
    suggestions: result.suggestions ?? [],
    total: result.total ?? 0,
  };
}
