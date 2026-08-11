import { describe, it, expect } from "vitest";
import { MultiGraph } from "graphology";
import {
  buildSigmaGraph,
  layoutGraph,
  endPointId,
} from "../client/sigma-view.js";
import type { GraphData, DerivedEdge } from "../client/graph.js";

/** Deterministic synthetic graph at benchmark `SIZES` scale (500 pages). */
function makeGraph(pageCount: number, edgeCount: number): GraphData {
  const nodes: GraphData["nodes"] = [];
  for (let i = 0; i < pageCount; i++) {
    nodes.push({
      id: `wiki/pages/page${i}.md`,
      label: `page${i}`,
      path: `wiki/pages/page${i}.md`,
      group: "concepts",
      degree: 0,
      title: `Page ${i}`,
    });
  }
  const edges: GraphData["edges"] = [];
  for (let i = 0; i < edgeCount; i++) {
    const a = i % pageCount;
    const b = (i * 7 + 3) % pageCount;
    if (a !== b) {
      edges.push({
        source: `wiki/pages/page${a}.md`,
        target: `wiki/pages/page${b}.md`,
      });
    }
  }
  return { nodes, edges };
}

describe("sigma view — graph construction", () => {
  it("loads a 500-page-class fixture without layout regressions", () => {
    const data = makeGraph(500, 700);

    const started = performance.now();
    const positions = layoutGraph(data);
    const layoutMs = performance.now() - started;

    expect(positions.size).toBe(500);
    for (const n of data.nodes) {
      expect(positions.has(n.id)).toBe(true);
      const p = positions.get(n.id)!;
      expect(typeof p.x).toBe("number");
      expect(typeof p.y).toBe("number");
    }
    // A synchronous 300-tick force layout at this scale must complete within a
    // generous clock bound (the real property is correctness + finite positions,
    // not wall-clock; tight bounds flake under CI load — repo de-flake precedent).
    expect(layoutMs).toBeLessThan(15000);
  });

  it("builds a MultiGraph with all canonical nodes and edges", () => {
    const data = makeGraph(500, 700);
    const graph = buildSigmaGraph(data, []);
    expect(graph).toBeInstanceOf(MultiGraph);
    expect(graph.order).toBe(500);
    expect(graph.size).toBe(700);
  });

  it("adds derived edges with layer + distinct color, allowing parallel edges", () => {
    const data = makeGraph(10, 15);
    const derived: DerivedEdge[] = [
      { source: "wiki/pages/page0.md", target: "wiki/pages/page1.md", layer: "derived", relType: "similar_to", weight: 0.9 },
      { source: "wiki/pages/page2.md", target: "wiki/pages/page9.md", layer: "derived", relType: "co_occurs_with", weight: 0.6 },
    ];
    const graph = buildSigmaGraph(data, derived);
    // 10 nodes + 2 derived edges added (parallel edges allowed by MultiGraph)
    expect(graph.order).toBe(10);
    expect(graph.size).toBe(15 + 2);

    let derivedFound = 0;
    graph.forEachEdge((_edge, _attrs, _s, _t, s, t) => {
      const attrs = graph.getEdgeAttributes(_edge) as unknown as { layer: string; color: string; label: string };
      if (attrs.layer === "derived") {
        derivedFound += 1;
        expect(attrs.color).toBe("#cba6f7");
        expect(attrs.label).toMatch(/^derived · /);
      }
      void _attrs;
      void _s;
      void _t;
      void s;
      void t;
    });
    expect(derivedFound).toBe(2);
  });

  it("resolves string and object endpoints in edges", () => {
    const edgeString = { source: "a", target: "b" };
    const edgeObj = { source: { id: "a" }, target: { id: "b" } };
    expect(endPointId(edgeString, "source")).toBe("a");
    expect(endPointId(edgeString, "target")).toBe("b");
    expect(endPointId(edgeObj, "source")).toBe("a");
    expect(endPointId(edgeObj, "target")).toBe("b");
  });

  it("derived edges may share endpoints with canonical edges without replacing them", () => {
    const data: GraphData = {
      nodes: [
        { id: "a", label: "A", path: "a", group: "other", degree: 1, title: null },
        { id: "b", label: "B", path: "b", group: "other", degree: 1, title: null },
      ],
      edges: [{ source: "a", target: "b" }],
    };
    const derived: DerivedEdge[] = [{ source: "a", target: "b", layer: "derived", relType: "similar_to", weight: 0.5 }];
    const graph = buildSigmaGraph(data, derived);
    expect(graph.order).toBe(2);
    expect(graph.size).toBe(2); // wikilink + derived, both preserved
    expect(graph.edges("a", "b")).toHaveLength(2); // parallel edges kept
  });
});
