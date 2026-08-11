import Sigma from "sigma";
import { MultiGraph } from "graphology";
import * as d3force from "d3-force";
import type { GraphData, GraphEdge, GraphNode, DerivedEdge, DerivedOverlayData } from "./graph.js";

export interface SigmaViewOptions {
  onNodeClick?: (node: GraphNode) => void;
}

const GROUP_COLORS: Record<string, string> = {
  concepts: "#89b4fa",
  entities: "#fab387",
  summaries: "#94e2d5",
  other: "#7f849c",
};
const CANONICAL_EDGE_COLOR = "rgba(180, 190, 254, 0.35)";
const DERIVED_EDGE_COLOR = "#cba6f7";

/**
 * Run a short d3-force layout synchronously and return per-node positions.
 * Pure computation — no DOM/WebGL — so it is safe to use in tests and gives
 * the WebGL view a stable initial layout at any graph size (including the
 * 500-page-class benchmark scale).
 */
export function layoutGraph(data: GraphData): Map<string, { x: number; y: number }> {
  const nodes: GraphNode[] = data.nodes.map((n) => ({ ...n }));
  const links: GraphEdge[] = data.edges.map((e) => ({ ...e }));

  const sim = d3force
    .forceSimulation<GraphNode>(nodes)
    .force(
      "link",
      d3force
        .forceLink<GraphNode, GraphEdge>(links)
        .id((d) => d.id)
        .distance(120)
        .strength(0.3),
    )
    .force("charge", d3force.forceManyBody<GraphNode>().strength(-120).distanceMax(600))
    .force("center", d3force.forceCenter(0, 0))
    .stop();

  for (let i = 0; i < 300; i++) sim.tick();

  const positions = new Map<string, { x: number; y: number }>();
  for (const n of nodes) positions.set(n.id, { x: n.x ?? 0, y: n.y ?? 0 });
  return positions;
}

export const endPointId = (e: GraphEdge, which: "source" | "target"): string => {
  const v = e[which];
  return typeof v === "string" ? v : v.id;
};

/**
 * Build a graphology MultiGraph (canonical + optional derived edges) suitable
 * for Sigma. Derived edges keep `layer: "derived"` and a distinct color;
 * canonical edges carry `layer: "wikilink"`. A MultiGraph is used so a
 * derived edge may share endpoints with a canonical edge.
 */
export function buildSigmaGraph(data: GraphData, derivedEdges: DerivedEdge[]): MultiGraph {
  const positions = layoutGraph(data);
  const graph = new MultiGraph();

  for (const n of data.nodes) {
    const p = positions.get(n.id) ?? { x: 0, y: 0 };
    graph.addNode(n.id, {
      label: n.title || n.label,
      x: p.x,
      y: p.y,
      size: Math.min(28, 6 + Math.sqrt(n.degree) * 2.2),
      color: GROUP_COLORS[n.group] ?? GROUP_COLORS["other"],
    });
  }

  data.edges.forEach((e, i) => {
    graph.addEdge(endPointId(e, "source"), endPointId(e, "target"), {
      label: "wikilink",
      color: CANONICAL_EDGE_COLOR,
      size: 1.2,
      layer: "wikilink",
    });
  });
  derivedEdges.forEach((e, i) => {
    graph.addEdge(endPointId(e, "source"), endPointId(e, "target"), {
      label: `derived · ${e.relType}`,
      color: DERIVED_EDGE_COLOR,
      size: 1,
      layer: "derived",
    });
  });

  return graph;
}

/**
 * WebGL graph view backed by Sigma. Zoom/pan are provided by Sigma's default
 * camera controls. The SVG mode remains available alongside this view; the
 * page markdown render path (mermaid + KaTeX) is untouched.
 */
export class SigmaView {
  private sigma: Sigma | null = null;
  private nodeById = new Map<string, GraphNode>();

  constructor(
    container: HTMLElement,
    data: GraphData,
    derived: DerivedOverlayData | null,
    enabled: boolean,
    opts: SigmaViewOptions = {},
  ) {
    this.nodeById = new Map(data.nodes.map((n) => [n.id, n]));
    const derivedEdges = enabled && derived && derived.available ? derived.edges : [];
    const graph = buildSigmaGraph(data, derivedEdges);

    this.sigma = new Sigma(graph, container, {
      renderLabels: true,
      renderEdgeLabels: false,
      labelFont: "Inter, system-ui, sans-serif",
      labelSize: 12,
      labelColor: { color: "#cdd6f4" },
      defaultNodeType: "circle",
      defaultEdgeType: "line",
      minCameraRatio: 0.05,
      maxCameraRatio: 8,
      autoRescale: true,
      autoCenter: true,
      allowInvalidContainer: true,
    });

    this.sigma.on("clickNode", ({ node }) => {
      const gn = this.nodeById.get(node);
      if (gn) opts.onNodeClick?.(gn);
    });
  }

  get graph(): MultiGraph | null {
    return this.sigma ? this.sigma.getGraph() : null;
  }

  destroy(): void {
    if (this.sigma) {
      this.sigma.kill();
      this.sigma = null;
    }
  }
}
