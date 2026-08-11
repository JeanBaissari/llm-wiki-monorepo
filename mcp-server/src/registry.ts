// MCP Server — Tool Registry
//
// Central registry of all tool definitions, parameter schemas,
// side-effect metadata, and tool call dispatch.

import type { PythonSidecar } from "./adapters/sidecar.js";

let sidecar: PythonSidecar | null = null;

export function setSidecar(s: PythonSidecar | null): void {
  sidecar = s;
}

export function getSidecar(): PythonSidecar | null {
  return sidecar;
}

export const PROJECT_PARAM = {
  project: {
    type: "string",
    description:
      "Project name. Required when serving multiple wikis (--projects mode). Defaults to the only/first project.",
  },
};

export const SIDE_EFFECT = {
  READ_ONLY: " [side_effect: read_only]",
  WRITE_PROJECT: " [side_effect: write_project]",
  WRITE_BACKUP: " [side_effect: write_backup]",
  EXTERNAL_PROCESS: " [side_effect: external_process]",
};

export const TOOL_DEFINITIONS = [
  {
    name: "llm_wiki_status",
    description:
      `Check wiki status — health, page count, last ingest date, open review count.${SIDE_EFFECT.READ_ONLY}`,
    inputSchema: {
      type: "object",
      properties: { ...PROJECT_PARAM },
      required: [],
    },
  },
  {
    name: "llm_wiki_files",
    description:
      `List files in the wiki or sources directory as a formatted file tree.${SIDE_EFFECT.READ_ONLY}`,
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
      `Read the contents of a file. Project-relative path only. Truncated at 120KB. Allow-listed directories: wiki, raw, audit, logs, plus PURPOSE.md, CLAUDE.md, SCHEMA.md.${SIDE_EFFECT.READ_ONLY}`,
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        path: {
          type: "string",
          description: "Project-relative path to the file (e.g. wiki/index.md). Absolute paths rejected.",
        },
      },
      required: ["path"],
    },
  },
  {
    name: "llm_wiki_reviews",
    description:
      `List wiki reviews, optionally filtered by status.${SIDE_EFFECT.READ_ONLY}`,
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
      `Full-text + semantic search over wiki markdown pages. Returns ranked results with snippets. Defaults to hybrid (BM25 + semantic vector KNN via RRF); requires the [semantic] extra + an embedded index and degrades to keyword otherwise. Set mode="keyword" to force lexical-only.${SIDE_EFFECT.READ_ONLY}`,
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
        mode: {
          type: "string",
          enum: ["keyword", "hybrid"],
          description:
            "Ranking mode (default: hybrid, LWM_032/ADR-0020). 'hybrid' fuses BM25 + semantic vector KNN via RRF and degrades to keyword when the semantic layer is unavailable; 'keyword' forces lexical-only.",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "llm_wiki_ask",
    description:
      `Grounded "ask this wiki" (LWM_033/ADR-0029): retrieves the LWM_030 community-summary pages + regular pages via the LWM_032 hybrid path with a summary-aware rerank (Python sidecar, deterministic + offline — no LLM call), and returns the grounded passages, citation stems, confidence, and faithfulness. The agent consumer synthesizes the answer from that context. Requires the Python sidecar; no sidecar → graceful error.${SIDE_EFFECT.READ_ONLY}`,
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        question: {
          type: "string",
          description: "The question to ground in the wiki",
        },
        top_k: {
          type: "number",
          description: "Number of grounded passages / citations (default: 10, max: 100)",
        },
      },
      required: ["question"],
    },
  },
  {
    name: "llm_wiki_graph",
    description:
      `Knowledge graph operations: build, insights, or search. (Backward-compatible wrapper — see llm_wiki_graph_build, _insights, _search for individual tools.)${SIDE_EFFECT.WRITE_PROJECT}`,
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
      `Build the knowledge graph from wiki markdown files. Uses direct graph-engine import — zero subprocess.${SIDE_EFFECT.WRITE_PROJECT}`,
    inputSchema: {
      type: "object",
      properties: { ...PROJECT_PARAM },
      required: [],
    },
  },
  {
    name: "llm_wiki_graph_insights",
    description:
      `Get graph insights — surprising connections and knowledge gaps. Uses direct graph-engine import.${SIDE_EFFECT.READ_ONLY}`,
    inputSchema: {
      type: "object",
      properties: { ...PROJECT_PARAM },
      required: [],
    },
  },
  {
    name: "llm_wiki_graph_search",
    description:
      `Search the knowledge graph for nodes matching a query. Uses direct graph-engine import.${SIDE_EFFECT.READ_ONLY}`,
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
      `Run lint checks on wiki pages via Python sidecar. Reports errors, warnings, and suggestions.${SIDE_EFFECT.EXTERNAL_PROCESS}`,
    inputSchema: {
      type: "object",
      properties: { ...PROJECT_PARAM },
      required: [],
    },
  },
  {
    name: "llm_wiki_ingest",
    description:
      `Trigger ingest of a source file into the wiki via Python sidecar. Zero subprocess — uses long-lived sidecar process.${SIDE_EFFECT.WRITE_PROJECT}`,
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        source_path: {
          type: "string",
          description: "Path to the source file to ingest (project-relative). Absolute paths rejected.",
        },
      },
      required: ["source_path"],
    },
  },
  {
    name: "llm_wiki_suggest_links",
    description:
      `Suggest missing wikilinks for wiki pages. Analyzes page text against the entity registry and returns link suggestions with confidence scores.${SIDE_EFFECT.READ_ONLY}`,
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        threshold: {
          type: "number",
          description: "Minimum suggestion score to include (default: 0.3, range: 0.0–1.0)",
        },
        limit: {
          type: "number",
          description: "Maximum suggestions to return (default: 20)",
        },
        pages: {
          type: "array",
          items: { type: "string" },
          description: "Specific page stems to analyze (default: all pages)",
        },
      },
    },
  },
  {
    name: "llm_wiki_backup",
    description:
      `Create a timestamped snapshot backup of the wiki. Archives wiki pages, logs, and audits into a tar.gz with integrity verification.${SIDE_EFFECT.WRITE_BACKUP}`,
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
      },
    },
  },
  {
    name: "llm_wiki_discover_entities",
    description:
      `Discover all entities registered in the wiki. Returns the entity registry with names, paths, types, and aliases. Optionally filter by entity type.${SIDE_EFFECT.READ_ONLY}`,
    inputSchema: {
      type: "object",
      properties: {
        ...PROJECT_PARAM,
        entity_type: {
          type: "string",
          description: "Filter by entity type (e.g., 'person', 'concept', 'tool'). Default: all.",
        },
      },
    },
  },
];

// ── Tool Dispatch ────────────────────────────────────────────────────────

type TextContent = { type: "text"; text: string };
type ToolResult = { content: TextContent[]; isError?: boolean };

function errorResult(text: string): ToolResult {
  return { content: [{ type: "text", text: `Error: ${text}` }], isError: true };
}

export async function handleCallTool(name: string, toolArgs: Record<string, unknown>): Promise<ToolResult> {
  try {
    switch (name) {
      case "llm_wiki_status": {
        const { handleStatus } = await import("./tools/status.js");
        return await handleStatus(toolArgs);
      }
      case "llm_wiki_files": {
        const { handleFiles } = await import("./tools/files.js");
        return await handleFiles(toolArgs);
      }
      case "llm_wiki_read_file": {
        const { handleReadFile } = await import("./tools/read-file.js");
        return await handleReadFile(toolArgs);
      }
      case "llm_wiki_reviews": {
        const { handleReviews } = await import("./tools/reviews.js");
        return await handleReviews(toolArgs);
      }
      case "llm_wiki_search": {
        const { handleSearch } = await import("./tools/search.js");
        return await handleSearch(toolArgs);
      }
      case "llm_wiki_ask": {
        const { handleAsk } = await import("./tools/ask.js");
        return await handleAsk(toolArgs);
      }
      case "llm_wiki_graph": {
        const { handleGraph } = await import("./tools/graph.js");
        return await handleGraph(toolArgs);
      }
      case "llm_wiki_graph_build": {
        const { handleGraphBuild } = await import("./tools/graph.js");
        return await handleGraphBuild(toolArgs);
      }
      case "llm_wiki_graph_insights": {
        const { handleGraphInsights } = await import("./tools/graph.js");
        return await handleGraphInsights(toolArgs);
      }
      case "llm_wiki_graph_search": {
        const { handleGraphSearch } = await import("./tools/graph.js");
        return await handleGraphSearch(toolArgs);
      }
      case "llm_wiki_lint": {
        const { handleLint } = await import("./tools/lint.js");
        return await handleLint(toolArgs);
      }
      case "llm_wiki_ingest": {
        const { handleIngest } = await import("./tools/ingest.js");
        return await handleIngest(toolArgs);
      }
      case "llm_wiki_suggest_links": {
        const { handleSuggestLinks } = await import("./tools/suggest.js");
        return await handleSuggestLinks(toolArgs);
      }
      case "llm_wiki_backup": {
        const { handleBackup } = await import("./tools/backup.js");
        return await handleBackup(toolArgs);
      }
      case "llm_wiki_discover_entities": {
        const { handleDiscoverEntities } = await import("./tools/entities.js");
        return await handleDiscoverEntities(toolArgs);
      }
      default:
        return errorResult(
          `Unknown tool: "${name}". Available tools: ${TOOL_DEFINITIONS.map((t) => t.name).join(", ")}`,
        );
    }
  } catch (e) {
    return errorResult(`Tool "${name}" failed: ${e}`);
  }
}
