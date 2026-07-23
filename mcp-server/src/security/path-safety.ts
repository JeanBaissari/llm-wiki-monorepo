// MCP Server — Path Safety Utilities

import * as fsSync from "node:fs";
import * as path from "node:path";

export const ALLOW_LIST_PATTERNS = [
  /^PURPOSE\.md$/,
  /^CLAUDE\.md$/,
  /^SCHEMA\.md$/,
  /^wiki(?:\/.*)?$/,
  /^raw(?:\/.*)?$/,
  /^audit(?:\/.*)?$/,
  /^logs?(?:\/.*)?$/,
];

export const BINARY_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
  ".pdf", ".zip", ".gz", ".tar", ".tgz",
  ".mp3", ".mp4", ".avi", ".mov",
  ".exe", ".dll", ".so", ".bin",
  ".db", ".sqlite", ".sqlite3",
  ".woff", ".woff2", ".ttf", ".eot",
]);

export function isBinaryExtension(filePath: string): boolean {
  const ext = path.extname(filePath).toLowerCase();
  return BINARY_EXTENSIONS.has(ext);
}

export function safeJoin(projectRoot: string, userPath: string): string {
  if (path.isAbsolute(userPath)) {
    throw new Error(`Absolute paths are not allowed: "${userPath}". Use a project-relative path.`);
  }

  if (!userPath || userPath.trim() === "") {
    throw new Error("Path must not be empty.");
  }

  const resolved = path.resolve(projectRoot, userPath);

  let realPath: string;
  try {
    realPath = fsSync.realpathSync(resolved);
  } catch {
    realPath = resolved;
  }

  const normalizedRoot = path.resolve(projectRoot);
  if (!realPath.startsWith(normalizedRoot + path.sep) && realPath !== normalizedRoot) {
    throw new Error(`Path escapes project root: "${userPath}".`);
  }

  const relPath = path.relative(normalizedRoot, realPath);
  const isAllowed = ALLOW_LIST_PATTERNS.some((pattern) => pattern.test(relPath));
  if (!isAllowed) {
    throw new Error(
      `Path not in allow-list: "${relPath}". Allowed: PURPOSE.md, CLAUDE.md, SCHEMA.md, wiki/**/*, raw/**/*, audit/**/*, logs/**/*`,
    );
  }

  return realPath;
}
