// MCP Server — BM25 Search Engine (SQLite FTS5-backed)
//
// Replaces the in-memory, rebuild-on-every-startup BM25 index with
// a persistent SQLite FTS5 disk-backed index. The Python script
// `skill/scripts/index_wiki.py` builds and maintains the database.
// This module reads from it via better-sqlite3 (read-only), with
// a sql.js WASM fallback for constrained environments.
//
// BM25 scoring uses the current regex-based tokenizer against
// FTS5-stored pre-tokenized content. FTS5 MATCH provides candidate
// document retrieval; scoring is computed in TypeScript to preserve
// identical BM25 semantics.

import * as fsSync from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { readFile } from "./wiki-fs.js";
import type { SearchResult } from "./types.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── SQLite backend: better-sqlite3 (native) → sql.js (WASM fallback) ──

interface SqliteDb {
  prepare(sql: string): SqliteStmt;
  close(): void;
}

interface SqliteStmt {
  get(...params: unknown[]): unknown;
  all(...params: unknown[]): unknown[];
}

// Lazy-loaded backend — resolved on first openDb() call
let _backend: {
  open: (dbPath: string, readonly: boolean) => SqliteDb;
} | null = null;

async function _initBackend(): Promise<void> {
  if (_backend) return;

  // Try better-sqlite3 first (native, fast)
  try {
    const BetterSqlite3 = (await import("better-sqlite3")).default;
    _backend = {
      open(dbPath: string, readonly: boolean): SqliteDb {
        return new BetterSqlite3(dbPath, { readonly }) as unknown as SqliteDb;
      },
    };
    return;
  } catch {
    // better-sqlite3 not available — fall through to sql.js WASM
  }

  // Fall back to sql.js (WASM)
  const initSqlJs = (await import("sql.js")).default;
  const SQL = await initSqlJs();
  _backend = {
    open(dbPath: string, _readonly: boolean): SqliteDb {
      const buffer = fsSync.readFileSync(dbPath);
      const db = new SQL.Database(buffer);
      return {
        prepare(sql: string): SqliteStmt {
          const stmt = db.prepare(sql);
          return {
            get(...params: unknown[]): unknown {
              stmt.bind(params);
              if (stmt.step()) {
                const cols = stmt.getColumnNames();
                const vals = stmt.get();
                stmt.free();
                const obj: Record<string, unknown> = {};
                for (let i = 0; i < cols.length; i++) {
                  obj[cols[i]] = vals[i];
                }
                return obj;
              }
              stmt.free();
              return undefined;
            },
            all(...params: unknown[]): unknown[] {
              stmt.bind(params);
              const results: unknown[] = [];
              while (stmt.step()) {
                const cols = stmt.getColumnNames();
                const vals = stmt.get();
                const obj: Record<string, unknown> = {};
                for (let i = 0; i < cols.length; i++) {
                  obj[cols[i]] = vals[i];
                }
                results.push(obj);
              }
              stmt.free();
              return results;
            },
          };
        },
        close(): void {
          db.close();
        },
      };
    },
  };
}

// ── Tokenizer (unchanged from original) ─────────────────────────────────

const STOP_WORDS = new Set([
  "the", "is", "a", "an", "and", "or", "but", "in", "on", "at", "to",
  "for", "of", "with", "by", "from", "as", "are", "was", "were", "be",
  "been", "being", "have", "has", "had", "do", "does", "did", "will",
  "would", "could", "should", "may", "might", "can", "shall", "it",
  "its", "this", "that", "these", "those", "not", "no", "nor",
]);

const K1 = 1.5; // BM25 term saturation
const B = 0.75; // BM25 length normalization

/** Tokenize text into lowercase terms, filtering stop words */
function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[\s,.;:!?()\[\]{}"'`~@#$%^&*+=<>/\\|_-]+/)
    .filter((t) => t.length > 1 && !STOP_WORDS.has(t));
}

// ── FTS5 query escaping ─────────────────────────────────────────────────

/**
 * Escape special FTS5 characters in a query term.
 * FTS5 special chars: * " ( ) and whitespace.
 * We wrap terms in double quotes for exact phrase matching.
 */
function fts5Escape(term: string): string {
  // Remove double quotes entirely — they'd break the MATCH syntax
  return term.replace(/"/g, "").replace(/\*/g, "\\*");
}

// ── Database connection cache ──────────────────────────────────────────

/** Cache of read-only database connections, keyed by db path */
const DB_CACHE = new Map<string, SqliteDb>();

/** Open (or return cached) read-only SQLite database at <wikiPath>/.index/wiki.db */
async function openDb(wikiPath: string): Promise<SqliteDb> {
  await _initBackend();
  const dbPath = path.join(wikiPath, ".index", "wiki.db");
  let db = DB_CACHE.get(dbPath);
  if (!db) {
    db = _backend!.open(dbPath, true);
    DB_CACHE.set(dbPath, db);
  }
  return db;
}

/** Close and remove a cached database connection */
function closeDb(wikiPath: string): void {
  const dbPath = path.join(wikiPath, ".index", "wiki.db");
  const db = DB_CACHE.get(dbPath);
  if (db) {
    db.close();
    DB_CACHE.delete(dbPath);
  }
}

// ── Stats helpers ──────────────────────────────────────────────────────

function getDocCount(db: SqliteDb): number {
  const row = db.prepare(
    "SELECT value FROM index_stats WHERE key = 'doc_count'"
  ).get() as { value: string } | undefined;
  return row ? parseInt(row.value, 10) : 0;
}

function getAvgLength(db: SqliteDb): number {
  const row = db.prepare(
    "SELECT value FROM index_stats WHERE key = 'avg_length'"
  ).get() as { value: string } | undefined;
  return row ? parseFloat(row.value) : 0;
}

// ── Monorepo root resolution ───────────────────────────────────────────

/**
 * Resolve the monorepo root directory for spawning index_wiki.py.
 * Walks up from the mcp-server directory looking for skill/scripts.
 */
function monorepoRoot(): string {
  let dir = path.resolve(__dirname);
  // mcp-server/dist/ or mcp-server/src/ — walk up
  for (let i = 0; i < 5; i++) {
    const candidate = path.join(dir, "skill", "scripts", "index_wiki.py");
    if (fsSync.existsSync(candidate)) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  // Fallback — assume standard layout relative to __dirname
  return path.resolve(__dirname, "..", "..");
}

// ── Public API (backward-compatible) ────────────────────────────────────

/** Error thrown when index is being built asynchronously */
export class IndexBuildingError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "IndexBuildingError";
  }
}

/**
 * Ensure the SQLite index exists — pre-build on startup.
 * wikiPath should be `layout.root` (wiki project root).
 * The database is at `<wikiPath>/.index/wiki.db`.
 */
export async function buildIndex(wikiPath: string): Promise<void> {
  const dbPath = path.join(wikiPath, ".index", "wiki.db");

  if (!fsSync.existsSync(dbPath)) {
    // Index doesn't exist — spawn index_wiki.py synchronously
    const scriptPath = path.join(monorepoRoot(), "skill", "scripts", "index_wiki.py");
    const { execFileSync } = await import("node:child_process");
    try {
      execFileSync("python3", [scriptPath, wikiPath], {
        stdio: "pipe",
        timeout: 60_000,
      });
    } catch (e) {
      // Index build failed — will fall through to async fallback in search()
      console.error(`[search] Index build failed: ${e}`);
    }
  }
}

/**
 * Search the wiki using SQLite FTS5 + current BM25 tokenizer.
 *
 * wikiPath: `layout.root` (wiki project root, DB at <root>/.index/wiki.db)
 * query: free-text search query
 * topK: max results (default 20)
 */
export async function search(
  wikiPath: string,
  query: string,
  topK: number = 20,
): Promise<SearchResult[]> {
  const dbPath = path.join(wikiPath, ".index", "wiki.db");

  // If index doesn't exist, try async build and return empty
  if (!fsSync.existsSync(dbPath)) {
    const scriptPath = path.join(monorepoRoot(), "skill", "scripts", "index_wiki.py");
    // Check if there are any .md files first — if not, don't bother spawning
    const { discoverLayout } = await import("./projects/discover.js");
    const layout = discoverLayout(wikiPath);
    const { findMdFiles } = await import("./wiki-fs.js");
    const mdFiles = await findMdFiles(layout.pages_dir);

    if (mdFiles.length === 0) {
      // Empty wiki — return empty results without building an index
      return [];
    }

    // Non-empty wiki without an index — spawn build and ask to retry
    spawn("python3", [scriptPath, wikiPath], {
      detached: true,
      stdio: "ignore",
    });
    throw new IndexBuildingError(
      "indexing in progress — retry in a few seconds"
    );
  }

  // Tokenize query
  const queryTerms = tokenize(query);
  if (queryTerms.length === 0) return [];

  const db = await openDb(wikiPath);

  // Read aggregate stats
  const N = getDocCount(db);
  if (N === 0) return [];

  const avgLength = getAvgLength(db);

  // ── Compute IDF for each query term using FTS5 MATCH counts ─────────
  const idf = new Map<string, number>();
  for (const term of queryTerms) {
    try {
      const escaped = fts5Escape(term);
      const row = db.prepare(
        `SELECT COUNT(*) as c FROM pages WHERE pages MATCH ?`
      ).get(escaped) as { c: number };
      const df = row.c;
      idf.set(term, Math.log((N - df + 0.5) / (df + 0.5) + 1));
    } catch {
      // FTS5 syntax error on unusual term — treat as df=0
      idf.set(term, Math.log((N + 0.5) / 0.5 + 1));
    }
  }

  // ── Retrieve candidates via FTS5 MATCH ─────────────────────────────
  // Use OR of all terms to get a broad candidate set, then score precisely
  const matchTerms = queryTerms
    .map((t) => `"${fts5Escape(t)}"`)
    .join(" OR ");

  interface CandidateRow {
    path: string;
    title: string;
    content: string;
  }

  let candidates: CandidateRow[];
  try {
    candidates = db.prepare(
      `SELECT path, title, content FROM pages WHERE pages MATCH ? LIMIT ?`
    ).all(matchTerms, Math.max(topK * 5, 100)) as CandidateRow[];
  } catch (e) {
    // FTS5 MATCH syntax error — no results
    return [];
  }

  // ── Compute BM25 scores using current tokenizer ────────────────────
  const scored: SearchResult[] = [];

  for (const doc of candidates) {
    // Parse pre-tokenized content (space-separated tokens)
    const tokens = doc.content.length > 0
      ? doc.content.split(/\s+/)
      : [];
    const docLength = tokens.length;

    let score = 0;
    for (const term of queryTerms) {
      // Count term frequency in pre-tokenized content
      const tf = tokens.filter((t) => t === term).length;
      if (tf === 0) continue;

      const numerator = tf * (K1 + 1);
      const denominator =
        tf + K1 * (1 - B + B * (docLength / avgLength));
      score += (idf.get(term) ?? 0) * (numerator / denominator);
    }

    if (score > 0) {
      scored.push({
        path: doc.path,
        title: doc.title,
        snippet: "", // computed below
        score,
      });
    }
  }

  // Sort by score descending, take topK
  scored.sort((a, b) => b.score - a.score);
  const top = scored.slice(0, topK);

  // ── Generate snippets for top results ──────────────────────────────
  for (const result of top) {
    try {
      const absPath = path.join(wikiPath, result.path);
      const content = await readFile(absPath);
      const firstTerm = queryTerms[0];
      const idx = content.toLowerCase().indexOf(firstTerm);
      if (idx >= 0) {
        const start = Math.max(0, idx - 40);
        const end = Math.min(content.length, idx + firstTerm.length + 120);
        result.snippet = content.slice(start, end).replace(/\n/g, " ");
        if (start > 0) result.snippet = "..." + result.snippet;
        if (end < content.length) result.snippet = result.snippet + "...";
      } else {
        result.snippet = content.slice(0, 150).replace(/\n/g, " ") + "...";
      }
    } catch {
      result.snippet = "(unreadable)";
    }
  }

  return top;
}

/**
 * Clear the database connection cache.
 * The on-disk index is preserved — this just resets cached connections
 * so the next search will re-open them.
 */
export function clearIndex(): void {
  for (const [dbPath, db] of DB_CACHE) {
    try {
      db.close();
    } catch {
      // already closed
    }
  }
  DB_CACHE.clear();
}
