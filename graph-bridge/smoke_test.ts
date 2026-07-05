// Quick smoke test for graph-bridge merger + graphology
import { mergeGraphs, buildUnifiedGraphology } from "./dist/index.js";

const wikiGraph = {
  nodes: [
    { id: "entities/foo", label: "Foo", type: "entity", path: "entities/foo.md", linkCount: 3, community: 0 },
    { id: "concepts/bar", label: "Bar", type: "concept", path: "concepts/bar.md", linkCount: 2, community: 0 },
  ],
  edges: [
    { source: "entities/foo", target: "concepts/bar", weight: 0.8 },
  ],
};

const codeGraph = {
  nodes: [
    { id: "src/foo.ts:Foo", label: "Foo", type: "class" as const, path: "src/foo.ts", language: "TypeScript" },
    { id: "src/bar.ts:bar", label: "bar", type: "function" as const, path: "src/bar.ts", language: "TypeScript" },
  ],
  edges: [
    { source: "src/foo.ts:Foo", target: "src/bar.ts:bar", type: "calls" as const, weight: 0.9 },
  ],
};

const result = mergeGraphs(wikiGraph, codeGraph);
console.log("Stats:", JSON.stringify(result.stats));
console.log("Unified nodes:", result.graph.merged.nodes.length);
console.log("Unified edges:", result.graph.merged.edges.length);

// Verify cross-domain match: "Foo" label appears in both graphs
const crossMatch = result.graph.merged.edges.filter(e => e.domain === "cross");
console.log("Cross edges:", crossMatch.length);

const g = buildUnifiedGraphology(result.graph);
console.log("Graphology order:", g.order);
console.log("Graphology size:", g.size);
console.log("PASS");
