// MCP Server — Ingest Bridge
//
// Delegates to ingest.py via the Python sidecar (LWM_07).
// Zero subprocess — uses sidecar.call("ingest_source", ...).

import path from "node:path";
import type { PythonSidecar } from "./adapters/sidecar.js";

// ── Public API ──────────────────────────────────────────────────────────────

export interface IngestResult {
  success: boolean;
  pages_created: number;
  pages_updated: number;
  reviews_written: number;
  error: string;
}

/**
 * Ingest a source file into the wiki.
 *
 * Uses the Python sidecar for zero-subprocess execution.
 * Falls back to error if sidecar is not available.
 *
 * @param sidecar     PythonSidecar instance
 * @param wikiRoot    Absolute path to wiki root
 * @param sourcePath  Path to the source file to ingest
 * @param options     Additional ingest options (provider, force, etc.)
 */
export async function runIngest(
  sidecar: PythonSidecar,
  wikiRoot: string,
  sourcePath: string,
  options: Record<string, unknown> = {},
): Promise<IngestResult> {
  if (!sidecar.isRunning()) {
    return {
      success: false,
      pages_created: 0,
      pages_updated: 0,
      reviews_written: 0,
      error: "Python sidecar is not running — cannot ingest",
    };
  }

  try {
    const result = (await sidecar.call("ingest_source", {
      wiki_root: wikiRoot,
      source_path: sourcePath,
      options,
    })) as IngestResult;

    return result ?? {
      success: false,
      pages_created: 0,
      pages_updated: 0,
      reviews_written: 0,
      error: "ingest returned null",
    };
  } catch (e) {
    return {
      success: false,
      pages_created: 0,
      pages_updated: 0,
      reviews_written: 0,
      error: `Ingest failed: ${e instanceof Error ? e.message : String(e)}`,
    };
  }
}
