#!/usr/bin/env node
/**
 * LLM Wiki MCP Server — stdio-based server with 8 tools.
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
import { fileURLToPath } from "node:url";

import {
  listDirectory,
  readFile,
  findMdFiles,
  fileExists,
} from "./wiki-fs.js";
import { buildIndex, search } from "./search.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ─── CLI Argument Parsing ───────────────────────────────────────────────────

let wikiPath = "";
for (let i = 0; i < process.argv.length; i++) {
  if (process.argv[i] === "--wiki" && i + 1 < process.argv.length) {
    wikiPath = process.argv[i + 1];
    break;
  }
}
if (!wikiPath) wikiPath = process.env.LLM_WIKI_PATH ?? "";
if (!wikiPath) {
  console.error(
    `Usage: ${process.argv[1] ?? "llm-wiki-mcp"} --wiki <path>  (or set LLM_WIKI_PATH)`,
  );
  process.exit(1);
}

// Resolve wiki path and validate it
wikiPath = path.resolve(wikiPath);

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

// ─── Helper: sources dir alongside wiki ─────────────────────────────────────

function sourcesDir(): string {
  return path.join(path.dirname(wikiPath), "sources");
}

// ─── Tool Handler Implementations ───────────────────────────────────────────

/**
 * 1. llm_wiki_status — Check wiki health, return page count, last ingest,
 *    open review count.
 */
async function handleStatus(): Promise<ToolResult> {
  try {
    const exists = await fileExists(wikiPath);
    if (!exists) {
      return textResult(
        `# LLM Wiki Status\n\n**Health:** ❌ Wiki directory not found\n**Path:** \`${wikiPath}\``,
      );
    }

    const pages = await findMdFiles(wikiPath);
    const pageCount = pages.length;

    // Attempt to read metadata for last ingest date
    let lastIngest: string | null = null;
    try {
      const metaPath = path.join(wikiPath, "..", ".wiki-meta.json");
      if (await fileExists(metaPath)) {
        const raw = await readFile(metaPath);
        const meta = JSON.parse(raw);
        lastIngest = meta.lastIngest ?? null;
      }
    } catch {
      // ignore
    }

    // Try loading review module for open review count
    let openReviews = 0;
    const reviewMod = await tryImport<{
      listReviews: (wp: string, status?: string) => Promise<{ status: string }[]>;
    }>("./review.js");
    if (reviewMod?.listReviews) {
      try {
        const reviews = await reviewMod.listReviews(wikiPath);
        openReviews = reviews.filter((r) => r.status === "open").length;
      } catch {
        // ignore
      }
    }

    const healthEmoji = pageCount > 0 ? "✅ Operational" : "⚠️  No pages found";

    return textResult(
      [
        "# LLM Wiki Status",
        "",
        `**Health:** ${healthEmoji}`,
        `**Wiki Path:** \`${wikiPath}\``,
        `**Page Count:** ${pageCount}`,
        `**Last Ingest:** ${lastIngest ?? "Never"}`,
        `**Open Reviews:** ${openReviews}`,
      ].join("\n"),
    );
  } catch (e) {
    return errorResult(`Failed to get status: ${e}`);
  }
}

/**
 * 2. llm_wiki_files — List files in wiki/sources/all directories.
 */
async function handleFiles(args: {
  root?: string;
  recursive?: boolean;
}): Promise<ToolResult> {
  try {
    const root = args.root ?? "wiki";
    const recursive = args.recursive !== false;

    const dirs: { label: string; dir: string }[] = [];
    if (root === "wiki" || root === "all") {
      dirs.push({ label: "wiki", dir: wikiPath });
    }
    if (root === "sources" || root === "all") {
      dirs.push({ label: "sources", dir: sourcesDir() });
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
async function handleReadFile(args: { path?: string }): Promise<ToolResult> {
  try {
    const filePath = args.path;
    if (!filePath) {
      return errorResult("Missing required argument: path");
    }

    // Resolve relative to wikiPath if not absolute
    const resolved = path.isAbsolute(filePath)
      ? filePath
      : path.join(wikiPath, filePath);

    const exists = await fileExists(resolved);
    if (!exists) {
      return errorResult(`File not found: ${resolved}`);
    }

    let content = await readFile(resolved);
    const maxBytes = 120 * 1024; // 120KB

    if (Buffer.byteLength(content, "utf-8") > maxBytes) {
      // Truncate at 120KB boundary
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
async function handleReviews(args: {
  status?: string;
}): Promise<ToolResult> {
  try {
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

    const status = args.status ?? "all";
    const reviews = await reviewMod.listReviews(wikiPath, status);

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
 * 5. llm_wiki_search — BM25 search over wiki pages.
 */
async function handleSearch(args: {
  query?: string;
  top_k?: number;
}): Promise<ToolResult> {
  try {
    const query = args.query;
    if (!query || query.trim() === "") {
      return errorResult("Missing required argument: query");
    }

    const topK = Math.min(Math.max(args.top_k ?? 10, 1), 100);

    const results = await search(wikiPath, query, topK);

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
      const relPath = path.relative(wikiPath, r.path);
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

/**
 * 6. llm_wiki_graph — Graph operations (build, insights, search).
 */
async function handleGraph(args: {
  action?: string;
  query?: string;
}): Promise<ToolResult> {
  try {
    const action = args.action ?? "build";

    const graphMod = await tryImport<{
      buildGraph: (wp: string) => Promise<{ nodes: { id: string; label: string }[]; edges: { source: string; target: string }[] }>;
      getInsights: (wp: string) => Promise<string[]>;
      searchGraph: (wp: string, q: string) => Promise<
        { nodes: { id: string; label: string; type: string; path: string; linkCount: number; community: number }[]; edges: any[]; matchedNodeIds: string[] }
      >;
    }>("./graph.js");

    if (!graphMod) {
      return textResult(
        `# Graph: ${action}\n\n_Graph module not available. Install or build src/graph.ts._`,
      );
    }

    switch (action) {
      case "build": {
        if (!graphMod.buildGraph) {
          return textResult("# Graph: build\n\n_buildGraph not available in graph module._");
        }
        const result = await graphMod.buildGraph(wikiPath);
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
      }

      case "insights": {
        if (!graphMod.getInsights) {
          return textResult("# Graph: insights\n\n_getInsights not available in graph module._");
        }
        const insights = await graphMod.getInsights(wikiPath);
        if (!insights || insights.length === 0) {
          return textResult("# Graph Insights\n\nNo insights available.");
        }
        const lines: string[] = ["# Graph Insights", ""];
        for (let i = 0; i < insights.length; i++) {
          lines.push(`${i + 1}. ${insights[i]}`);
        }
        return textResult(lines.join("\n"));
      }

      case "search": {
        const query = args.query;
        if (!query || query.trim() === "") {
          return errorResult("Missing required argument: query for graph search");
        }
        if (!graphMod.searchGraph) {
          return textResult("# Graph: search\n\n_searchGraph not available in graph module._");
        }
        const graphResult = await graphMod.searchGraph(wikiPath, query);
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
      }

      default:
        return errorResult(
          `Unknown graph action: "${action}". Use "build", "insights", or "search".`,
        );
    }
  } catch (e) {
    return errorResult(`Graph operation failed: ${e}`);
  }
}

/**
 * 7. llm_wiki_lint — Run lint checks on the wiki.
 */
async function handleLint(): Promise<ToolResult> {
  try {
    const lintMod = await tryImport<{
      runLint: (wp: string) => Promise<
        { issues: { type: string; severity: string; page: string; detail: string }[]; exitCode: number }
      >;
    }>("./lint.js");

    if (!lintMod?.runLint) {
      return textResult(
        "# Lint Results\n\n_Lint module not available. Install or build src/lint.ts._",
      );
    }

    const lintResult = await lintMod.runLint(wikiPath);
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
 * 8. llm_wiki_ingest — Trigger an ingest of a source file.
 */
async function handleIngest(args: {
  source_path?: string;
}): Promise<ToolResult> {
  try {
    const sourcePath = args.source_path;
    if (!sourcePath) {
      return errorResult("Missing required argument: source_path");
    }

    // Resolve source path
    const resolvedSource = path.isAbsolute(sourcePath)
      ? sourcePath
      : path.join(wikiPath, sourcePath);

    const exists = await fileExists(resolvedSource);
    if (!exists) {
      return errorResult(`Source file not found: ${resolvedSource}`);
    }

    // Find ingest script using __dirname (dist/ → monorepo root)
    const scriptPath = path.resolve(__dirname, "../..", "skill", "scripts", "ingest.py");

    if (!(await fileExists(scriptPath))) {
      return errorResult(
        `Ingest script not found at: ${scriptPath}`,
      );
    }

    // Run python3 ingest.py with wiki root as first positional arg
    const { execSync } = await import("node:child_process");
    const output = execSync(
      `python3 "${scriptPath}" "${wikiPath}" "${resolvedSource}"`,
      { encoding: "utf-8", timeout: 120_000, maxBuffer: 10 * 1024 * 1024 },
    );

    return textResult(
      [
        "# Ingest Complete",
        "",
        `**Source:** \`${resolvedSource}\``,
        `**Script:** \`${scriptPath}\``,
        "",
        "**Output:**",
        "```",
        output.trim(),
        "```",
      ].join("\n"),
    );
  } catch (e: any) {
    const msg = e?.stderr ?? e?.stdout ?? String(e);
    return errorResult(`Ingest failed: ${msg}`);
  }
}

// ─── MCP Server Setup ───────────────────────────────────────────────────────

const TOOL_DEFINITIONS = [
  {
    name: "llm_wiki_status",
    description:
      "Check wiki status — health, page count, last ingest date, open review count.",
    inputSchema: {
      type: "object",
      properties: {},
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
      "BM25 full-text search over wiki markdown pages. Returns ranked results with snippets.",
    inputSchema: {
      type: "object",
      properties: {
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
      "Knowledge graph operations: build, insights, or search.",
    inputSchema: {
      type: "object",
      properties: {
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
    name: "llm_wiki_lint",
    description:
      "Run lint checks on wiki pages. Reports errors, warnings, and suggestions.",
    inputSchema: {
      type: "object",
      properties: {},
      required: [],
    },
  },
  {
    name: "llm_wiki_ingest",
    description:
      "Trigger ingest of a source file into the wiki. Runs python3 skill/scripts/ingest.py.",
    inputSchema: {
      type: "object",
      properties: {
        source_path: {
          type: "string",
          description:
            "Path to the source file to ingest (absolute or relative to wiki root)",
        },
      },
      required: ["source_path"],
    },
  },
];

// ─── Main ───────────────────────────────────────────────────────────────────

async function main() {
  // Validate wiki path up front
  try {
    const stat = await fs.stat(wikiPath);
    if (!stat.isDirectory()) {
      console.error(`Wiki path is not a directory: ${wikiPath}`);
      process.exit(1);
    }
  } catch (e) {
    console.error(`Wiki path does not exist or is not accessible: ${wikiPath}`);
    process.exit(1);
  }

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
          return await handleStatus();
        case "llm_wiki_files":
          return await handleFiles(toolArgs as { root?: string; recursive?: boolean });
        case "llm_wiki_read_file":
          return await handleReadFile(toolArgs as { path?: string });
        case "llm_wiki_reviews":
          return await handleReviews(toolArgs as { status?: string });
        case "llm_wiki_search":
          return await handleSearch(toolArgs as { query?: string; top_k?: number });
        case "llm_wiki_graph":
          return await handleGraph(toolArgs as { action?: string; query?: string });
        case "llm_wiki_lint":
          return await handleLint();
        case "llm_wiki_ingest":
          return await handleIngest(toolArgs as { source_path?: string });
        default:
          return errorResult(`Unknown tool: "${name}". Available tools: ${TOOL_DEFINITIONS.map((t) => t.name).join(", ")}`);
      }
    } catch (e) {
      return errorResult(`Tool "${name}" failed: ${e}`);
    }
  });

  // Connect transport
  const transport = new StdioServerTransport();
  await server.connect(transport);

  // Keep process alive — the transport handles stdin/stdout
}

main().catch((e) => {
  console.error("Fatal server error:", e);
  process.exit(1);
});
