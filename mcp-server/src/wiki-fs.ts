// MCP Server — Filesystem Adapter
// Replaces Tauri API calls with direct Node.js fs operations

import * as fs from "node:fs/promises";
import * as path from "node:path";
import type { FileNode } from "./types.js";

/** Normalize a path — resolve relative, remove trailing slashes */
export function normalizePath(p: string): string {
  return path.resolve(p).replace(/\/+$/, "");
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
