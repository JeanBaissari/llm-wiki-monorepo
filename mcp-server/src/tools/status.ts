import * as path from "node:path";
import { getProjectConfig, textResult, errorResult, tryImport, ToolResult } from "../projects/config.js";
import { findMdFiles, fileExists, readFile } from "../wiki-fs.js";
import { getSidecar } from "../registry.js";

export async function handleStatus(args: Record<string, unknown> = {}): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const exists = await fileExists(wp);
    if (!exists) {
      return textResult(
        `# LLM Wiki Status\n\n**Health:** ❌ Wiki directory not found\n**Path:** \`${wp}\``,
      );
    }

    const pages = await findMdFiles(layout.pages_dir);
    const pageCount = pages.length;

    let lastIngest: string | null = null;
    try {
      const metaPath = path.join(wp, "..", ".wiki-meta.json");
      if (await fileExists(metaPath)) {
        const raw = await readFile(metaPath);
        const meta = JSON.parse(raw);
        lastIngest = meta.lastIngest ?? null;
      }
    } catch {
      // ignore
    }

    let openReviews = 0;
    const reviewMod = await tryImport<{
      listReviews: (wp: string, status?: string) => Promise<{ status: string }[]>;
    }>("../review.js");
    if (reviewMod?.listReviews) {
      try {
        const reviews = await reviewMod.listReviews(layout.audit_dir ?? wp);
        openReviews = reviews.filter((r) => r.status === "open").length;
      } catch {
        // ignore
      }
    }

    const sidecar = getSidecar();
    const healthEmoji = pageCount > 0 ? "✅ Operational" : "⚠️  No pages found";
    const projectName = (args.project as string) || "default";

    return textResult(
      [
        "# LLM Wiki Status",
        "",
        `**Project:** ${projectName}`,
        `**Health:** ${healthEmoji}`,
        `**Wiki Path:** \`${wp}\``,
        `**Page Count:** ${pageCount}`,
        `**Last Ingest:** ${lastIngest ?? "Never"}`,
        `**Open Reviews:** ${openReviews}`,
        `**Sidecar:** ${sidecar?.isRunning() ? "✅ Running" : "⚠️  Not running"}`,
      ].join("\n"),
    );
  } catch (e) {
    return errorResult(`Failed to get status: ${e}`);
  }
}
