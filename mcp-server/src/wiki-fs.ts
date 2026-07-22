// MCP Server — Filesystem Adapter
// Replaces Tauri API calls with direct Node.js fs operations

import * as fs from "node:fs/promises";
import * as fsSync from "node:fs";
import * as path from "node:path";
import type { FileNode } from "./types.js";

/** Normalize a path — resolve relative, remove trailing slashes */
export function normalizePath(p: string): string {
  return path.resolve(p).replace(/\/+$/, "");
}

const ALLOW_LIST_PATTERNS = [
  /^PURPOSE\.md$/,
  /^CLAUDE\.md$/,
  /^SCHEMA\.md$/,
  /^wiki(?:\/.*)?$/,
  /^raw(?:\/.*)?$/,
  /^audit(?:\/.*)?$/,
  /^logs?(?:\/.*)?$/,
];

const BINARY_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
  ".pdf", ".zip", ".gz", ".tar", ".tgz",
  ".mp3", ".mp4", ".avi", ".mov",
  ".exe", ".dll", ".so", ".bin",
  ".db", ".sqlite", ".sqlite3",
  ".woff", ".woff2", ".ttf", ".eot",
]);

/**
 * Safe path resolution within a project root.
 * Rejects absolute paths, traversals escaping the root, and non-allow-listed paths.
 */
export function safeJoin(projectRoot: string, userPath: string): string {
  // Reject absolute paths
  if (path.isAbsolute(userPath)) {
    throw new Error(`Absolute paths are not allowed: "${userPath}". Use a project-relative path.`);
  }

  // Reject empty path
  if (!userPath || userPath.trim() === "") {
    throw new Error("Path must not be empty.");
  }

  // Resolve .. segments
  const resolved = path.resolve(projectRoot, userPath);

  // Resolve symlinks to verify the real path
  let realPath: string;
  try {
    realPath = fsSync.realpathSync(resolved);
  } catch {
    realPath = resolved;
  }

  // Verify the path hasn't escaped projectRoot
  const normalizedRoot = path.resolve(projectRoot);
  if (!realPath.startsWith(normalizedRoot + path.sep) && realPath !== normalizedRoot) {
    throw new Error(`Path escapes project root: "${userPath}".`);
  }

  // Check allow-list: path must be relative to projectRoot
  const relPath = path.relative(normalizedRoot, realPath);
  const isAllowed = ALLOW_LIST_PATTERNS.some((pattern) => pattern.test(relPath));
  if (!isAllowed) {
    throw new Error(
      `Path not in allow-list: "${relPath}". Allowed: PURPOSE.md, CLAUDE.md, SCHEMA.md, wiki/**/*, raw/**/*, audit/**/*, logs/**/*`,
    );
  }

  return realPath;
}

/**
 * Check if a file has a binary extension and should be rejected.
 */
export function isBinaryExtension(filePath: string): boolean {
  const ext = path.extname(filePath).toLowerCase();
  return BINARY_EXTENSIONS.has(ext);
}

/** List directory contents recursively, building a FileNode tree */
export async function listDirectory(
  dirPath: string,
  recursive: boolean = true,
  maxFiles: number = 10000,
): Promise<{ files: FileNode[]; truncated: boolean }> {
  const root = normalizePath(dirPath);
  const files: FileNode[] = [];
  let count = 0;

  async function walk(currentPath: string): Promise<void> {
    if (count >= maxFiles) return;
    let entries;
    try {
      entries = await fs.readdir(currentPath, { withFileTypes: true });
    } catch {
      return;
    }

    // Sort: dirs first, then alphabetical
    entries.sort((a, b) => {
      if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
      return a.name.localeCompare(b.name);
    });

    for (const entry of entries) {
      if (count >= maxFiles) return;
      if (entry.name.startsWith(".")) continue;

      const fullPath = path.join(currentPath, entry.name);
      const relPath = path.relative(root, fullPath);

      if (entry.isDirectory()) {
        const node: FileNode = {
          name: entry.name,
          path: fullPath,
          is_dir: true,
          children: [],
        };
        files.push(node);
        count++;
        if (recursive) await walk(fullPath);
      } else {
        files.push({
          name: entry.name,
          path: fullPath,
          is_dir: false,
        });
        count++;
      }
    }
  }

  await walk(root);
  return { files, truncated: count >= maxFiles };
}

/** Read a file's text content */
export async function readFile(filePath: string): Promise<string> {
  return fs.readFile(filePath, "utf-8");
}

/** Write content to a file, creating parent directories if needed */
export async function writeFile(
  filePath: string,
  content: string,
): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, content, "utf-8");
}

/** Check if a file exists */
export async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

/** Get file size in bytes */
export async function getFileSize(filePath: string): Promise<number> {
  const stat = await fs.stat(filePath);
  return stat.size;
}

/** Get file modification time as ISO string */
export async function getFileModifiedTime(
  filePath: string,
): Promise<string> {
  const stat = await fs.stat(filePath);
  return stat.mtime.toISOString();
}

/** Find all .md files under a directory (flat list, no tree) */
export async function findMdFiles(dirPath: string): Promise<string[]> {
  const files: string[] = [];
  const walk = async (current: string) => {
    let entries;
    try {
      entries = await fs.readdir(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.name.startsWith(".")) continue;
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        await walk(full);
      } else if (entry.name.endsWith(".md")) {
        files.push(full);
      }
    }
  };
  await walk(dirPath);
  return files;
}

/** Ensure a directory exists */
export async function ensureDir(dirPath: string): Promise<void> {
  await fs.mkdir(dirPath, { recursive: true });
}
