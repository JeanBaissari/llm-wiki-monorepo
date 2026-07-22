/**
 * ts_louvain_runner.ts
 *
 * Standalone CLI script to run TypeScript Louvain community detection
 * from a graph fixture JSON file and optional seed.
 *
 * Usage:
 *   npx tsx graph-engine/scripts/ts_louvain_runner.ts \
 *     tests/fixtures/graphs/two_clique.json 42
 *
 * Output (stdout):
 *   {"graph":"two_clique","seed":42,"assignments":{"n0":0,"n1":1,...}}
 *
 * This script is invoked by the Python verification harness (run_verification.py)
 * to compare TS vs Python Louvain results.
 */

import { readFileSync } from "fs";
import { detectCommunities } from "../src/louvain.js";

interface GraphFixture {
  name: string;
  nodes: string[];
  edges: Array<{ source: string; target: string; weight: number }>;
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    console.error("Usage: ts_louvain_runner.ts <graph.json> [seed]");
    process.exit(1);
  }

  const graphPath = args[0];
  const seed = args[1] !== undefined ? parseInt(args[1], 10) : undefined;

  // Read graph fixture
  const raw = readFileSync(graphPath, "utf-8");
  const graph: GraphFixture = JSON.parse(raw);

  // Convert to GraphNode[] / GraphEdge[] format expected by detectCommunities
  const nodes = graph.nodes.map((id) => ({
    id,
    label: id,
    linkCount: 0,
    community: 0,
    path: `${id}.md`,
    type: "entity",
  }));

  const edges = graph.edges;

  // Run community detection with seed
  const result = detectCommunities(nodes as any, edges, { seed });
  const assignmentsObj: Record<string, number> = {};
  for (const [node, community] of result.assignments) {
    assignmentsObj[node] = community;
  }

  // Output JSON
  const output = {
    graph: graph.name,
    seed: seed ?? null,
    nodeCount: graph.nodes.length,
    edgeCount: graph.edges.length,
    communityCount: result.communities.length,
    assignments: assignmentsObj,
  };

  console.log(JSON.stringify(output));
}

main();
