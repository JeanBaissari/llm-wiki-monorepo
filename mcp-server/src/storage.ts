// MCP Server — Cache Layer
// JSON cache files stored in raw/.cache/<key>.json
// Supports TTL-based expiration checked on read and during clearCache

import { readFile, writeFile, fileExists, ensureDir } from "./wiki-fs.js";
import * as path from "node:path";
import * as fs from "node:fs/promises";

// ─── Internal helpers ──────────────────────────────────────

function cacheDir(wikiPath: string): string {
  return path.join(wikiPath, "raw", ".cache");
}

/** Sanitize key to a safe filesystem name (alphanumeric, dot, dash, underscore) */
function sanitizeKey(key: string): string {
  return key.replace(/[^a-zA-Z0-9._-]/g, "_");
}

function cacheFilePath(wikiPath: string, key: string): string {
  return path.join(cacheDir(wikiPath), `${sanitizeKey(key)}.json`);
}

interface CacheEntry {
  value: unknown;
  created: string;
  expires?: string;
}

// ─── Public API ────────────────────────────────────────────

/**
 * Read a cache entry.
 * Returns the stored value as a JSON string, or null if missing/expired.
 */
export async function getCache(
  wikiPath: string,
  key: string,
): Promise<string | null> {
  const filePath = cacheFilePath(wikiPath, key);
  if (!(await fileExists(filePath))) return null;

  try {
    const raw = await readFile(filePath);
    const entry = JSON.parse(raw) as CacheEntry;

    // Check embedded TTL
    if (entry.expires && new Date(entry.expires) <= new Date()) {
      await fs.unlink(filePath).catch(() => {});
      return null;
    }

    // Return the value portion serialized back to JSON
    return JSON.stringify(entry.value);
  } catch {
    return null;
  }
}

/**
 * Write a cache entry.
 * The value is serialized to JSON and stored with a creation timestamp.
 */
export async function setCache(
  wikiPath: string,
  key: string,
  value: unknown,
): Promise<void> {
  const dir = cacheDir(wikiPath);
  await ensureDir(dir);

  const entry: CacheEntry = {
    value,
    created: new Date().toISOString(),
  };

  const filePath = cacheFilePath(wikiPath, key);
  await writeFile(filePath, JSON.stringify(entry, null, 2));
}

/**
 * Clear all cache entries older than 30 days (by file mtime).
 * Also evicts entries whose embedded TTL has expired.
 */
export async function clearCache(wikiPath: string): Promise<void> {
  const dir = cacheDir(wikiPath);
  const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000; // 30 days
  let removed = 0;

  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      if (!entry.isFile() || !entry.name.endsWith(".json")) continue;

      const fullPath = path.join(dir, entry.name);
      try {
        const stat = await fs.stat(fullPath);

        // Remove by file age
        if (stat.mtimeMs < cutoff) {
          await fs.unlink(fullPath);
          removed++;
          continue;
        }

        // Also check embedded TTL in the content
        const raw = await readFile(fullPath);
        const parsed = JSON.parse(raw) as CacheEntry;
        if (parsed.expires && new Date(parsed.expires).getTime() < Date.now()) {
          await fs.unlink(fullPath);
          removed++;
        }
      } catch {
        // Skip files that can't be read
      }
    }
  } catch {
    // Cache dir doesn't exist — nothing to clear
  }
}
