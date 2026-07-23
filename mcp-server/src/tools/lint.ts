import { getProjectConfig, textResult, errorResult, tryImport, ToolResult } from "../projects/config.js";
import { getSidecar } from "../registry.js";

export async function handleLint(args: Record<string, unknown> = {}): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);

    const lintMod = await tryImport<{
      runLint: (wp: string, sidecar?: any | null) => Promise<{
        issues: { type: string; severity: string; page: string; detail: string }[];
        exitCode: number;
      }>;
    }>("../lint.js");

    if (!lintMod?.runLint) {
      return textResult(
        "# Lint Results\n\n_Lint module not available. Install or build src/lint.ts._",
      );
    }

    const sidecar = getSidecar();
    const lintResult = await lintMod.runLint(layout.pages_dir, sidecar);
    const issues = Array.isArray(lintResult) ? lintResult : lintResult.issues;

    if (!issues || issues.length === 0) {
      return textResult(
        "# Lint Results\n\n✅ No issues found. The wiki looks clean!",
      );
    }

    const bySeverity: Record<string, typeof issues> = {};
    for (const issue of issues) {
      (bySeverity[issue.severity] ??= []).push(issue);
    }

    const lines: string[] = [
      `# Lint Results (${issues.length} issues)`,
      "",
    ];

    const severityOrder = ["error", "warn", "suggest", "info"];
    for (const sev of severityOrder) {
      const group = bySeverity[sev];
      if (!group || group.length === 0) continue;
      const badge =
        sev === "error"
          ? "🔴 ERROR"
          : sev === "warn"
            ? "🟡 WARN"
            : sev === "suggest"
              ? "🔵 Suggest"
              : "⚪ Info";
      lines.push(`### ${badge} (${group.length})`, "");
      for (const issue of group) {
        lines.push(`- **${issue.type}** on \`${issue.page}\``);
        if (issue.detail) lines.push(`  ${issue.detail}`);
      }
      lines.push("");
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Lint failed: ${e}`);
  }
}
