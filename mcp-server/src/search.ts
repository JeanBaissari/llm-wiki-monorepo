// MCP Server — BM25 Search Engine
// Pure TypeScript, no dependencies. Keyword search over wiki/ markdown files.

import { findMdFiles, readFile } from "./wiki-fs.js";
import type { SearchResult } from "./types.js";

interface IndexEntry {
  path: string;
  title: string;
  terms: Map<string, number>; // term → frequency in document
  length: number; // total term count
}

let index: IndexEntry[] | null = null;
let indexWikiPath: string | null = null;
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

/** Extract title from markdown content */
function extractTitle(content: string, filename: string): string {
  // Try frontmatter title
  const fm = content.match(/^---\n[\s\S]*?^title:\s*["']?(.+?)["']?\s*$/m);
  if (fm) return fm[1].trim();
  // Try H1
  const h1 = content.match(/^#\s+(.+)$/m);
  if (h1) return h1[1].trim();
  return filename.replace(/\.md$/, "").replace(/[-_]/g, " ");
}

/** Build search index from wiki directory */
export async function buildIndex(wikiPath: string): Promise<void> {
  if (index && indexWikiPath === wikiPath) return; // already indexed

  const files = await findMdFiles(wikiPath);
  const entries: IndexEntry[] = [];

  for (const filePath of files) {
    try {
      const content = await readFile(filePath);
      const title = extractTitle(content, filePath);
      const terms = new Map<string, number>();
      const tokens = tokenize(content);

      for (const t of tokens) {
        terms.set(t, (terms.get(t) ?? 0) + 1);
      }

      entries.push({
        path: filePath,
        title,
        terms,
        length: tokens.length,
      });
    } catch {
      // Skip unreadable files
    }
  }

  index = entries;
  indexWikiPath = wikiPath;
}

/** BM25 search: rank documents by relevance to query */
export async function search(
  wikiPath: string,
  query: string,
  topK: number = 20,
): Promise<SearchResult[]> {
  await buildIndex(wikiPath);
  if (!index || index.length === 0) return [];

  const queryTerms = tokenize(query);
  if (queryTerms.length === 0) return [];

  const avgLength =
    index.reduce((sum, doc) => sum + doc.length, 0) / index.length;
  const N = index.length;

  // Compute IDF for each query term
  const idf = new Map<string, number>();
  for (const term of queryTerms) {
    const df = index.filter((doc) => doc.terms.has(term)).length;
    idf.set(term, Math.log((N - df + 0.5) / (df + 0.5) + 1));
  }

  // Score each document
  const scored: SearchResult[] = [];

  for (const doc of index) {
    let score = 0;
    for (const term of queryTerms) {
      const tf = doc.terms.get(term) ?? 0;
      if (tf === 0) continue;
      const numerator = tf * (K1 + 1);
      const denominator =
        tf + K1 * (1 - B + B * (doc.length / avgLength));
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

  scored.sort((a, b) => b.score - a.score);

  // Generate snippets for top results
  const top = scored.slice(0, topK);
  for (const result of top) {
    try {
      const content = await readFile(result.path);
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

/** Clear the search index (force rebuild on next search) */
export function clearIndex(): void {
  index = null;
  indexWikiPath = null;
}
