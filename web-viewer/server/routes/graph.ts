import fs from "node:fs";
import path from "node:path";
import url from "node:url";
import { execSync } from "node:child_process";
import type { Request, Response } from "express";
import type { ServerConfig } from "../config.js";

export interface GraphNode {
  id: string; // path relative to wikiRoot, e.g. "wiki/concepts/Transformers.md"
  label: string; // display name (stem, e.g. "Transformers")
  path: string; // same as id, kept explicit for client
  group: string; // concepts | entities | summaries | other
  degree: number; // in + out link count, used for node sizing
  title: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const WIKILINK_RE = /\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]/g;

export function buildGraph(wikiRoot: string): GraphData {
  const wikiDir = path.join(wikiRoot, "wiki");
  if (!fs.existsSync(wikiDir)) return { nodes: [], edges: [] };

  const files = collectMdFiles(wikiDir);

  // Build a lookup table keyed by both the stem ("Transformers") and the
  // relative-to-wiki path (e.g. "concepts/Transformers"), so wikilinks can
  // resolve in either form.
  const byKey: Map<string, string> = new Map(); // key → rel-from-wikiRoot path
  const nodes: Map<string, GraphNode> = new Map();

  for (const f of files) {
    const relFromWiki = path.relative(wikiDir, f).split(path.sep).join("/");
    const id = `wiki/${relFromWiki}`;
    const stem = path.basename(f, ".md");
    const parts = relFromWiki.split("/");
    const group = parts.length > 1 ? parts[0]! : "other";
    const title = extractTitle(fs.readFileSync(f, "utf-8")) ?? stem;

    const node: GraphNode = {
      id,
      label: stem,
      path: id,
      group,
      degree: 0,
      title,
    };
    nodes.set(id, node);
    byKey.set(stem, id);
    byKey.set(relFromWiki.replace(/\.md$/, ""), id);
    // Also index by basename without extension in lowercase as a last-resort alias
    byKey.set(stem.toLowerCase(), id);
  }

  // Pass 2: build edges. Parse wikilinks per file and resolve targets.
  const edges: GraphEdge[] = [];
  const seenEdges = new Set<string>();
  for (const f of files) {
    const relFromWiki = path.relative(wikiDir, f).split(path.sep).join("/");
    const srcId = `wiki/${relFromWiki}`;
    const text = fs.readFileSync(f, "utf-8");
    WIKILINK_RE.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = WIKILINK_RE.exec(text))) {
      const target = m[1]!.trim();
      if (target.startsWith("#")) continue; // anchor-only links — ignore
      const tgtId =
        byKey.get(target) ??
        byKey.get(target.replace(/\.md$/, "")) ??
        byKey.get(target.toLowerCase());
      if (!tgtId || tgtId === srcId) continue;

      const key = `${srcId}→${tgtId}`;
      if (seenEdges.has(key)) continue;
      seenEdges.add(key);
      edges.push({ source: srcId, target: tgtId });

      nodes.get(srcId)!.degree += 1;
      nodes.get(tgtId)!.degree += 1;
    }
  }

  return {
    nodes: Array.from(nodes.values()),
    edges,
  };
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

function extractTitle(text: string): string | null {
  // frontmatter title
  const fm = /^---\n([\s\S]*?)\n---/.exec(text);
  if (fm) {
    const t = /^title:\s*(.+)$/m.exec(fm[1]!);
    if (t) return t[1]!.trim().replace(/^["']|["']$/g, "");
  }
  const h1 = /^#\s+(.+?)\s*$/m.exec(text);
  return h1 ? h1[1]! : null;
}

export function handleGraph(cfg: ServerConfig) {
  return (_req: Request, res: Response) => {
    res.json(buildGraph(cfg.wikiRoot));
  };
}

// ── Graph Insights (via graph-engine CLI) ──────────────────────────────────

interface InsightsCache {
  data: unknown;
  timestamp: number;
}

let insightsCache: InsightsCache | null = null;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export function handleGraphInsights(cfg: ServerConfig) {
  return (_req: Request, res: Response) => {
    if (insightsCache && Date.now() - insightsCache.timestamp < CACHE_TTL) {
      res.json(insightsCache.data);
      return;
    }

    try {
      const __dirname = path.dirname(url.fileURLToPath(import.meta.url));
      const repoRoot = path.resolve(__dirname, "../../..");
      const enginePath = path.resolve(repoRoot, "graph-engine", "dist", "index.js");

      if (!fs.existsSync(enginePath)) {
        res.status(500).json({
          error: "graph-engine not built",
          detail: `Run 'cd graph-engine && npm install && npx tsc' first.`,
        });
        return;
      }

      const dataPath = path.join(cfg.wikiRoot, "graph-data.json");
      if (!fs.existsSync(dataPath)) {
        execSync(`node "${enginePath}" --wiki "${cfg.wikiRoot}" --action build`, {
          stdio: "pipe",
          timeout: 30000,
          encoding: "utf-8",
        });
      }

      const stdout = execSync(
        `node "${enginePath}" --wiki "${cfg.wikiRoot}" --action insights`,
        { encoding: "utf-8", stdio: "pipe", timeout: 30000 },
      );

      const data = JSON.parse(stdout);
      insightsCache = { data, timestamp: Date.now() };
      res.json(data);
    } catch (err) {
      console.error("graph insights failed", err);
      res.status(500).json({ error: "Failed to get graph insights", detail: String(err) });
    }
  };
}
