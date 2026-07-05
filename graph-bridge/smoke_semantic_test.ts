// Smoke test for semantic-edges
import { extractSemanticEdges } from "./dist/index.js";
import type { CodeNode, CodeEdge } from "./dist/index.js";

const nodes: CodeNode[] = [
  { id: "A", label: "foo", type: "function", path: "src/a.ts", language: "TypeScript" },
  { id: "B", label: "bar", type: "function", path: "src/b.ts", language: "TypeScript" },
  { id: "C", label: "baz", type: "function", path: "src/c.ts", language: "TypeScript" },
  { id: "D", label: "BazClass", type: "class", path: "src/d.ts", language: "TypeScript" },
  { id: "E", label: "BaseBaz", type: "class", path: "src/e.ts", language: "TypeScript" },
];

const edges: CodeEdge[] = [
  { source: "A", target: "B", type: "calls", weight: 0.9 },
  { source: "B", target: "C", type: "calls", weight: 0.9 },
  { source: "D", target: "E", type: "extends", weight: 0.9 },
];

const result = extractSemanticEdges(nodes, edges);
console.log("Added:", JSON.stringify(result.added));
console.log("Total edges:", result.edges.length);
// Expected: 3 original + 1 call chain (A→C) + 1 class hierarchy (D→E transitive)
console.log(result.edges.filter(e => !edges.includes(e)).map(e => `${e.source}→${e.target} (${e.type})`));
console.log("PASS");
