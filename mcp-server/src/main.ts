#!/usr/bin/env node
/**
 * LLM Wiki MCP Server — stdio-based server with 14 tools.
 *
 * LWM_07: Python sidecar + direct TypeScript imports replace per-call
 * subprocess spawning. Zero fork/exec overhead per tool call.
 *
 * Usage: node dist/main.js --wiki <path>  (or set LLM_WIKI_PATH)
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import * as path from "node:path";
import * as fs from "node:fs/promises";

import { buildIndex } from "./search.js";
import { PythonSidecar } from "./adapters/sidecar.js";
import { setConfig, monorepoRoot, scanProjects } from "./projects/config.js";
import { discoverLayout, WikiLayout } from "./projects/discover.js";
import type { ServerConfig } from "./projects/config.js";
import { setSidecar, TOOL_DEFINITIONS, handleCallTool } from "./registry.js";

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

// ─── Main ───────────────────────────────────────────────────────────────────

async function main() {
  // Build config: --projects mode or single-wiki mode
  let config: ServerConfig;

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

  setConfig(config);

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
  const defaultProject = config.projects.get(config.defaultProject);
  let sidecar: PythonSidecar | null = null;
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
  setSidecar(sidecar);

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
    return await handleCallTool(name, toolArgs);
  });

  // Connect transport
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((e) => {
  console.error("Fatal server error:", e);
  process.exit(1);
});
