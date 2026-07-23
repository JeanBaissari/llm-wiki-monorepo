// MCP Server — Project Config
//
// Central server configuration, project scanning, and shared utilities.

import * as path from "node:path";
import * as fs from "node:fs/promises";
import * as fsSync from "node:fs";
import { fileURLToPath } from "node:url";
import { discoverLayout, WikiLayout } from "./discover.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export interface ServerConfig {
  projects: Map<string, { root: string; layout: WikiLayout }>;
  defaultProject: string;
}

export let config: ServerConfig;

export function setConfig(c: ServerConfig): void {
  config = c;
}

export function getProjectConfig(toolArgs: Record<string, unknown>): { root: string; layout: WikiLayout } {
  const projectName = (toolArgs.project as string) || config.defaultProject;
  const project = config.projects.get(projectName);
  if (!project) {
    const available = [...config.projects.keys()].join(", ");
    throw new Error(`Unknown project: "${projectName}". Available: ${available}`);
  }
  return project;
}

export async function scanProjects(basePath: string): Promise<Map<string, { root: string; layout: WikiLayout }>> {
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

export function monorepoRoot(): string {
  let dir = __dirname;
  for (let i = 0; i < 7; i++) {
    const candidate = path.join(dir, "skill", "scripts", "sidecar.py");
    if (fsSync.existsSync(candidate)) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return path.resolve(__dirname, "..", "..", "..");
}

export function sourcesDir(layout: WikiLayout): string {
  return layout.raw_dir ?? path.join(layout.root, "raw");
}

// ─── Dynamic Module Loader ──────────────────────────────────────────────────

export async function tryImport<T>(module: string): Promise<T | null> {
  try {
    return (await import(module)) as T;
  } catch {
    return null;
  }
}

// ─── Result Helpers ─────────────────────────────────────────────────────────

export type TextContent = { type: "text"; text: string };
export type ToolResult = { content: TextContent[]; isError?: boolean };

export function textResult(text: string): ToolResult {
  return { content: [{ type: "text", text }] };
}

export function errorResult(error: string): ToolResult {
  return {
    content: [{ type: "text", text: `Error: ${error}` }],
    isError: true,
  };
}
