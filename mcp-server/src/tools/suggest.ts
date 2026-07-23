import { getProjectConfig, textResult, errorResult, tryImport, ToolResult } from "../projects/config.js";
import { getSidecar } from "../registry.js";
import type { PythonSidecar } from "../adapters/sidecar.js";
import type { SuggestResult } from "../suggest.js";

export async function handleSuggestLinks(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);

    const sidecar = getSidecar();
    if (!sidecar?.isRunning()) {
      return errorResult(
        "Python sidecar is not running — cannot suggest links. The sidecar may have failed to start.",
      );
    }

    const suggestMod = await tryImport<{
      suggestLinks: (
        sidecar: PythonSidecar,
        wikiPath: string,
        options: { threshold?: number; limit?: number; pages?: string[] },
      ) => Promise<SuggestResult>;
    }>("../suggest.js");

    if (!suggestMod?.suggestLinks) {
      return textResult(
        "# Suggest Links\n\n_Suggest module not available. Install or build src/suggest.ts._",
      );
    }

    const threshold = (args.threshold as number) ?? 0.3;
    const limit = (args.limit as number) ?? 20;
    const pages = args.pages as string[] | undefined;

    const result = await suggestMod.suggestLinks(sidecar, layout.root, {
      threshold,
      limit,
      pages,
    });

    if (!result.suggestions || result.suggestions.length === 0) {
      return textResult("# Link Suggestions\n\nNo suggestions found.");
    }

    const lines: string[] = [
      `# Link Suggestions (${result.total})`,
      "",
    ];

    for (let i = 0; i < result.suggestions.length; i++) {
      const s = result.suggestions[i];
      lines.push(
        `### ${i + 1}. ${s.source_title} → ${s.target_title}`,
        `**Score:** ${s.score.toFixed(3)} | **Entity:** \`${s.entity}\` | **Reason:** ${s.reason}`,
        `**Source:** \`${s.source}\` → **Target:** \`${s.target}\``,
        "",
      );
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Suggest links failed: ${e}`);
  }
}
