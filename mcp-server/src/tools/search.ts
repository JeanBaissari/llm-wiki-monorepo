import * as path from "node:path";
import { getProjectConfig, textResult, errorResult, ToolResult } from "../projects/config.js";
import { search } from "../search.js";

export async function handleSearch(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const query = args.query as string | undefined;
    if (!query || query.trim() === "") {
      return errorResult("Missing required argument: query");
    }

    const topK = Math.min(Math.max((args.top_k as number) ?? 10, 1), 100);

    const results = await search(layout.root, query, topK);

    if (results.length === 0) {
      return textResult(
        `# Search Results\n\nNo results found for "${query}".`,
      );
    }

    const lines: string[] = [
      `# Search Results for "${query}" (${results.length})`,
      "",
    ];

    for (let i = 0; i < results.length; i++) {
      const r = results[i];
      const relPath = path.relative(layout.root, r.path);
      lines.push(
        `### ${i + 1}. ${r.title}`,
        `**Path:** \`${relPath}\`  **Score:** ${r.score.toFixed(4)}`,
        `${r.snippet || "(no snippet)"}`,
        "",
      );
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Search failed: ${e}`);
  }
}
