import { App, Notice, TFile, normalizePath } from "obsidian";
import {
  computeAnchor,
  makeId,
  filenameFor,
  toMarkdown,
  type AuditEntry,
  type Severity,
} from "audit-shared";
import type { LLMWikiAuditSettings } from "./settings.js";

export interface WriteAuditArgs {
  file: TFile;
  fileText: string;
  selStart: number;
  selEnd: number;
  severity: Severity;
  comment: string;
}

/**
 * Convert the active selection into an audit file on disk.
 * Returns the TFile written, or throws on error (errors are also surfaced via Notice).
 */
export async function writeAudit(
  app: App,
  settings: LLMWikiAuditSettings,
  args: WriteAuditArgs,
): Promise<TFile> {
  const {
    file,
    fileText,
    selStart,
    selEnd,
    severity,
    comment,
  } = args;

  const targetRel = resolveTargetRelativeToWiki(file.path, settings.wikiRoot);

  const anchor = computeAnchor(fileText, selStart, selEnd);

  const id = makeId();
  const slug = firstWords(comment, 5);
  const filename = filenameFor(id, slug);
  const auditDirPath = joinRel(
    settings.wikiRoot === "." ? "" : settings.wikiRoot,
    settings.auditDir,
  );
  const fullPath = normalizePath(joinRel(auditDirPath, filename));

  await ensureFolder(app, auditDirPath);

  const entry: AuditEntry = {
    id,
    target: targetRel,
    target_lines: anchor.target_lines,
    anchor_before: anchor.anchor_before,
    anchor_text: anchor.anchor_text,
    anchor_after: anchor.anchor_after,
    severity,
    author: settings.author,
    source: "obsidian-plugin",
    created: new Date().toISOString(),
    status: "open",
    body: renderBody(comment),
  };

  const md = toMarkdown(entry);
  try {
    const created = await app.vault.create(fullPath, md);
    new Notice(`Audit filed: ${filename}`);
    return created;
  } catch (err) {
    new Notice(`Failed to write audit file: ${String(err)}`);
    throw err;
  }
}

function renderBody(comment: string): string {
  return `# Comment\n\n${comment.trim()}\n\n# Resolution\n\n<!-- filled in when the audit is processed -->\n`;
}

function firstWords(text: string, n: number): string {
  const words = text.trim().split(/\s+/).slice(0, n).join(" ");
  return words;
}

function resolveTargetRelativeToWiki(vaultPath: string, wikiRoot: string): string {
  if (wikiRoot === "" || wikiRoot === ".") return vaultPath;
  const normalized = wikiRoot.replace(/\/+$/, "");
  if (vaultPath === normalized) return "";
  if (vaultPath.startsWith(normalized + "/")) {
    return vaultPath.slice(normalized.length + 1);
  }
  // Target lives outside the configured wiki root — keep the vault-relative
  // path. This will be flagged by lint if it doesn't resolve to a file.
  return vaultPath;
}

function joinRel(...parts: string[]): string {
  return parts
    .filter((p) => p && p !== ".")
    .map((p) => p.replace(/^\/+|\/+$/g, ""))
    .filter((p) => p.length > 0)
    .join("/");
}

async function ensureFolder(app: App, path: string): Promise<void> {
  if (!path) return;
  const existing = app.vault.getAbstractFileByPath(path);
  if (existing) return;
  try {
    await app.vault.createFolder(path);
  } catch {
    // Folder might exist already due to race; ignore.
  }
}
