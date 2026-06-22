// Graph Engine — CLI Wrapper + Public API
//
// CLI Usage:
//   node dist/index.js --wiki <path> --action <build|insights|search|relevance> [--query <q>] [--node <id>]
//
// Programmatic usage:
//   import { findSurprisingConnections, detectKnowledgeGaps, applyGraphSearch } from 'graph-engine';

import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

// ---------------------------------------------------------------------------
// Re-export public API for programmatic use
// ---------------------------------------------------------------------------

export { findSurprisingConnections, detectKnowledgeGaps } from './insights.js';
export type { SurprisingConnection, KnowledgeGap } from './types.js';
export { applyGraphSearch } from './search.js';
export type { SearchResult } from './search.js';

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

interface CliArgs {
  wiki: string;
  action: string;
  query?: string;
  node?: string;
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
    const { wiki, action, query, node: nodeId } = parseArgs();

    if (!wiki || !action) {
      console.error(
        'Usage: node dist/index.js --wiki <path> --action <build|insights|search|relevance> [--query <q>] [--node <id>]',
      );
      process.exitCode = 1;
      return;
    }

    let result: unknown;

    switch (action) {
      case 'build': {
        const buildMod = await tryImport('./build.js');
        if (!buildMod || typeof (buildMod as any).buildWikiGraph !== 'function') {
          throw new Error('Build action not available — graph-engine build module missing.');
        }
        result = await (buildMod as any).buildWikiGraph(wiki);
        break;
      }

      case 'insights': {
        const data = loadGraphData(wiki);
        const { findSurprisingConnections, detectKnowledgeGaps } = await import('./insights.js');
        result = {
          surprisingConnections: findSurprisingConnections(data.nodes, data.edges, data.communities),
          knowledgeGaps: detectKnowledgeGaps(data.nodes, data.edges, data.communities),
        };
        break;
      }

      case 'search': {
        if (!query) {
          throw new Error('--query is required for the search action');
        }
        const data = loadGraphData(wiki);
        const { applyGraphSearch } = await import('./search.js');
        result = applyGraphSearch(data.nodes, data.edges, query);
        break;
      }

      case 'relevance': {
        if (!nodeId) {
          throw new Error('--node is required for the relevance action');
        }
        const data = loadGraphData(wiki);
        const relMod = await tryImport('./relevance.js');
        if (!relMod || typeof (relMod as any).getRelatedNodes !== 'function') {
          throw new Error('Relevance action not available — graph-engine relevance module missing.');
        }
        result = (relMod as any).getRelatedNodes(nodeId, data.nodes, data.edges, 10);
        break;
      }

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

main();
