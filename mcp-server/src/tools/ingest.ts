import { getProjectConfig, textResult, errorResult, tryImport, ToolResult } from "../projects/config.js";
import { safeJoin } from "../security/path-safety.js";
import { fileExists } from "../wiki-fs.js";
import { getSidecar } from "../registry.js";
import type { PythonSidecar } from "../adapters/sidecar.js";

export async function handleIngest(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const sourcePath = args.source_path as string | undefined;
    if (!sourcePath) {
      return errorResult("Missing required argument: source_path");
    }

    const resolvedSource = safeJoin(wp, sourcePath);

    const exists = await fileExists(resolvedSource);
    if (!exists) {
      return errorResult(`Source file not found: ${resolvedSource}`);
    }

    const sidecar = getSidecar();
    if (!sidecar?.isRunning()) {
      return errorResult(
        "Python sidecar is not running — cannot ingest. The sidecar may have failed to start.",
      );
    }

    const ingestMod = await tryImport<{
      runIngest: (
        sidecar: PythonSidecar,
        wikiRoot: string,
        sourcePath: string,
        options: Record<string, unknown>,
      ) => Promise<{
        success: boolean;
        pages_created: number;
        pages_updated: number;
        reviews_written: number;
        error: string;
      }>;
    }>("../ingest.js");

    if (!ingestMod?.runIngest) {
      return textResult(
        "# Ingest\n\n_Ingest module not available. Install or build src/ingest.ts._",
      );
    }

    const result = await ingestMod.runIngest(sidecar, layout.root, resolvedSource, {});

    if (!result.success) {
      return errorResult(`Ingest failed: ${result.error}`);
    }

    return textResult(
      [
        "# Ingest Complete",
        "",
        `**Source:** \`${resolvedSource}\``,
        "",
        `**Pages Created:** ${result.pages_created}`,
        `**Pages Updated:** ${result.pages_updated}`,
        `**Reviews Written:** ${result.reviews_written}`,
      ].join("\n"),
    );
  } catch (e: any) {
    const msg = e?.stderr ?? e?.stdout ?? String(e);
    return errorResult(`Ingest failed: ${msg}`);
  }
}
