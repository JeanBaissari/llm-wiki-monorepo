import { getProjectConfig, textResult, errorResult, tryImport, ToolResult } from "../projects/config.js";
import { getSidecar } from "../registry.js";
import type { PythonSidecar } from "../adapters/sidecar.js";
import type { BackupResult } from "../backup.js";

export async function handleBackup(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);

    const sidecar = getSidecar();
    if (!sidecar?.isRunning()) {
      return errorResult(
        "Python sidecar is not running — cannot create backup. The sidecar may have failed to start.",
      );
    }

    const backupMod = await tryImport<{
      createBackup: (
        sidecar: PythonSidecar,
        wikiPath: string,
      ) => Promise<BackupResult>;
    }>("../backup.js");

    if (!backupMod?.createBackup) {
      return textResult(
        "# Backup\n\n_Backup module not available. Install or build src/backup.ts._",
      );
    }

    const result = await backupMod.createBackup(sidecar, layout.root);

    const sizeMB = (result.size_bytes / (1024 * 1024)).toFixed(1);
    return textResult(
      [
        "# Backup Created",
        "",
        `**Archive:** \`${result.archive_path}\``,
        `**Size:** ${sizeMB} MB (${result.size_bytes.toLocaleString()} bytes)`,
        `**Files:** ${result.file_count}`,
        `**Integrity:** ${result.integrity === "valid" ? "✅ Valid" : result.integrity === "invalid" ? "❌ Invalid" : "⚠️  Unverifiable"}`,
      ].join("\n"),
    );
  } catch (e) {
    return errorResult(`Backup failed: ${e}`);
  }
}
