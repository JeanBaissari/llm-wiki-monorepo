import { execSync } from "child_process";
import path from "path";

/**
 * WikiLayout — matches the Python discover.py WikiLayout dataclass.
 */
export interface WikiLayout {
  root: string;
  pages_dir: string;
  raw_dir: string | null;
  log_dir: string | null;
  audit_dir: string | null;
  outputs_dir: string | null;
  index_file: string | null;
  schema_file: string | null;
  purpose_file: string | null;
  page_type_dirs: string[];
  page_types: Record<string, string>;
  frontmatter_required: string[];
  frontmatter_optional: string[];
  date_format: string;
  skip_stems: string[];
  structural_types: string[];
  discovery_method: string;
  confidence: number;
}

/**
 * Resolve the monorepo root from the compiled dist/ directory.
 * mcp-server/dist/ → mcp-server/ → monorepo root
 */
function monorepoRoot(): string {
  return path.resolve(__dirname, "../..");
}

/**
 * Discover wiki structure by calling the Python discover.py module.
 * Falls back to a basic layout if Python is unavailable or discovery fails.
 */
export function discoverLayout(wikiPath: string): WikiLayout {
  const scriptPath = path.join(monorepoRoot(), "skill", "scripts", "discover.py");

  try {
    const output = execSync(
      `python3 "${scriptPath}" --json "${wikiPath}"`,
      { encoding: "utf-8", timeout: 15000, stdio: ["pipe", "pipe", "pipe"] }
    );

    // Parse the JSON output — skip any stderr trace lines that might leak
    const lines = output.trim().split("\n");
    const jsonLine = lines.find(l => l.startsWith("{"));
    if (!jsonLine) {
      return basicLayout(wikiPath);
    }

    return JSON.parse(jsonLine) as WikiLayout;
  } catch {
    return basicLayout(wikiPath);
  }
}

/**
 * Basic layout fallback when discover.py is unavailable.
 * Assumes the wiki follows the canonical scaffolded structure.
 */
function basicLayout(wikiPath: string): WikiLayout {
  const root = path.resolve(wikiPath);
  const wikiDir = path.join(root, "wiki");

  // Check if wiki/ subdirectory exists
  const { existsSync } = require("fs");
  const pagesDir = existsSync(wikiDir) ? wikiDir : root;
  const rawDir = path.join(root, "raw");
  const logDir = path.join(root, "log");
  const auditDir = path.join(root, "audit");

  return {
    root,
    pages_dir: pagesDir,
    raw_dir: existsSync(rawDir) ? rawDir : null,
    log_dir: existsSync(logDir) ? logDir : null,
    audit_dir: existsSync(auditDir) ? auditDir : null,
    outputs_dir: null,
    index_file: path.join(pagesDir, "index.md"),
    schema_file: path.join(root, "CLAUDE.md"),
    purpose_file: path.join(root, "PURPOSE.md"),
    page_type_dirs: ["concepts", "entities", "summaries", "comparisons", "graphs", "synthesis"],
    page_types: {
      concepts: "Concepts",
      entities: "Entities",
      summaries: "Summaries",
      comparisons: "Comparisons",
      graphs: "Graphs",
      synthesis: "Synthesis",
    },
    frontmatter_required: ["title", "type", "created"],
    frontmatter_optional: ["updated", "sources", "tags", "confidence"],
    date_format: "%Y-%m-%d",
    skip_stems: ["index", "log", "overview"],
    structural_types: ["index", "log", "overview"],
    discovery_method: "fallback",
    confidence: 0.5,
  };
}
