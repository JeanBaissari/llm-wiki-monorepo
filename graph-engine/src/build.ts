// ============================================================
// graph-engine/src/build.ts — Wiki Markdown → Graph Builder
// ============================================================

import * as fs from 'node:fs';
import * as path from 'node:path';
import type { GraphNode, GraphEdge, GraphData } from './types.js';
import { calculateRelevance } from './relevance.js';

// ============================================================
// Types
// ============================================================

interface ParsedPage {
  id: string; // relative path without .md, e.g. "entities/andrej-karpathy"
  label: string;
  type: string;
  path: string; // relative path, e.g. "entities/andrej-karpathy.md"
  sources: string[];
  wikilinks: string[];
}

// ============================================================
// Frontmatter parser (no external YAML dep)
// ============================================================

/**
 * Parse YAML frontmatter from markdown content.
 * Returns the frontmatter data and the body content.
 */
function parseFrontmatter(content: string): { data: Record<string, unknown>; body: string } {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) return { data: {}, body: content };

  const yaml = match[1];
  const body = match[2];
  const data: Record<string, unknown> = {};

  for (const line of yaml.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;

    const colonIndex = trimmed.indexOf(':');
    if (colonIndex === -1) continue;

    const key = trimmed.slice(0, colonIndex).trim();
    let rawValue: string = trimmed.slice(colonIndex + 1).trim();

    // Parse inline arrays: [item1, item2]
    if (rawValue.startsWith('[') && rawValue.endsWith(']')) {
      const items = rawValue
        .slice(1, -1)
        .split(',')
        .map((s) => s.trim().replace(/^['"]|['"]$/g, ''))
        .filter(Boolean);
      data[key] = items;
    }
    // Parse booleans
    else if (rawValue === 'true') data[key] = true;
    else if (rawValue === 'false') data[key] = false;
    // Parse numbers
    else if (/^\d+$/.test(rawValue)) data[key] = parseInt(rawValue, 10);
    // String value
    else {
      data[key] = rawValue.replace(/^['"]|['"]$/g, '');
    }
  }

  return { data, body };
}

// ============================================================
// Wikilink extraction
// ============================================================

/**
 * Extract [[wikilinks]] from markdown body content.
 * Handles aliases: [[Page Title|display text]] → "Page Title"
 * Handles paths: [[concepts/Foo/index|Foo]] → "concepts/Foo/index"
 */
function extractWikilinks(body: string): string[] {
  const regex = /\[\[([^\]]+)\]\]/g;
  const links: string[] = [];
  let match: RegExpExecArray | null;
  while ((match = regex.exec(body)) !== null) {
    const target = match[1].split('|')[0].trim();
    if (target) links.push(target);
  }
  return links;
}

/**
 * Extract the first H1 heading (# Title) from markdown body.
 * Used as fallback when frontmatter has no title.
 */
function extractH1(body: string): string | null {
  const match = body.match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : null;
}

// ============================================================
// Node ID resolution
// ============================================================

/**
 * Build a lookup map from page labels (and normalized forms) to node IDs.
 * Enables resolution of [[Page Title]] → "entities/andrej-karpathy".
 */
function buildTitleIndex(pages: ParsedPage[]): Map<string, string> {
  const index = new Map<string, string>();

  for (const page of pages) {
    // Exact label → ID
    index.set(page.label.toLowerCase(), page.id);

    // Normalized label (slugified) → ID
    const slug = page.label
      .toLowerCase()
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '');
    index.set(slug, page.id);

    // ID itself → ID (so path-like wikilinks resolve directly)
    index.set(page.id.toLowerCase(), page.id);

    // Last segment of path (filename without extension) → ID
    const basename = path.basename(page.id);
    index.set(basename.toLowerCase(), page.id);
  }

  return index;
}

/**
 * Resolve a [[wikilink]] target string to a node ID.
 * Returns null if no matching page is found.
 */
function resolveWikilink(
  wikilink: string,
  titleIndex: Map<string, string>,
): string | null {
  const key = wikilink.toLowerCase().trim();

  // Direct lookup
  const direct = titleIndex.get(key);
  if (direct) return direct;

  // Try slugified version
  const slug = key.replace(/\s+/g, '-').replace(/[^a-z0-9-/_]/g, '');
  const slugMatch = titleIndex.get(slug);
  if (slugMatch) return slugMatch;

  // If wikilink looks like a path (contains /), try resolving just the basename
  if (key.includes('/')) {
    const basename = key.split('/').pop()?.replace(/\.md$/i, '') ?? '';
    const baseMatch = titleIndex.get(basename);
    if (baseMatch) return baseMatch;
  }

  return null;
}

// ============================================================
// File discovery
// ============================================================

/**
 * Recursively find all .md files under a directory.
 */
function findMdFiles(dir: string): string[] {
  const files: string[] = [];

  function walk(current: string) {
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (entry.isFile() && entry.name.endsWith('.md')) {
        files.push(fullPath);
      }
    }
  }

  walk(dir);
  return files;
}

// ============================================================
// Main builder
// ============================================================

/**
 * Build a GraphData from wiki markdown files.
 *
 * Pipeline:
 * 1. Recursively find all .md files under wikiPath
 * 2. Parse frontmatter (title, type, sources) and extract [[wikilinks]]
 * 3. Skip pages with type === "query"
 * 4. Build GraphNode[] with linkCount (outbound + inbound wikilinks)
 * 5. Build GraphEdge[] by resolving wikilinks to node IDs, deduplicating
 * 6. Run calculateRelevance on each edge to set weight
 *
 * @param wikiPath - Path to the wiki/ directory
 * @throws {Error} If wikiPath does not exist
 */
export async function buildWikiGraph(wikiPath: string): Promise<GraphData> {
  // Validate wiki path
  if (!fs.existsSync(wikiPath)) {
    throw new Error(`Wiki directory not found: ${wikiPath}`);
  }

  // ── Step 1: Find all .md files ────────────────────────────
  const mdFiles = findMdFiles(wikiPath);

  if (mdFiles.length === 0) {
    return { nodes: [], edges: [], communities: [] };
  }

  // ── Step 2-3: Parse files, skip query pages ───────────────
  const pages: ParsedPage[] = [];

  for (const filePath of mdFiles) {
    const content = fs.readFileSync(filePath, 'utf-8');
    const { data, body } = parseFrontmatter(content);

    const relPath = path.relative(wikiPath, filePath);
    const id = relPath.replace(/\.md$/i, '');
    const label =
      (data.title as string) ||
      extractH1(body) ||
      path.basename(filePath, '.md');
    const type = (data.type as string) || 'concept';
    const sources = Array.isArray(data.sources)
      ? (data.sources as string[])
      : [];
    const wikilinks = extractWikilinks(body);

    // Skip hidden / query pages
    if (type === 'query') continue;

    pages.push({ id, label, type, path: relPath, sources, wikilinks });
  }

  // ── Step 4: Build nodes ───────────────────────────────────
  const nodeMap = new Map<string, GraphNode>();
  const linkCounts = new Map<string, number>();
  const nodes: GraphNode[] = [];

  for (const page of pages) {
    const node: GraphNode = {
      id: page.id,
      label: page.label,
      type: page.type,
      path: page.path,
      linkCount: 0, // computed below
      community: 0, // assigned by Louvain later
    };
    nodeMap.set(node.id, node);
    nodes.push(node);
    linkCounts.set(node.id, 0);
  }

  // ── Step 5: Build edges ───────────────────────────────────
  const titleIndex = buildTitleIndex(pages);
  const edgeSet = new Set<string>(); // dedup key: "source|target" (sorted)
  const edges: GraphEdge[] = [];

  for (const page of pages) {
    for (const wikilink of page.wikilinks) {
      const targetId = resolveWikilink(wikilink, titleIndex);

      // Only create edges to known nodes
      if (targetId && nodeMap.has(targetId)) {
        // Deduplicate: sort IDs so A↔B and B↔A collapse to same key
        const key =
          page.id < targetId
            ? `${page.id}|${targetId}`
            : `${targetId}|${page.id}`;

        if (!edgeSet.has(key)) {
          edgeSet.add(key);
          edges.push({
            source: page.id,
            target: targetId,
            weight: 0, // set below
          });
        }

        // Count links (both outbound and inbound)
        linkCounts.set(page.id, (linkCounts.get(page.id) ?? 0) + 1);
        linkCounts.set(targetId, (linkCounts.get(targetId) ?? 0) + 1);
      }
    }
  }

  // Update linkCount on each node
  for (const node of nodes) {
    node.linkCount = linkCounts.get(node.id) ?? 0;
  }

  // ── Step 6: Calculate relevance weights ───────────────────
  // Build enriched node map with sources for signal 2 support
  const enrichedMap = new Map<string, GraphNode>();
  for (const page of pages) {
    const node = nodeMap.get(page.id);
    if (node) {
      // Attach sources as an extra property (used by calculateRelevance)
      (node as GraphNode & { sources: string[] }).sources = page.sources;
      enrichedMap.set(node.id, node);
    }
  }

  for (const edge of edges) {
    const nodeA = enrichedMap.get(edge.source);
    const nodeB = enrichedMap.get(edge.target);
    if (nodeA && nodeB) {
      edge.weight = calculateRelevance(
        nodeA,
        nodeB,
        nodes,
        edges,
        enrichedMap,
      );
    }
  }

  return { nodes, edges, communities: [] };
}

/**
 * Build a RetrievalGraph from wiki markdown files.
 * Returns the graph in the format expected by the original nashsu
 * relevance model (Map-based, with outLinks and sources on each node).
 *
 * @param wikiPath - Path to the wiki/ directory
 */
export async function buildRetrievalGraph(
  wikiPath: string,
): Promise<Map<string, import('./relevance.js').RetrievalNode>> {
  const graphData = await buildWikiGraph(wikiPath);

  const nodes = new Map<string, import('./relevance.js').RetrievalNode>();

  // First pass: create all nodes
  for (const gn of graphData.nodes) {
    nodes.set(gn.id, {
      id: gn.id,
      outLinks: new Set<string>(),
      sources: [],
      type: gn.type,
    });
  }

  // Second pass: populate outLinks and sources from edges + enriched data
  for (const edge of graphData.edges) {
    const src = nodes.get(edge.source);
    const tgt = nodes.get(edge.target);
    if (src) src.outLinks.add(edge.target);
    if (tgt) tgt.outLinks.add(edge.source);
  }

  return nodes;
}
