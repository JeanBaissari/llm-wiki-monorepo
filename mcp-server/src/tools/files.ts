import * as path from "node:path";
import { getProjectConfig, textResult, errorResult, sourcesDir, ToolResult } from "../projects/config.js";
import { listDirectory, fileExists } from "../wiki-fs.js";

export async function handleFiles(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const root = (args.root as string) ?? "wiki";
    const recursive = (args.recursive as boolean) !== false;

    const dirs: { label: string; dir: string }[] = [];
    if (root === "wiki" || root === "all") {
      dirs.push({ label: "wiki", dir: layout.pages_dir });
    }
    if (root === "sources" || root === "all") {
      dirs.push({ label: "sources", dir: sourcesDir(layout) });
    }

    const lines: string[] = [];

    for (const { label, dir } of dirs) {
      const exists = await fileExists(dir);
      if (!exists) {
        lines.push(`## ${label}/ (directory not found)`);
        continue;
      }

      const { files, truncated } = await listDirectory(dir, recursive);
      lines.push(`## ${label}/`);
      if (files.length === 0) {
        lines.push("  _(empty)_");
      } else {
        for (const file of files) {
          const prefix = file.is_dir ? "📁" : "📄";
          const relPath = path.relative(dir, file.path);
          lines.push(`  ${prefix} ${relPath}`);
        }
        if (truncated) {
          lines.push(`  _… (truncated, more files exist)_`);
        }
      }
      lines.push("");
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Failed to list files: ${e}`);
  }
}
