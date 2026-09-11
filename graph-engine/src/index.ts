// Graph Engine — CLI Wrapper + Public API
//
// CLI Usage:
//   node dist/index.js --wiki <path> --action <build|insights|search|relevance>
//     [--query <q>] [--node <id>] [--format <json>] [--tuning-json <path>]
//
// Programmatic usage:
//   import { findSurprisingConnections, detectKnowledgeGaps, applyGraphSearch } from 'graph-engine';

import { readFileSync, existsSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Re-export public API for programmatic use
// ---------------------------------------------------------------------------
export { findSurprisingConnections, detectKnowledgeGaps } from './insights.js';
export type { SurprisingConnection, KnowledgeGap } from './types.js';
export { applyGraphSearch } from './search.js';
export type { SearchResult } from './search.js';
export { buildWikiGraph, buildRetrievalGraph } from './build.js';
export { calculateRelevance, getRelatedNodes } from './relevance.js';
export { loadTuningJson, toRelevanceOptions, toInsightsOptions, toLouvainOptions } from './tuning.js';
export type { TuningProfile } from './tuning.js';

import { loadTuningJson, toRelevanceOptions, toInsightsOptions, toLouvainOptions } from './tuning.js';

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

interface CliArgs {
  wiki: string;
  action: string;
  query?: string;
  node?: string;
  tuningJson?: string;
}

function parseArgs(): CliArgs {
  const argv = process.argv.slice(2);
  const args: Record<string, string> = {};

  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    if (key.startsWith('--')) {
      const name = key.slice(2);
      const val = argv[i + 1];
      if (val !== undefined && !val.startsWith('--')) {
        args[name] = val;
        i++;
      } else {
        args[name] = '';
      }
    }
  }

  return {
    wiki: args['wiki'] ?? '',
    action: args['action'] ?? '',
    query: args['query'],
    node: args['node'],
    tuningJson: args['tuning-json'] || args['tuning_json'],
  };
}

// ---------------------------------------------------------------------------
// Graph data loader (for actions that need pre-built graph-data.json)
// ---------------------------------------------------------------------------

interface GraphData {
  nodes: import('./types.js').GraphNode[];
  edges: import('./types.js').GraphEdge[];
  communities: import('./types.js').CommunityInfo[];
}

function loadGraphData(wikiPath: string): GraphData {
  const dataPath = join(wikiPath, 'graph-data.json');
  if (!existsSync(dataPath)) {
    throw new Error(`Graph data not found at ${dataPath}. Run "node graph-engine/dist/index.js --wiki ${wikiPath} --action build" first.`);
  }
  const raw = readFileSync(dataPath, 'utf-8');
  return JSON.parse(raw) as GraphData;
}

// ---------------------------------------------------------------------------
// Lazy dynamic import helpers
// ---------------------------------------------------------------------------

async function tryImport(name: string): Promise<Record<string, unknown> | null> {
  try {
    return await import(name);
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  try {
    const { wiki, action, query, node: nodeId, tuningJson } = parseArgs();

    if (!wiki || !action) {
      console.error(
        'Usage: node dist/index.js --wiki <path> --action <build|insights|search|relevance> [--query <q>] [--node <id>] [--tuning-json <path>]',
      );
      process.exitCode = 1;
      return;
    }

    // LWM_031: the resolved tuning emitted by `llm-wiki tuning --json`. Null
    // (absent/invalid) → every consumer keeps its built-in defaults.
    const tuning = loadTuningJson(tuningJson);
    const relevanceOptions = toRelevanceOptions(tuning);
    const insightsOptions = toInsightsOptions(tuning);
    const louvainOptions = toLouvainOptions(tuning);

    let result: unknown;

    switch (action) {
      // ── Build ────────────────────────────────────────────
      case 'build': {
        const buildMod = await tryImport('./build.js');
        if (!buildMod || typeof (buildMod as any).buildWikiGraph !== 'function') {
          throw new Error('Build action not available — graph-engine build module missing.');
        }
        // Resolve wiki path: if the passed path contains a wiki/ subdir, use it
        const wikiSubdir = join(wiki, 'wiki');
        const wikiPath = existsSync(wikiSubdir) ? wikiSubdir : wiki;
        result = await (buildMod as any).buildWikiGraph(wikiPath, {
          relevance: relevanceOptions,
          louvain: louvainOptions,
        });
        // Persist graph-data.json in the original wiki root directory
        const outputPath = join(wiki, 'graph-data.json');
        writeFileSync(outputPath, JSON.stringify(result, null, 2), 'utf-8');
        break;
      }

      // ── Insights ─────────────────────────────────────────
      case 'insights': {
        const data = loadGraphData(wiki);
        const { findSurprisingConnections, detectKnowledgeGaps } = await import('./insights.js');
        result = {
          surprisingConnections: findSurprisingConnections(data.nodes, data.edges, data.communities, 5, insightsOptions),
          knowledgeGaps: detectKnowledgeGaps(data.nodes, data.edges, data.communities, 8, insightsOptions),
        };
        break;
      }

      // ── Search ───────────────────────────────────────────
      case 'search': {
        if (!query) {
          throw new Error('--query is required for the search action');
        }
        const data = loadGraphData(wiki);
        const { applyGraphSearch } = await import('./search.js');
        result = applyGraphSearch(data.nodes, data.edges, query);
        break;
      }

      // ── Relevance ────────────────────────────────────────
      case 'relevance': {
        if (!nodeId) {
          throw new Error('--node is required for the relevance action');
        }
        const data = loadGraphData(wiki);
        const relMod = await import('./relevance.js');
        if (
          typeof relMod.getRelatedNodes !== 'function' ||
          typeof relMod.buildGraphStructure !== 'function'
        ) {
          throw new Error('Relevance action not available — graph-engine relevance module missing.');
        }
        const structure = relMod.buildGraphStructure(data.edges);
        result = relMod.getRelatedNodes(nodeId, data.nodes, structure, 10, relevanceOptions);
        break;
      }

      // ── Merged (unified wiki + code graph) ───────────────
      // Removed in v0.6.4: external code-analysis merge had no in-repo
      // consumers or tests. Use `build`, `relevance`, and `insights`.

      // ── Export graph ─────────────────────────────────────
      // Removed in v0.6.4: HTML/SVG export depended on the code-graph merge.

      default: {
        throw new Error(
          `Unknown action: "${action}". Valid actions: build, insights, search, relevance.`,
        );
      }
    }

    console.log(JSON.stringify(result, null, 2));
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(JSON.stringify({ error: message }));
    process.exitCode = 1;
  }
}

const __filename = fileURLToPath(import.meta.url);
if (process.argv[1] === __filename) {
  main();
}
