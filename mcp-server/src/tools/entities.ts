import { getProjectConfig, textResult, errorResult, tryImport, ToolResult } from "../projects/config.js";
import { getSidecar } from "../registry.js";
import type { PythonSidecar } from "../adapters/sidecar.js";
import type { EntityRegistryResult } from "../discover-tool.js";

export async function handleDiscoverEntities(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);

    const sidecar = getSidecar();
    if (!sidecar?.isRunning()) {
      return errorResult(
        "Python sidecar is not running — cannot discover entities. The sidecar may have failed to start.",
      );
    }

    const discoverMod = await tryImport<{
      discoverEntities: (
        sidecar: PythonSidecar,
        wikiPath: string,
        entityType?: string,
      ) => Promise<EntityRegistryResult>;
    }>("../discover-tool.js");

    if (!discoverMod?.discoverEntities) {
      return textResult(
        "# Entity Discovery\n\n_Discover module not available. Install or build src/discover-tool.ts._",
      );
    }

    const entityType = args.entity_type as string | undefined;

    const result = await discoverMod.discoverEntities(
      sidecar,
      layout.root,
      entityType,
    );

    if (!result.entities || result.entities.length === 0) {
      return textResult(
        `# Entity Registry\n\nNo entities found${entityType ? ` of type "${entityType}"` : ""}.`,
      );
    }

    const lines: string[] = [
      `# Entity Registry (${result.total})`,
      entityType ? `Filtered by type: **${entityType}**` : "",
      "",
    ];

    // Group by type for readability
    const byType: Record<string, typeof result.entities> = {};
    for (const entity of result.entities) {
      const t = entity.type || "(no type)";
      (byType[t] ??= []).push(entity);
    }

    for (const [type, entities] of Object.entries(byType)) {
      lines.push(`## ${type} (${entities.length})`, "");
      for (const e of entities) {
        const aliasStr = e.aliases?.length
          ? ` (aliases: ${e.aliases.join(", ")})`
          : "";
        lines.push(`- **${e.title}** \`${e.stem}\`${aliasStr}`);
      }
      lines.push("");
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Entity discovery failed: ${e}`);
  }
}
