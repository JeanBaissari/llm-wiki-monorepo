import { describe, expect, expectTypeOf, it } from "vitest";
import type {
  CommunityInfo,
  GraphData,
  GraphEdge,
  GraphNode,
} from "./index.js";
import * as sharedTypes from "./index.js";

describe("shared-types runtime surface", () => {
  it("loads as a valid ES module", () => {
    expect(sharedTypes).toBeTypeOf("object");
  });
});

describe("GraphNode", () => {
  it("matches the canonical wiki node shape", () => {
    const node: GraphNode = {
      id: "concept-attention",
      label: "Attention Mechanism",
      type: "concept",
      path: "wiki/concepts/attention_mechanism.md",
      linkCount: 7,
      community: 2,
    };

    expect(node.linkCount).toBe(7);
    expect(node.community).toBe(2);

    expectTypeOf<GraphNode["id"]>().toBeString();
    expectTypeOf<GraphNode["label"]>().toBeString();
    expectTypeOf<GraphNode["type"]>().toBeString();
    expectTypeOf<GraphNode["path"]>().toBeString();
    expectTypeOf<GraphNode["linkCount"]>().toBeNumber();
    expectTypeOf<GraphNode["community"]>().toBeNumber();
    expectTypeOf<GraphNode["sources"]>().toEqualTypeOf<string[] | undefined>();
  });
});

describe("GraphEdge", () => {
  it("keeps the legacy triple valid and admits optional v0.5.0 fields", () => {
    const legacy: GraphEdge = { source: "a", target: "b", weight: 1 };
    expect(legacy.weight).toBe(1);

    const extended: GraphEdge = {
      source: "a",
      target: "b",
      weight: 2,
      relType: "cites",
      directed: true,
      validFrom: "2026-01-01T00:00:00Z",
      validTo: "2026-12-31T00:00:00Z",
      observedAt: "2026-01-01T00:00:00Z",
    };
    expect(extended.directed).toBe(true);

    expectTypeOf<GraphEdge["source"]>().toBeString();
    expectTypeOf<GraphEdge["target"]>().toBeString();
    expectTypeOf<GraphEdge["weight"]>().toBeNumber();
    expectTypeOf<GraphEdge["relType"]>().toEqualTypeOf<string | undefined>();
    expectTypeOf<GraphEdge["directed"]>().toEqualTypeOf<boolean | undefined>();
    expectTypeOf<GraphEdge["validFrom"]>().toEqualTypeOf<string | undefined>();
    expectTypeOf<GraphEdge["validTo"]>().toEqualTypeOf<string | undefined>();
    expectTypeOf<GraphEdge["observedAt"]>().toEqualTypeOf<string | undefined>();
  });
});

describe("CommunityInfo", () => {
  it("matches the Louvain community shape", () => {
    const community: CommunityInfo = {
      id: 3,
      nodeCount: 12,
      cohesion: 0.72,
      topNodes: ["Attention Mechanism", "Transformer Architecture"],
    };

    expect(community.topNodes).toHaveLength(2);
    expect(community.cohesion).toBeCloseTo(0.72);

    expectTypeOf<CommunityInfo>().toEqualTypeOf<{
      id: number;
      nodeCount: number;
      cohesion: number;
      topNodes: string[];
    }>();
  });
});

describe("GraphData", () => {
  it("is the canonical aggregation of nodes, edges, and communities", () => {
    const data: GraphData = { nodes: [], edges: [], communities: [] };

    expect(data.nodes).toHaveLength(0);

    expectTypeOf<GraphData["nodes"]>().toEqualTypeOf<GraphNode[]>();
    expectTypeOf<GraphData["edges"]>().toEqualTypeOf<GraphEdge[]>();
    expectTypeOf<GraphData["communities"]>().toEqualTypeOf<CommunityInfo[]>();
  });
});
