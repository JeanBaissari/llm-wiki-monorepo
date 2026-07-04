// MCP Server — Backup Bridge
//
// Delegates to backup.py via the Python sidecar (LWM_07).
// Zero subprocess — uses sidecar.call("backup", ...).

import type { PythonSidecar } from "./sidecar.js";

// ── Types ────────────────────────────────────────────────────────────────────

export interface BackupResult {
  archive_path: string;
  size_bytes: number;
  file_count: number;
  integrity: string;
}

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * Create a timestamped snapshot backup of the wiki.
 *
 * Uses the Python sidecar for zero-subprocess execution.
 * Delegates to backup.py's cmd_snapshot with stdout capture.
 *
 * @param sidecar     PythonSidecar instance
 * @param wikiPath    Absolute path to wiki root
 */
export async function createBackup(
  sidecar: PythonSidecar,
  wikiPath: string,
): Promise<BackupResult> {
  if (!sidecar.isRunning()) {
    throw new Error("Python sidecar is not running — cannot create backup");
  }

  const result = (await sidecar.call("backup", {
    wiki_root: wikiPath,
  })) as BackupResult;

  if (!result.archive_path) {
    throw new Error(
      `Backup failed: ${(result as unknown as { error?: string }).error ?? "unknown error"}`,
    );
  }

  return result;
}
