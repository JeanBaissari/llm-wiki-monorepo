import { getProjectConfig, textResult, errorResult, tryImport, ToolResult } from "../projects/config.js";

export async function handleGraph(args: Record<string, unknown>): Promise<ToolResult> {
  const action = (args.action as string) ?? "build";

  switch (action) {
    case "build":
      return handleGraphBuild(args);
    case "insights":
      return handleGraphInsights(args);
    case "search":
      return handleGraphSearch(args);
    default:
      return errorResult(
        `Unknown graph action: "${action}". Use "build", "insights", or "search".`,
      );
  }
}

export async function handleGraphBuild(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);

    const graphMod = await tryImport<{
      buildGraph: (wp: string) => Promise<{ nodes: { id: string; label: string }[]; edges: { source: string; target: string }[] }>;
    }>("../adapters/graph-engine.js");

    if (!graphMod?.buildGraph) {
      return textResult(
        "# Graph: build\n\n_Graph module not available. Install or build src/graph.ts._",
      );
    }

    const result = await graphMod.buildGraph(layout.pages_dir);
    return textResult(
      [
        "# Graph Build Complete",
        "",
        `**Nodes:** ${result.nodes.length}`,
        `**Edges:** ${result.edges.length}`,
        "",
        "The knowledge graph has been rebuilt from the wiki content.",
      ].join("\n"),
    );
  } catch (e) {
    return errorResult(`Graph build failed: ${e}`);
  }
}

export async function handleGraphInsights(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);

    const graphMod = await tryImport<{
      getInsights: (wp: string) => Promise<string[]>;
    }>("../adapters/graph-engine.js");

    if (!graphMod?.getInsights) {
      return textResult(
        "# Graph: insights\n\n_Graph module not available. Install or build src/graph.ts._",
      );
    }

    const insights = await graphMod.getInsights(layout.pages_dir);
    if (!insights || (Array.isArray(insights) && insights.length === 0)) {
      return textResult("# Graph Insights\n\nNo insights available.");
    }

    // Handle both old (string[]) and new (object) return formats
    if (Array.isArray(insights)) {
      const lines: string[] = ["# Graph Insights", ""];
      for (let i = 0; i < insights.length; i++) {
        lines.push(`${i + 1}. ${insights[i]}`);
      }
      return textResult(lines.join("\n"));
    }

    // Structured format from LWM_07
    const data = insights as unknown as {
      surprisingConnections?: Array<{ source: any; target: any; score: number; reasons: string[] }>;
      knowledgeGaps?: Array<{ title: string; description: string; suggestion: string }>;
    };

    const lines: string[] = ["# Graph Insights", ""];

    if (data.surprisingConnections?.length) {
      lines.push(`## Surprising Connections (${data.surprisingConnections.length})`, "");
      for (const sc of data.surprisingConnections) {
        const srcLabel = sc.source?.label ?? sc.source?.id ?? "?";
        const tgtLabel = sc.target?.label ?? sc.target?.id ?? "?";
        lines.push(`- **${srcLabel}** ↔ **${tgtLabel}** (score: ${sc.score.toFixed(2)})`);
        if (sc.reasons?.length) {
          lines.push(`  _${sc.reasons.join(", ")}_`);
        }
      }
      lines.push("");
    }

    if (data.knowledgeGaps?.length) {
      lines.push(`## Knowledge Gaps (${data.knowledgeGaps.length})`, "");
      for (const kg of data.knowledgeGaps) {
        lines.push(`- **${kg.title}**: ${kg.description}`);
        if (kg.suggestion) lines.push(`  → ${kg.suggestion}`);
      }
      lines.push("");
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Graph insights failed: ${e}`);
  }
}

export async function handleGraphSearch(args: Record<string, unknown>): Promise<ToolResult> {
  const query = args.query as string | undefined;
  if (!query || query.trim() === "") {
    return errorResult("Missing required argument: query for graph search");
  }

  try {
    const { root: wp, layout } = getProjectConfig(args);

    const graphMod = await tryImport<{
      searchGraph: (wp: string, q: string) => Promise<{
        nodes: { id: string; label: string; type: string; path: string; linkCount: number; community: number }[];
        edges: any[];
        matchedNodeIds: string[];
      }>;
    }>("../adapters/graph-engine.js");

    if (!graphMod?.searchGraph) {
      return textResult(
        "# Graph: search\n\n_Graph module not available. Install or build src/graph.ts._",
      );
    }

    const graphResult = await graphMod.searchGraph(layout.pages_dir, query);

    if (!graphResult || !graphResult.nodes || graphResult.nodes.length === 0) {
      return textResult(`# Graph Search: "${query}"\n\nNo results found.`);
    }

    const lines: string[] = [
      `# Graph Search Results for "${query}" (${graphResult.nodes.length})`,
      "",
    ];
    for (const r of graphResult.nodes) {
      lines.push(`- **${r.label}** (\`${r.id}\`)`);
    }
    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Graph search failed: ${e}`);
  }
}
