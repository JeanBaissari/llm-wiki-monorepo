// Graph Engine — CLI Wrapper + Public API
//
// CLI Usage:
//   node dist/index.js --wiki <path> --action <build|insights|search|relevance|merged|export-graph>
//     [--query <q>] [--node <id>] [--code-analysis <path>] [--format <svg|html|json>]
//
// Programmatic usage:
//   import { findSurprisingConnections, detectKnowledgeGaps, applyGraphSearch } from 'graph-engine';

import { readFileSync, existsSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';

// ---------------------------------------------------------------------------
// Re-export public API for programmatic use
// ---------------------------------------------------------------------------
export { findSurprisingConnections, detectKnowledgeGaps } from './insights.js';
export type { SurprisingConnection, KnowledgeGap } from './types.js';
export { applyGraphSearch } from './search.js';
export type { SearchResult } from './search.js';
export { buildWikiGraph, buildRetrievalGraph } from './build.js';
export { calculateRelevance, getRelatedNodes } from './relevance.js';

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

interface CliArgs {
  wiki: string;
  action: string;
  query?: string;
  node?: string;
  codeAnalysis?: string;
  format?: string;
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
    codeAnalysis: args['code-analysis'] || args['code_analysis'],
    format: args['format'],
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

function loadJson(path: string): unknown {
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, 'utf-8'));
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
// Export formats
// ---------------------------------------------------------------------------

function exportGraphAsHtml(
  nodes: { id: string; label: string; domain?: string; [key: string]: unknown }[],
  edges: { source: string; target: string; domain?: string; weight?: number; [key: string]: unknown }[],
): string {
  const edgeColorMap: Record<string, string> = {
    wikilink: '#4a9eff',
    codestructure: '#4caf50',
    cross: '#ff9800',
  };
  const defaultColor = '#9e9e9e';

  const nodeData = JSON.stringify(
    nodes.map((n) => ({ id: n.id, label: n.label, group: n.domain ?? 'unknown' })),
  );
  const edgeData = JSON.stringify(
    edges.map((e) => ({
      from: e.source,
      to: e.target,
      color: { color: edgeColorMap[e.domain ?? ''] ?? defaultColor },
      width: (e.weight ?? 0.5) * 3,
      dashes: e.domain === 'cross',
      title: `domain: ${e.domain ?? 'unknown'}`,
    })),
  );

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>LLM Wiki — Unified Graph</title>
<style>
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #1a1a2e; color: #eee; }
  #mynetwork { width: 100vw; height: 100vh; }
  #legend {
    position: absolute; bottom: 20px; left: 20px;
    background: rgba(26,26,46,0.9); padding: 12px 16px; border-radius: 8px;
    border: 1px solid #333; font-size: 13px;
  }
  .legend-item { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
  .legend-swatch { width: 20px; height: 3px; border-radius: 2px; }
  .legend-line-dash { border-top: 3px dashed; width: 20px; }
</style>
</head>
<body>
<div id="mynetwork"></div>
<div id="legend">
  <div class="legend-item"><span class="legend-swatch" style="background:#4a9eff"></span> Wikilinks</div>
  <div class="legend-item"><span class="legend-swatch" style="background:#4caf50"></span> Code structure</div>
  <div class="legend-item"><span class="legend-swatch" style="background:#ff9800"></span> Cross-graph</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.6/vis-network.min.js"></script>
<script>
  const nodes = new vis.DataSet(${nodeData});
  const edges = new vis.DataSet(${edgeData});
  const container = document.getElementById('mynetwork');
  const data = { nodes, edges };
  const options = {
    nodes: { shape: 'dot', size: 10, font: { color: '#ccc', size: 12 } },
    edges: { smooth: { type: 'continuous' } },
    physics: { solver: 'forceAtlas2Based', forceAtlas2Based: { gravitationalConstant: -40 } },
    interaction: { hover: true, tooltipDelay: 200 },
    background: '#1a1a2e',
  };
  new vis.Network(container, data, options);
</script>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  try {
    const { wiki, action, query, node: nodeId, codeAnalysis, format } = parseArgs();

    if (!wiki || !action) {
      console.error(
        'Usage: node dist/index.js --wiki <path> --action <build|insights|search|relevance|merged|export-graph> [--query <q>] [--node <id>] [--code-analysis <path>] [--format <svg|html|json>]',
      );
      process.exitCode = 1;
      return;
    }

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
        result = await (buildMod as any).buildWikiGraph(wikiPath);
        // Persist graph-data.json in the original wiki root directory
        const outputPath = join(wiki, 'graph-data.json');
        writeFileSync(outputPath, JSON.stringify(result, null, 2), 'utf-8');

        // ── Optional code analysis ─────────────────────────
        if (codeAnalysis) {
          const bridge = await tryImport('@baissari/llm-wiki-graph-bridge');
          if (!bridge || typeof (bridge as any).buildCodeGraph !== 'function') {
            console.warn(JSON.stringify({
              warning: 'Code analysis requested but @baissari/llm-wiki-graph-bridge not available. Install it with: npm install @baissari/llm-wiki-graph-bridge',
            }));
          } else {
            const codeResult = await (bridge as any).buildCodeGraph(codeAnalysis, {
              rootDir: codeAnalysis,
            });
            const codeGraphPath = join(wiki, 'code-graph.json');
            writeFileSync(codeGraphPath, JSON.stringify(codeResult, null, 2), 'utf-8');
            console.warn(JSON.stringify({
              info: `Code analysis complete: ${codeResult.fileCount} files scanned, ${codeResult.nodes.length} nodes, ${codeResult.edges.length} edges`,
              codeGraphPath,
            }));
          }
        }
        break;
      }

      // ── Insights ─────────────────────────────────────────
      case 'insights': {
        const data = loadGraphData(wiki);
        const { findSurprisingConnections, detectKnowledgeGaps } = await import('./insights.js');
        result = {
          surprisingConnections: findSurprisingConnections(data.nodes, data.edges, data.communities),
          knowledgeGaps: detectKnowledgeGaps(data.nodes, data.edges, data.communities),
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
        const relMod = await tryImport('./relevance.js');
        if (
          !relMod ||
          typeof (relMod as any).getRelatedNodes !== 'function' ||
          typeof (relMod as any).buildGraphStructure !== 'function'
        ) {
          throw new Error('Relevance action not available — graph-engine relevance module missing.');
        }
        const structure = (relMod as any).buildGraphStructure(data.edges);
        result = (relMod as any).getRelatedNodes(nodeId, data.nodes, structure, 10);
        break;
      }

      // ── Merged (unified wiki + code graph) ───────────────
      case 'merged': {
        const wikiGraph = loadGraphData(wiki);
        const codeGraphPath = join(wiki, 'code-graph.json');
        const codeGraphRaw = loadJson(codeGraphPath);
        if (!codeGraphRaw) {
          throw new Error(
            `Code graph not found at ${codeGraphPath}. Run with --code-analysis first.`,
          );
        }
        const codeGraph = codeGraphRaw as { nodes: unknown[]; edges: unknown[] };

        const bridge = await import('@baissari/llm-wiki-graph-bridge');
        const mergeResult = (bridge as any).mergeGraphs(
          { nodes: wikiGraph.nodes, edges: wikiGraph.edges },
          { nodes: codeGraph.nodes, edges: codeGraph.edges },
          { crossDomainThreshold: 0.7, matchByPath: true },
        );

        result = mergeResult.graph;
        break;
      }

      // ── Export graph ─────────────────────────────────────
      case 'export-graph': {
        const fmt = format || 'json';
        const wikiGraph = loadGraphData(wiki);

        // Try to load code-graph for export too
        let codeGraphRaw: unknown = null;
        const codePath = join(wiki, 'code-graph.json');
        if (existsSync(codePath)) {
          codeGraphRaw = loadJson(codePath);
        }

        let nodes: { id: string; label: string; domain?: string; [key: string]: unknown }[];
        let edges: { source: string; target: string; domain?: string; weight?: number; [key: string]: unknown }[];

        if (codeGraphRaw) {
          // Use unified graph
          const codeGraph = codeGraphRaw as { nodes: unknown[]; edges: unknown[] };
          const bridge = await import('@baissari/llm-wiki-graph-bridge');
          const mergeResult = (bridge as any).mergeGraphs(
            { nodes: wikiGraph.nodes, edges: wikiGraph.edges },
            { nodes: codeGraph.nodes, edges: codeGraph.edges },
            { crossDomainThreshold: 0.7, matchByPath: true },
          );
          nodes = mergeResult.graph.merged.nodes;
          edges = mergeResult.graph.merged.edges;
        } else {
          // Wiki graph only
          nodes = wikiGraph.nodes as unknown as { id: string; label: string; domain?: string; [key: string]: unknown }[];
          edges = wikiGraph.edges as unknown as { source: string; target: string; domain?: string; weight?: number; [key: string]: unknown }[];
        }

        switch (fmt) {
          case 'html': {
            const html = exportGraphAsHtml(nodes, edges);
            const htmlPath = join(wiki, 'graph-export.html');
            writeFileSync(htmlPath, html, 'utf-8');
            result = { format: 'html', path: htmlPath };
            break;
          }
          case 'svg': {
            // For SVG, we output a basic summary since vis.js requires a browser
            // Full SVG export would need a headless browser — this is a placeholder
            // that generates a data-URI with the vis.js network
            const html = exportGraphAsHtml(nodes, edges);
            result = {
              format: 'svg',
              warning: 'Full SVG export requires a headless browser. Use --format html for an interactive view, or pipe the JSON for programmatic SVG generation.',
              nodeCount: nodes.length,
              edgeCount: edges.length,
            };
            break;
          }
          case 'json':
          default: {
            result = { nodes, edges };
            break;
          }
        }
        break;
      }

      default: {
        throw new Error(
          `Unknown action: "${action}". Valid actions: build, insights, search, relevance, merged, export-graph.`,
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
