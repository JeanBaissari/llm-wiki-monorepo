#!/usr/bin/env node
/**
 * LLM Wiki MCP Server — stdio-based server with 11 tools.
 *
 * LWM_07: Python sidecar + direct TypeScript imports replace per-call
 * subprocess spawning. Zero fork/exec overhead per tool call.
 *
 * Usage: node dist/index.js --wiki <path>  (or set LLM_WIKI_PATH)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import * as path from "node:path";
import * as fs from "node:fs/promises";
import * as fsSync from "node:fs";
import { fileURLToPath } from "node:url";

import {
  listDirectory,
  readFile,
  findMdFiles,
  fileExists,
} from "./wiki-fs.js";
import { buildIndex, search } from "./search.js";
import { discoverLayout, WikiLayout } from "./discover.js";
import { PythonSidecar } from "./sidecar.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ─── Config ──────────────────────────────────────────────────────────────────

interface ServerConfig {
  projects: Map<string, { root: string; layout: WikiLayout }>;
  defaultProject: string;
}

let config: ServerConfig;
let sidecar: PythonSidecar | null = null;

// ─── CLI Argument Parsing ───────────────────────────────────────────────────

let wikiPath = "";
let projectsDir = "";

for (let i = 0; i < process.argv.length; i++) {
  if (process.argv[i] === "--wiki" && i + 1 < process.argv.length) {
    wikiPath = process.argv[i + 1];
  }
  if (process.argv[i] === "--projects" && i + 1 < process.argv.length) {
    projectsDir = process.argv[i + 1];
  }
}

if (!wikiPath && !projectsDir) {
  wikiPath = process.env.LLM_WIKI_PATH ?? "";
}

if (wikiPath && projectsDir) {
  console.error("Cannot use both --wiki and --projects flags. Choose one mode.");
  process.exit(1);
}

if (!wikiPath && !projectsDir) {
  console.error(
    `Usage: ${process.argv[1] ?? "llm-wiki-mcp"} --wiki <path>  (or set LLM_WIKI_PATH)`,
  );
  console.error(
    `       ${process.argv[1] ?? "llm-wiki-mcp"} --projects <path>  (serves multiple wikis)`,
  );
  process.exit(1);
}

if (wikiPath) wikiPath = path.resolve(wikiPath);

// ─── Dynamic Module Loader ──────────────────────────────────────────────────

async function tryImport<T>(module: string): Promise<T | null> {
  try {
    return (await import(module)) as T;
  } catch {
    return null;
  }
}

// ─── Result Helpers ─────────────────────────────────────────────────────────

type TextContent = { type: "text"; text: string };
type ToolResult = { content: TextContent[]; isError?: boolean };

function textResult(text: string): ToolResult {
  return { content: [{ type: "text", text }] };
}

function errorResult(error: string): ToolResult {
  return {
    content: [{ type: "text", text: `Error: ${error}` }],
    isError: true,
  };
}

// ─── Helpers: sources dir, project scanning, wiki root resolution ──────────

function sourcesDir(layout: WikiLayout): string {
  return layout.raw_dir ?? path.join(layout.root, "raw");
}

async function scanProjects(basePath: string): Promise<Map<string, { root: string; layout: WikiLayout }>> {
  const projects = new Map<string, { root: string; layout: WikiLayout }>();
  const entries = await fs.readdir(basePath, { withFileTypes: true });
  const dirs = entries
    .filter((e) => e.isDirectory() && !e.name.startsWith("."))
    .sort((a, b) => a.name.localeCompare(b.name));
  for (const entry of dirs) {
    const projPath = path.join(basePath, entry.name);
    try {
      const layout = discoverLayout(projPath);
      if (layout.confidence >= 0.14) {
        projects.set(entry.name, { root: projPath, layout });
      }
    } catch {
      // skip — not a wiki
    }
  }
  return projects;
}

function getProjectConfig(toolArgs: Record<string, unknown>): { root: string; layout: WikiLayout } {
  const projectName = (toolArgs.project as string) || config.defaultProject;
  const project = config.projects.get(projectName);
  if (!project) {
    const available = [...config.projects.keys()].join(", ");
    throw new Error(`Unknown project: "${projectName}". Available: ${available}`);
  }
  return project;
}

// ─── Monorepo root resolution ─────────────────────────────────────────────

function monorepoRoot(): string {
  let dir = __dirname;
  for (let i = 0; i < 5; i++) {
    const candidate = path.join(dir, "skill", "scripts", "sidecar.py");
    if (fsSync.existsSync(candidate)) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return path.resolve(__dirname, "..", "..");
}

// ─── Tool Handler Implementations ───────────────────────────────────────────

/**
 * 1. llm_wiki_status — Check wiki health, return page count, last ingest,
 *    open review count.
 */
async function handleStatus(args: Record<string, unknown> = {}): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const exists = await fileExists(wp);
    if (!exists) {
      return textResult(
        `# LLM Wiki Status\n\n**Health:** ❌ Wiki directory not found\n**Path:** \`${wp}\``,
      );
    }

    const pages = await findMdFiles(layout.pages_dir);
    const pageCount = pages.length;

    let lastIngest: string | null = null;
    try {
      const metaPath = path.join(wp, "..", ".wiki-meta.json");
      if (await fileExists(metaPath)) {
        const raw = await readFile(metaPath);
        const meta = JSON.parse(raw);
        lastIngest = meta.lastIngest ?? null;
      }
    } catch {
      // ignore
    }

    let openReviews = 0;
    const reviewMod = await tryImport<{
      listReviews: (wp: string, status?: string) => Promise<{ status: string }[]>;
    }>("./review.js");
    if (reviewMod?.listReviews) {
      try {
        const reviews = await reviewMod.listReviews(layout.audit_dir ?? wp);
        openReviews = reviews.filter((r) => r.status === "open").length;
      } catch {
        // ignore
      }
    }

    const healthEmoji = pageCount > 0 ? "✅ Operational" : "⚠️  No pages found";
    const projectName = (args.project as string) || config.defaultProject;

    return textResult(
      [
        "# LLM Wiki Status",
        "",
        `**Project:** ${projectName}`,
        `**Health:** ${healthEmoji}`,
        `**Wiki Path:** \`${wp}\``,
        `**Page Count:** ${pageCount}`,
        `**Last Ingest:** ${lastIngest ?? "Never"}`,
        `**Open Reviews:** ${openReviews}`,
        `**Sidecar:** ${sidecar?.isRunning() ? "✅ Running" : "⚠️  Not running"}`,
      ].join("\n"),
    );
  } catch (e) {
    return errorResult(`Failed to get status: ${e}`);
  }
}

/**
 * 2. llm_wiki_files — List files in wiki/sources/all directories.
 */
async function handleFiles(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const root = (args.root as string) ?? "wiki";
    const recursive = (args.recursive as boolean) !== false;

    const dirs: { label: string; dir: string }[] = [];
    if (root === "wiki" || root === "all") {
      dirs.push({ label: "wiki", dir: layout.pages_dir });
    }
    if (root === "sources" || root === "all") {
      dirs.push({ label: "sources", dir: sourcesDir(layout) });
    }

    const lines: string[] = [];

    for (const { label, dir } of dirs) {
      const exists = await fileExists(dir);
      if (!exists) {
        lines.push(`## ${label}/ (directory not found)`);
        continue;
      }

      const { files, truncated } = await listDirectory(dir, recursive);
      lines.push(`## ${label}/`);
      if (files.length === 0) {
        lines.push("  _(empty)_");
      } else {
        for (const file of files) {
          const prefix = file.is_dir ? "📁" : "📄";
          const relPath = path.relative(dir, file.path);
          lines.push(`  ${prefix} ${relPath}`);
        }
        if (truncated) {
          lines.push(`  _… (truncated, more files exist)_`);
        }
      }
      lines.push("");
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Failed to list files: ${e}`);
  }
}

/**
 * 3. llm_wiki_read_file — Read a file, truncated at 120KB.
 */
async function handleReadFile(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const filePath = args.path as string | undefined;
    if (!filePath) {
      return errorResult("Missing required argument: path");
    }

    const resolved = path.isAbsolute(filePath)
      ? filePath
      : path.join(layout.pages_dir, filePath);

    const exists = await fileExists(resolved);
    if (!exists) {
      return errorResult(`File not found: ${resolved}`);
    }

    let content = await readFile(resolved);
    const maxBytes = 120 * 1024;

    if (Buffer.byteLength(content, "utf-8") > maxBytes) {
      const truncated = Buffer.from(content, "utf-8").subarray(0, maxBytes);
      content = truncated.toString("utf-8") + "\n\n_… (truncated at 120KB)_";
    }

    return textResult(content);
  } catch (e) {
    return errorResult(`Failed to read file: ${e}`);
  }
}

/**
 * 4. llm_wiki_reviews — List reviews, filterable by status.
 */
async function handleReviews(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const reviewMod = await tryImport<{
      listReviews: (
        wp: string,
        status?: string,
      ) => Promise<
        {
          id: string;
          title: string;
          type: string;
          severity: string;
          status: string;
          description: string;
          created: string;
          author: string;
        }[]
      >;
    }>("./review.js");

    if (!reviewMod?.listReviews) {
      return textResult(
        "# LLM Wiki Reviews\n\n_Review module not available. Install or build src/review.ts._",
      );
    }

    const status = (args.status as string) ?? "all";
    const reviews = await reviewMod.listReviews(layout.audit_dir ?? wp, status);

    if (reviews.length === 0) {
      return textResult(
        `# LLM Wiki Reviews\n\nNo reviews found${status !== "all" ? ` with status "${status}"` : ""}.`,
      );
    }

    const lines: string[] = [
      `# LLM Wiki Reviews (${reviews.length})`,
      "",
    ];

    for (const r of reviews) {
      const statusEmoji = r.status === "open" ? "🔴" : "✅";
      const severityTag =
        r.severity === "error"
          ? "**ERROR**"
          : r.severity === "warn"
            ? "*WARN*"
            : r.severity === "suggest"
              ? "_suggest_"
              : "info";
      lines.push(
        `### ${statusEmoji} ${r.title}`,
        `**ID:** \`${r.id}\`  **Type:** ${r.type}  **Severity:** ${severityTag}  **Status:** ${r.status}`,
        `**Author:** ${r.author}  **Created:** ${r.created}`,
        `**Description:** ${r.description}`,
        "",
      );
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Failed to list reviews: ${e}`);
  }
}

/**
 * 5. llm_wiki_search — FTS5 search over wiki pages.
 */
async function handleSearch(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const query = args.query as string | undefined;
    if (!query || query.trim() === "") {
      return errorResult("Missing required argument: query");
    }

    const topK = Math.min(Math.max((args.top_k as number) ?? 10, 1), 100);

    const results = await search(layout.root, query, topK);

    if (results.length === 0) {
      return textResult(
        `# Search Results\n\nNo results found for "${query}".`,
      );
    }

    const lines: string[] = [
      `# Search Results for "${query}" (${results.length})`,
      "",
    ];

    for (let i = 0; i < results.length; i++) {
      const r = results[i];
      const relPath = path.relative(layout.root, r.path);
      lines.push(
        `### ${i + 1}. ${r.title}`,
        `**Path:** \`${relPath}\`  **Score:** ${r.score.toFixed(4)}`,
        `${r.snippet || "(no snippet)"}`,
        "",
      );
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Search failed: ${e}`);
  }
}

// ─── Graph Tools (LWM_07: direct imports, split into separate tools) ─────

/**
 * 6. llm_wiki_graph — Combined graph tool (backward-compatible wrapper).
 *
 * Preserved for backward compatibility. Delegates to the split tools below.
 */
async function handleGraph(args: Record<string, unknown>): Promise<ToolResult> {
  const action = (args.action as string) ?? "build";

  switch (action) {
    case "build":
      return handleGraphBuild(args);
    case "insights":
      return handleGraphInsights(args);
    case "search":
      return handleGraphSearch(args);
    default:
      return errorResult(
        `Unknown graph action: "${action}". Use "build", "insights", or "search".`,
      );
  }
}

/**
 * 7. llm_wiki_graph_build — Build the knowledge graph.
 *
 * Imports buildWikiGraph from graph-engine directly (LWM_07).
 */
async function handleGraphBuild(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);

    const graphMod = await tryImport<{
      buildGraph: (wp: string) => Promise<{ nodes: { id: string; label: string }[]; edges: { source: string; target: string }[] }>;
    }>("./graph.js");

    if (!graphMod?.buildGraph) {
      return textResult(
        "# Graph: build\n\n_Graph module not available. Install or build src/graph.ts._",
      );
    }

    const result = await graphMod.buildGraph(layout.pages_dir);
    return textResult(
      [
        "# Graph Build Complete",
        "",
        `**Nodes:** ${result.nodes.length}`,
        `**Edges:** ${result.edges.length}`,
        "",
        "The knowledge graph has been rebuilt from the wiki content.",
      ].join("\n"),
    );
  } catch (e) {
    return errorResult(`Graph build failed: ${e}`);
  }
}

/**
 * 8. llm_wiki_graph_insights — Get graph insights (surprising connections, knowledge gaps).
 *
 * Imports findSurprisingConnections/detectKnowledgeGaps from graph-engine directly (LWM_07).
 */
async function handleGraphInsights(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);

    const graphMod = await tryImport<{
      getInsights: (wp: string) => Promise<string[]>;
    }>("./graph.js");

    if (!graphMod?.getInsights) {
      return textResult(
        "# Graph: insights\n\n_Graph module not available. Install or build src/graph.ts._",
      );
    }

    const insights = await graphMod.getInsights(layout.pages_dir);
    if (!insights || (Array.isArray(insights) && insights.length === 0)) {
      return textResult("# Graph Insights\n\nNo insights available.");
    }

    // Handle both old (string[]) and new (object) return formats
    if (Array.isArray(insights)) {
      const lines: string[] = ["# Graph Insights", ""];
      for (let i = 0; i < insights.length; i++) {
        lines.push(`${i + 1}. ${insights[i]}`);
      }
      return textResult(lines.join("\n"));
    }

    // Structured format from LWM_07
    const data = insights as unknown as {
      surprisingConnections?: Array<{ source: any; target: any; score: number; reasons: string[] }>;
      knowledgeGaps?: Array<{ title: string; description: string; suggestion: string }>;
    };

    const lines: string[] = ["# Graph Insights", ""];

    if (data.surprisingConnections?.length) {
      lines.push(`## Surprising Connections (${data.surprisingConnections.length})`, "");
      for (const sc of data.surprisingConnections) {
        const srcLabel = sc.source?.label ?? sc.source?.id ?? "?";
        const tgtLabel = sc.target?.label ?? sc.target?.id ?? "?";
        lines.push(`- **${srcLabel}** ↔ **${tgtLabel}** (score: ${sc.score.toFixed(2)})`);
        if (sc.reasons?.length) {
          lines.push(`  _${sc.reasons.join(", ")}_`);
        }
      }
      lines.push("");
    }

    if (data.knowledgeGaps?.length) {
      lines.push(`## Knowledge Gaps (${data.knowledgeGaps.length})`, "");
      for (const kg of data.knowledgeGaps) {
        lines.push(`- **${kg.title}**: ${kg.description}`);
        if (kg.suggestion) lines.push(`  → ${kg.suggestion}`);
      }
      lines.push("");
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Graph insights failed: ${e}`);
  }
}

/**
 * 9. llm_wiki_graph_search — Search the knowledge graph.
 *
 * Imports applyGraphSearch from graph-engine directly (LWM_07).
 */
async function handleGraphSearch(args: Record<string, unknown>): Promise<ToolResult> {
  const query = args.query as string | undefined;
  if (!query || query.trim() === "") {
    return errorResult("Missing required argument: query for graph search");
  }

  try {
    const { root: wp, layout } = getProjectConfig(args);

    const graphMod = await tryImport<{
      searchGraph: (wp: string, q: string) => Promise<{
        nodes: { id: string; label: string; type: string; path: string; linkCount: number; community: number }[];
        edges: any[];
        matchedNodeIds: string[];
      }>;
    }>("./graph.js");

    if (!graphMod?.searchGraph) {
      return textResult(
        "# Graph: search\n\n_Graph module not available. Install or build src/graph.ts._",
      );
    }

    const graphResult = await graphMod.searchGraph(layout.pages_dir, query);

    if (!graphResult || !graphResult.nodes || graphResult.nodes.length === 0) {
      return textResult(`# Graph Search: "${query}"\n\nNo results found.`);
    }

    const lines: string[] = [
      `# Graph Search Results for "${query}" (${graphResult.nodes.length})`,
      "",
    ];
    for (const r of graphResult.nodes) {
      lines.push(`- **${r.label}** (\`${r.id}\`)`);
    }
    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Graph search failed: ${e}`);
  }
}

// ─── Lint & Ingest Tools (LWM_07: sidecar RPC) ──────────────────────────

/**
 * 10. llm_wiki_lint — Run lint checks on the wiki via Python sidecar.
 */
async function handleLint(args: Record<string, unknown> = {}): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);

    const lintMod = await tryImport<{
      runLint: (wp: string, sidecar?: PythonSidecar | null) => Promise<{
        issues: { type: string; severity: string; page: string; detail: string }[];
        exitCode: number;
      }>;
    }>("./lint.js");

    if (!lintMod?.runLint) {
      return textResult(
        "# Lint Results\n\n_Lint module not available. Install or build src/lint.ts._",
      );
    }

    const lintResult = await lintMod.runLint(layout.pages_dir, sidecar);
    const issues = Array.isArray(lintResult) ? lintResult : lintResult.issues;

    if (!issues || issues.length === 0) {
      return textResult(
        "# Lint Results\n\n✅ No issues found. The wiki looks clean!",
      );
    }

    const bySeverity: Record<string, typeof issues> = {};
    for (const issue of issues) {
      (bySeverity[issue.severity] ??= []).push(issue);
    }

    const lines: string[] = [
      `# Lint Results (${issues.length} issues)`,
      "",
    ];

    const severityOrder = ["error", "warn", "suggest", "info"];
    for (const sev of severityOrder) {
      const group = bySeverity[sev];
      if (!group || group.length === 0) continue;
      const badge =
        sev === "error"
          ? "🔴 ERROR"
          : sev === "warn"
            ? "🟡 WARN"
            : sev === "suggest"
              ? "🔵 Suggest"
              : "⚪ Info";
      lines.push(`### ${badge} (${group.length})`, "");
      for (const issue of group) {
        lines.push(`- **${issue.type}** on \`${issue.page}\``);
        if (issue.detail) lines.push(`  ${issue.detail}`);
      }
      lines.push("");
    }

    return textResult(lines.join("\n"));
  } catch (e) {
    return errorResult(`Lint failed: ${e}`);
  }
}

/**
 * 11. llm_wiki_ingest — Trigger an ingest of a source file via Python sidecar.
 */
async function handleIngest(args: Record<string, unknown>): Promise<ToolResult> {
  try {
    const { root: wp, layout } = getProjectConfig(args);
    const sourcePath = args.source_path as string | undefined;
    if (!sourcePath) {
      return errorResult("Missing required argument: source_path");
    }

    const resolvedSource = path.isAbsolute(sourcePath)
      ? sourcePath
      : path.join(wp, sourcePath);

    const exists = await fileExists(resolvedSource);
    if (!exists) {
      return errorResult(`Source file not found: ${resolvedSource}`);
    }

    if (!sidecar?.isRunning()) {
      return errorResult(
        "Python sidecar is not running — cannot ingest. The sidecar may have failed to start.",
      );
    }

    const ingestMod = await tryImport<{
      runIngest: (
        sidecar: PythonSidecar,
        wikiRoot: string,
        sourcePath: string,
        options: Record<string, unknown>,
      ) => Promise<{
        success: boolean;
        pages_created: number;
        pages_updated: number;
        reviews_written: number;
        error: string;
      }>;
    }>("./ingest.js");

    if (!ingestMod?.runIngest) {
      return textResult(
        "# Ingest\n\n_Ingest module not available. Install or build src/ingest.ts._",
      );
    }

    const result = await ingestMod.runIngest(sidecar, layout.root, resolvedSource, {});

    if (!result.success) {
      return errorResult(`Ingest failed: ${result.error}`);
    }

    return textResult(
      [
        "# Ingest Complete",
        "",
        `**Source:** \`${resolvedSource}\``,
        "",
        `**Pages Created:** ${result.pages_created}`,
        `**Pages Updated:** ${result.pages_updated}`,
        `**Reviews Written:** ${result.reviews_written}`,
      ].join("\n"),
    );
  } catch (e: any) {
    const msg = e?.stderr ?? e?.stdout ?? String(e);
    return errorResult(`Ingest failed: ${msg}`);
  }
}

// ─── MCP Server Setup ───────────────────────────────────────────────────────

const PROJECT_PARAM = {
  project: {
    type: "string",
    description:
      "Project name. Required when serving multiple wikis (--projects mode). Defaults to the only/first project.",
  },
};

const TOOL_DEFINITIONS = [
  {
    name: "llm_wiki_status",
    description:
      "Check wiki status — health, page count, last ingest date, open review count.",
    inputSchema: {
      type: "object",
      properties: { ...PROJECT_PARAM },
      required: [],
    },
  },
  {
    name: "llm_wiki_files",
    description:
      "List files in the wiki or sources directory as a formatted file tree.",
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        root: {
          type: "string",
          enum: ["wiki", "sources", "all"],
          description: "Which directory to list (default: wiki)",
        },
        recursive: {
          type: "boolean",
          description: "List recursively (default: true)",
        },
      },
    },
  },
  {
    name: "llm_wiki_read_file",
    description:
      "Read the contents of a file. Truncated at 120KB. Path relative to wiki root if not absolute.",
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        path: {
          type: "string",
          description: "Path to the file (absolute or relative to wiki root)",
        },
      },
      required: ["path"],
    },
  },
  {
    name: "llm_wiki_reviews",
    description:
      "List wiki reviews, optionally filtered by status.",
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        status: {
          type: "string",
          enum: ["open", "resolved", "all"],
          description: "Filter by review status (default: all)",
        },
      },
    },
  },
  {
    name: "llm_wiki_search",
    description:
      "FTS5 full-text search over wiki markdown pages. Returns ranked results with snippets.",
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        query: {
          type: "string",
          description: "Search query",
        },
        top_k: {
          type: "number",
          description: "Number of results to return (default: 10, max: 100)",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "llm_wiki_graph",
    description:
      "Knowledge graph operations: build, insights, or search. (Backward-compatible wrapper — see llm_wiki_graph_build, _insights, _search for individual tools.)",
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        action: {
          type: "string",
          enum: ["build", "insights", "search"],
          description: "Graph action (default: build)",
        },
        query: {
          type: "string",
          description: 'Query string (required for action="search")',
        },
      },
      required: [],
    },
  },
  {
    name: "llm_wiki_graph_build",
    description:
      "Build the knowledge graph from wiki markdown files. Uses direct graph-engine import — zero subprocess.",
    inputSchema: {
      type: "object",
      properties: { ...PROJECT_PARAM },
      required: [],
    },
  },
  {
    name: "llm_wiki_graph_insights",
    description:
      "Get graph insights — surprising connections and knowledge gaps. Uses direct graph-engine import.",
    inputSchema: {
      type: "object",
      properties: { ...PROJECT_PARAM },
      required: [],
    },
  },
  {
    name: "llm_wiki_graph_search",
    description:
      "Search the knowledge graph for nodes matching a query. Uses direct graph-engine import.",
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        query: {
          type: "string",
          description: "Search query for graph nodes",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "llm_wiki_lint",
    description:
      "Run lint checks on wiki pages via Python sidecar. Reports errors, warnings, and suggestions.",
    inputSchema: {
      type: "object",
      properties: { ...PROJECT_PARAM },
      required: [],
    },
  },
  {
    name: "llm_wiki_ingest",
    description:
      "Trigger ingest of a source file into the wiki via Python sidecar. Zero subprocess — uses long-lived sidecar process.",
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        source_path: {
          type: "string",
          description: "Path to the source file to ingest (absolute or relative to wiki root)",
        },
      },
      required: ["source_path"],
    },
  },
];

// ─── Main ───────────────────────────────────────────────────────────────────

async function main() {
  // Build config: --projects mode or single-wiki mode
  if (projectsDir) {
    const resolvedProjects = path.resolve(projectsDir);
    const projects = await scanProjects(resolvedProjects);
    if (projects.size === 0) {
      console.error(`No wiki projects found in: ${resolvedProjects}`);
      process.exit(1);
    }
    const firstKey = projects.keys().next().value as string;
    config = { projects, defaultProject: firstKey };
  } else {
    try {
      const stat = await fs.stat(wikiPath);
      if (!stat.isDirectory()) {
        console.error(`Wiki path is not a directory: ${wikiPath}`);
        process.exit(1);
      }
    } catch {
      console.error(`Wiki path does not exist or is not accessible: ${wikiPath}`);
      process.exit(1);
    }
    const layout = discoverLayout(wikiPath);
    config = {
      projects: new Map([["default", { root: wikiPath, layout }]]),
      defaultProject: "default",
    };
  }

  // ── Pre-build search indexes for all projects ──────────────────────────
  for (const [name, project] of config.projects) {
    try {
      await buildIndex(project.root);
      console.error(`[startup] Search index ready for project: ${name}`);
    } catch (e) {
      console.error(`[startup] Search index build deferred for ${name}: ${e}`);
    }
  }

  // ── Start Python Sidecar (LWM_07) ──────────────────────────────────────
  // Use the default project's wiki root for the sidecar
  const defaultProject = config.projects.get(config.defaultProject);
  if (defaultProject) {
    try {
      const root = monorepoRoot();
      sidecar = new PythonSidecar(defaultProject.root, root);
      console.error(`[startup] Starting Python sidecar...`);
      await sidecar.start();
      console.error(`[startup] Python sidecar ready`);
    } catch (e) {
      console.error(`[startup] Python sidecar failed to start: ${e}`);
      console.error(`[startup] MCP server will run without Python-backed tools`);
      sidecar = null;
    }
  }

  // ── Graceful shutdown ──────────────────────────────────────────────────
  const shutdown = async () => {
    console.error("[shutdown] MCP server shutting down...");
    if (sidecar) {
      try {
        await sidecar.stop();
        console.error("[shutdown] Python sidecar stopped");
      } catch (e) {
        console.error(`[shutdown] Sidecar stop error: ${e}`);
      }
    }
    process.exit(0);
  };

  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);

  const server = new Server(
    { name: "llm-wiki-mcp", version: "1.0.0" },
    { capabilities: { tools: {} } },
  );

  // List tools handler
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: TOOL_DEFINITIONS,
  }));

  // Call tool handler
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    const toolArgs = (args ?? {}) as Record<string, unknown>;

    try {
      switch (name) {
        case "llm_wiki_status":
          return await handleStatus(toolArgs);
        case "llm_wiki_files":
          return await handleFiles(toolArgs);
        case "llm_wiki_read_file":
          return await handleReadFile(toolArgs);
        case "llm_wiki_reviews":
          return await handleReviews(toolArgs);
        case "llm_wiki_search":
          return await handleSearch(toolArgs);
        case "llm_wiki_graph":
          return await handleGraph(toolArgs);
        case "llm_wiki_graph_build":
          return await handleGraphBuild(toolArgs);
        case "llm_wiki_graph_insights":
          return await handleGraphInsights(toolArgs);
        case "llm_wiki_graph_search":
          return await handleGraphSearch(toolArgs);
        case "llm_wiki_lint":
          return await handleLint(toolArgs);
        case "llm_wiki_ingest":
          return await handleIngest(toolArgs);
        default:
          return errorResult(
            `Unknown tool: "${name}". Available tools: ${TOOL_DEFINITIONS.map((t) => t.name).join(", ")}`,
          );
      }
    } catch (e) {
      return errorResult(`Tool "${name}" failed: ${e}`);
    }
  });

  // Connect transport
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((e) => {
  console.error("Fatal server error:", e);
  process.exit(1);
});
