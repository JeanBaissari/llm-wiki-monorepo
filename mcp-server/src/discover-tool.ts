// MCP Server — Discover Entities Bridge
//
// Delegates to discover.py/link_suggest.py entity registry via the Python sidecar (LWM_07).
// Zero subprocess — uses sidecar.call("discover_entities", ...).

import type { PythonSidecar } from "./sidecar.js";

// ── Types ────────────────────────────────────────────────────────────────────

export interface Entity {
  name: string;
  stem: string;
  title: string;
  type: string;
  aliases?: string[];
}

export interface EntityRegistryResult {
  entities: Entity[];
  total: number;
}

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * Discover all entities registered in the wiki.
 *
 * Uses the Python sidecar for zero-subprocess execution.
 * Builds entity registry from wiki pages via link_suggest.py's
 * build_entity_registry pipeline.
 *
 * @param sidecar     PythonSidecar instance
 * @param wikiPath    Absolute path to wiki root
 * @param entityType  Optional filter by entity type
 */
export async function discoverEntities(
  sidecar: PythonSidecar,
  wikiPath: string,
  entityType?: string,
): Promise<EntityRegistryResult> {
  if (!sidecar.isRunning()) {
    throw new Error("Python sidecar is not running — cannot discover entities");
  }

  const result = (await sidecar.call("discover_entities", {
    wiki_root: wikiPath,
    entity_type: entityType ?? null,
  })) as EntityRegistryResult;

  return {
    entities: result.entities ?? [],
    total: result.total ?? 0,
  };
}
