// Verification: merger + graphology + semantic-edges
import { mergeGraphs, buildUnifiedGraphology, extractSemanticEdges } from "./dist/index.js";
import type { CodeNode, CodeEdge } from "./dist/index.js";

let passed = 0, failed = 0;
function assert(cond: boolean, msg: string) {
  if (cond) { passed++; console.log(`  ✓ ${msg}`); }
  else { failed++; console.log(`  ✗ ${msg}`); }
}

// ── Merger ──────────────────────────────────────────────────
console.log("merger:");
const wiki = {
  nodes: [{ id: "entities/foo", label: "Foo", type: "entity", path: "entities/foo.md", linkCount: 3, community: 0 },
          { id: "concepts/bar", label: "Bar", type: "concept", path: "concepts/bar.md", linkCount: 2, community: 0 }],
  edges: [{ source: "entities/foo", target: "concepts/bar", weight: 0.8 }],
};
const code = {
  nodes: [{ id: "src/foo.ts:Foo", label: "Foo", type: "class" as const, path: "src/foo.ts", language: "TypeScript" },
          { id: "src/bar.ts:bar", label: "bar", type: "function" as const, path: "src/bar.ts", language: "TypeScript" }],
  edges: [{ source: "src/foo.ts:Foo", target: "src/bar.ts:bar", type: "calls" as const, weight: 0.9 }],
};

const r = mergeGraphs(wiki, code);
assert(r.stats.wikiNodes === 2, "wikiNodes=2");
assert(r.stats.codeNodes === 2, "codeNodes=2");
assert(r.stats.mergedNodes === 2, "mergedNodes=2 (both Foo and bar/Bar match)");
assert(r.stats.crossEdges >= 1, "crossEdges >= 1");
assert(r.graph.merged.nodes.length > 0, "merged.nodes non-empty");
assert(r.graph.merged.edges.length > 0, "merged.edges non-empty");

const g = buildUnifiedGraphology(r.graph);
assert(g.order >= 1, `graphology order=${g.order} >= 1`);
assert(g.size >= 1, `graphology size=${g.size} >= 1`);

// ── Semantic edges ──────────────────────────────────────────
console.log("semantic-edges:");
const snodes: CodeNode[] = [
  { id: "A", label: "foo", type: "function", path: "src/a.ts", language: "TypeScript" },
  { id: "B", label: "bar", type: "function", path: "src/b.ts", language: "TypeScript" },
  { id: "C", label: "baz", type: "function", path: "src/c.ts", language: "TypeScript" },
];
const sedges: CodeEdge[] = [
  { source: "A", target: "B", type: "calls", weight: 0.9 },
  { source: "B", target: "C", type: "calls", weight: 0.9 },
];

const sr = extractSemanticEdges(snodes, sedges);
assert(sr.added.callChains === 1, "callChains=1 (A→C transitive)");
assert(sr.added.classHierarchies === 0, "classHierarchies=0");
assert(sr.edges.length === 4, "total edges = 4 (3 original + 1 inferred)");

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
