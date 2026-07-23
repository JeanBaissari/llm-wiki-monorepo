import { getProjectConfig, textResult, errorResult, tryImport, ToolResult } from "../projects/config.js";

export async function handleReviews(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const reviewMod = await tryImport<{
      listReviews: (
        wp: string,
        status?: string,
      ) => Promise<
        {
          id: string;
          title: string;
          type: string;
          severity: string;
          status: string;
          description: string;
          created: string;
          author: string;
        }[]
      >;
    }>("../review.js");

    if (!reviewMod?.listReviews) {
      return textResult(
        "# LLM Wiki Reviews\n\n_Review module not available. Install or build src/review.ts._",
      );
    }

    const status = (args.status as string) ?? "all";
    const reviews = await reviewMod.listReviews(layout.audit_dir ?? wp, status);

    if (reviews.length === 0) {
      return textResult(
        `# LLM Wiki Reviews\n\nNo reviews found${status !== "all" ? ` with status "${status}"` : ""}.`,
      );
    }

    const lines: string[] = [
      `# LLM Wiki Reviews (${reviews.length})`,
      "",
    ];

    for (const r of reviews) {
      const statusEmoji = r.status === "open" ? "🔴" : "✅";
      const severityTag =
        r.severity === "error"
          ? "**ERROR**"
          : r.severity === "warn"
            ? "*WARN*"
            : r.severity === "suggest"
              ? "_suggest_"
              : "info";
      lines.push(
        `### ${statusEmoji} ${r.title}`,
        `**ID:** \`${r.id}\`  **Type:** ${r.type}  **Severity:** ${severityTag}  **Status:** ${r.status}`,
        `**Author:** ${r.author}  **Created:** ${r.created}`,
        `**Description:** ${r.description}`,
        "",
      );
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Failed to list reviews: ${e}`);
  }
}
