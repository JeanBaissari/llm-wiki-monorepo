import fs from "node:fs";
import path from "node:path";
import type { Request, Response } from "express";
import type { ServerConfig } from "../config.js";

interface SearchResult {
  title: string;
  path: string;
  snippet: string;
  score: number;
}

const STOP_WORDS = new Set([
  "the", "is", "a", "an", "and", "or", "but", "in", "on", "at", "to",
  "for", "of", "with", "by", "from", "as", "are", "was", "were", "be",
  "been", "being", "have", "has", "had", "do", "does", "did", "will",
  "would", "could", "should", "may", "might", "can", "shall", "it",
  "its", "this", "that", "these", "those", "not", "no", "nor",
]);

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[\s,.;:!?()\[\]{}"'`~@#$%^&*+=<>/\\|_-]+/)
    .filter(t => t.length > 1 && !STOP_WORDS.has(t));
}

function extractTitle(content: string): string | null {
  const fm = /^---\n([\s\S]*?)\n---/.exec(content);
  if (fm) {
    const t = /^title:\s*(.+)$/m.exec(fm[1]!);
    if (t) return t[1]!.trim().replace(/^["']|["']$/g, "");
  }
  const h1 = /^#\s+(.+?)\s*$/m.exec(content);
  return h1 ? h1[1]! : null;
}

function collectMdFiles(dir: string): string[] {
  const out: string[] = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name.startsWith(".")) continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...collectMdFiles(full));
    else if (e.isFile() && e.name.endsWith(".md")) out.push(full);
  }
  return out;
}

export function handleSearch(cfg: ServerConfig) {
  return (req: Request, res: Response) => {
    const q = (req.query.q as string | undefined) ?? "";
    if (!q.trim()) {
      res.json({ results: [] });
      return;
    }

    const wikiDir = path.join(cfg.wikiRoot, "wiki");
    if (!fs.existsSync(wikiDir)) {
      res.json({ results: [] });
      return;
    }

    const files = collectMdFiles(wikiDir);
    const queryTerms = tokenize(q);
    if (queryTerms.length === 0) {
      res.json({ results: [] });
      return;
    }

    const scored: SearchResult[] = [];

    for (const f of files) {
      const content = fs.readFileSync(f, "utf-8");
      const title = extractTitle(content) ?? path.basename(f, ".md");
      const relPath = path.relative(cfg.wikiRoot, f).split(path.sep).join("/");

      const bodyTokens = tokenize(content);
      const titleTokens = tokenize(title);

      let score = 0;
      for (const qt of queryTerms) {
        score += bodyTokens.filter(t => t === qt).length;
        score += titleTokens.filter(t => t === qt).length * 3;
      }

      if (score > 0) {
        const firstTerm = queryTerms[0]!;
        const idx = content.toLowerCase().indexOf(firstTerm);
        let snippet = "";
        if (idx >= 0) {
          const start = Math.max(0, idx - 40);
          const end = Math.min(content.length, idx + firstTerm.length + 60);
          snippet = content.slice(start, end).replace(/\n/g, " ");
          if (start > 0) snippet = "..." + snippet;
          if (end < content.length) snippet = snippet + "...";
        } else {
          snippet = content.slice(0, 100).replace(/\n/g, " ") + "...";
        }

        scored.push({ title, path: relPath, snippet, score });
      }
    }

    scored.sort((a, b) => b.score - a.score);
    res.json({ results: scored.slice(0, 20) });
  };
}
