declare module "@baissari/llm-wiki-graph-bridge" {
  export function buildCodeGraph(
    root: string,
    options?: Record<string, unknown>,
  ): Promise<{
    fileCount: number;
    nodes: unknown[];
    edges: unknown[];
    [key: string]: unknown;
  }>;

  export function mergeGraphs(
    wikiGraph: { nodes: unknown[]; edges: unknown[] },
    codeGraph: { nodes: unknown[]; edges: unknown[] },
    options?: Record<string, unknown>,
  ): {
    graph: {
      merged: {
        nodes: unknown[];
        edges: unknown[];
      };
    };
    [key: string]: unknown;
  };
}
