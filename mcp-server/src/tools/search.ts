import * as path from "node:path";
import { getProjectConfig, textResult, errorResult, ToolResult } from "../projects/config.js";
import { getSidecar } from "../registry.js";
import { search } from "../search.js";

export async function handleSearch(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const query = args.query as string | undefined;
    if (!query || query.trim() === "") {
      return errorResult("Missing required argument: query");
    }

    const topK = Math.min(Math.max((args.top_k as number) ?? 10, 1), 100);

    // Hybrid mode (opt-in, LWM_020): fuse keyword + semantic via the Python
    // sidecar. Any unavailability/error falls through to the byte-identical
    // keyword path below, so the default is never affected.
    if ((args.mode as string) === "hybrid") {
      const sidecar = getSidecar();
      if (sidecar?.isRunning()) {
        try {
          const res = (await sidecar.call("hybrid_search", {
            wiki_root: layout.root,
            query,
            top_k: topK,
          })) as {
            results?: Array<{ path: string; title: string; snippet?: string; matched?: string }>;
            error?: string;
          };
          if (!res.error && Array.isArray(res.results)) {
            if (res.results.length === 0) {
              return textResult(`# Search Results\n\nNo results found for "${query}".`);
            }
            const hlines: string[] = [
              `# Hybrid Search Results for "${query}" (${res.results.length})`,
              "",
            ];
            for (let i = 0; i < res.results.length; i++) {
              const r = res.results[i];
              const tag = r.matched ? ` _[${r.matched}]_` : "";
              hlines.push(
                `### ${i + 1}. ${r.title}${tag}`,
                `**Path:** \`${r.path}\``,
                `${r.snippet || "(no snippet)"}`,
                "",
              );
            }
            return textResult(hlines.join("\n"));
          }
        } catch {
          // fall through to keyword
        }
      }
      // sidecar unavailable/failed → keyword fallback below
    }

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
