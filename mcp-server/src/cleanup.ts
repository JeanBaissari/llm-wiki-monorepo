// MCP Server — Soft Cascade Cleanup
// When a source file is deleted, find all wiki pages that reference it
// in their frontmatter `sources:` list, strip the reference, and report
// pages that become orphans (0 remaining sources).

import { readFile, writeFile, ensureDir, findMdFiles } from "./wiki-fs.js";
import * as path from "node:path";

// ─── Frontmatter source parsing ────────────────────────────

interface SourcesInfo {
  sources: string[];
  /** Start and end position of the sources block within the file content */
  blockStart: number;
  blockEnd: number;
}

/**
 * Parse the `sources:` field from frontmatter.
 * Supports both inline array:  sources: [a, b, c]
 * and block list:             sources:\n  - "a"\n  - "b"
 */
function parseSources(content: string): SourcesInfo {
  const empty: SourcesInfo = { sources: [], blockStart: -1, blockEnd: -1 };

  const fmMatch = content.match(/^---\n[\s\S]*?\n---/);
  if (!fmMatch) return empty;

  const fmStart = fmMatch.index!;
  const fmEnd = fmStart + fmMatch[0].length;

  // Try inline array format: sources: [item1, item2]
  const inlineMatch = fmMatch[0].match(
    /^(sources:\s*\[(.*?)\])/m,
  );
  if (inlineMatch) {
    const raw = inlineMatch[2];
    const sources = raw
      .split(",")
      .map((s) => s.trim().replace(/^["']|["']$/g, ""))
      .filter(Boolean);
    const blockStart = fmStart + inlineMatch.index!;
    const blockEnd = blockStart + inlineMatch[1].length;
    return { sources, blockStart, blockEnd };
  }

  // Try block list format:
  // sources:
  //   - "item1"
  //   - "item2"
  const blockHeaderMatch = fmMatch[0].match(/^sources:\s*$/m);
  if (blockHeaderMatch) {
    const headerIndex = fmMatch[0].indexOf(blockHeaderMatch[0]);
    const afterHeader = fmMatch[0].slice(headerIndex + blockHeaderMatch[0].length);
    const listItemRegex = /^\n\s+-\s*["']?(.+?)["']?\s*/gm;
    const sources: string[] = [];
    let lastEnd = 0;
    let itemMatch: RegExpExecArray | null;

    while ((itemMatch = listItemRegex.exec(afterHeader)) !== null) {
      sources.push(itemMatch[1].replace(/^["']|["']$/g, ""));
      lastEnd = itemMatch.index + itemMatch[0].length;
    }

    const blockStart = fmStart + headerIndex;
    const blockEnd = fmStart + headerIndex + blockHeaderMatch[0].length + lastEnd;
    return { sources, blockStart, blockEnd };
  }

  return empty;
}

/**
 * Replace the sources section in content with a new list.
 * If newSources is empty, the entire sources block is removed.
 */
function replaceSourcesInContent(
  content: string,
  info: SourcesInfo,
  newSources: string[],
): string {
  if (info.blockStart < 0) {
    // No existing sources block — add one before closing ---
    if (newSources.length === 0) return content;
    const sourcesYaml = `sources:\n${newSources.map((s) => `  - "${s}"`).join("\n")}`;
    const fmEnd = content.indexOf("\n---\n") + 4; // after "---"
    return content.slice(0, fmEnd) + "\n" + sourcesYaml + content.slice(fmEnd);
  }

  if (newSources.length === 0) {
    // Remove the entire sources block
    return content.slice(0, info.blockStart) + content.slice(info.blockEnd);
  }

  const sourcesYaml = `sources:\n${newSources.map((s) => `  - "${s}"`).join("\n")}`;
  return content.slice(0, info.blockStart) + sourcesYaml + content.slice(info.blockEnd);
}

// ─── Logging ───────────────────────────────────────────────

async function appendLog(
  wikiPath: string,
  sourcePath: string,
  actions: string[],
  orphanedPages: string[],
): Promise<void> {
  const now = new Date();
  const dateStr =
    `${now.getFullYear()}` +
    `${String(now.getMonth() + 1).padStart(2, "0")}` +
    `${String(now.getDate()).padStart(2, "0")}`;

  const logDir = path.join(wikiPath, "log");
  await ensureDir(logDir);

  const logFile = path.join(logDir, `${dateStr}.md`);

  const lines: string[] = [
    `## Cleanup: ${now.toISOString()}`,
    "",
    `**Deleted source:** \`${sourcePath}\``,
    "",
    "**Actions:**",
    ...actions.map((a) => `- ${a}`),
  ];

  if (orphanedPages.length > 0) {
    lines.push(
      "",
      "**Orphaned pages (0 remaining sources):**",
      ...orphanedPages.map((p) => `- ${p}`),
    );
  }

  lines.push("", "---", "");

  // Append to existing log file or create new one
  let existing = "";
  try {
    existing = await readFile(logFile);
  } catch {
    // File doesn't exist yet
  }

  await writeFile(logFile, existing + lines.join("\n"));
}

// ─── Public API ────────────────────────────────────────────

/**
 * Soft-cascade cleanup when a source file is deleted.
 *
 * Finds all wiki pages whose frontmatter `sources:` includes the given
 * sourcePath, strips that entry from the list, and reports any pages
 * that end up with 0 remaining sources (orphaned).
 *
 * Actions are logged to log/YYYYMMDD.md.
 *
 * @param wikiPath   Root path of the wiki
 * @param sourcePath The source file that was deleted (relative or absolute)
 * @returns The list of orphaned page paths (relative to wikiPath)
 */
export async function cleanupDeletedSource(
  wikiPath: string,
  sourcePath: string,
): Promise<{ orphanedPages: string[] }> {
  const orphanedPages: string[] = [];
  const actions: string[] = [];

  // Normalize the source path for comparison
  const normalizedSource = path.normalize(sourcePath);

  // Discover all markdown files in the wiki
  const mdFiles = await findMdFiles(wikiPath);

  for (const filePath of mdFiles) {
    try {
      const content = await readFile(filePath);
      const info = parseSources(content);

      if (!info.sources.includes(normalizedSource) && !info.sources.includes(sourcePath)) {
        continue;
      }

      // Strip the specific source entry
      const newSources = info.sources.filter(
        (s) => s !== normalizedSource && s !== sourcePath,
      );

      if (newSources.length === info.sources.length) {
        continue; // no change
      }

      const relPath = path.relative(wikiPath, filePath);

      const updatedContent = replaceSourcesInContent(content, info, newSources);
      await writeFile(filePath, updatedContent);

      actions.push(
        `Stripped source "${sourcePath}" from ${relPath} (${info.sources.length} → ${newSources.length} sources)`,
      );

      if (newSources.length === 0) {
        orphanedPages.push(relPath);
      }
    } catch {
      // Skip unreadable files
    }
  }

  // Log the cleanup
  if (actions.length > 0) {
    await appendLog(wikiPath, sourcePath, actions, orphanedPages);
  }

  return { orphanedPages };
}
