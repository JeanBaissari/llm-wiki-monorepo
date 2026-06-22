// MCP Server — Lint Bridge
// Bridges to lint_wiki.py (Python), with a TypeScript fallback for basic checks.

import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import type { LintIssue } from "./types.js";
import { fileExists, findMdFiles } from "./wiki-fs.js";

const execFileAsync = promisify(execFile);

// Monorepo root is the parent of the mcp-server/ directory
const MONOREPO_ROOT = path.resolve(process.cwd(), "..");

/** Full path to lint_wiki.py */
function lintScriptPath(): string {
  return path.resolve(
    MONOREPO_ROOT,
    "skill",
    "scripts",
    "lint_wiki.py",
  );
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Run lint checks against a wiki directory.
 *
 * First tries to shell out to `lint_wiki.py` (Python). If the script is not
 * found, falls back to basic TypeScript structural checks (dead wikilinks,
 * orphan pages, missing index entries).
 *
 * @param wikiPath — Path to the wiki root (containing wiki/, log/, audit/…)
 */
export async function runLint(
  wikiPath: string,
): Promise<{ issues: LintIssue[]; exitCode: number }> {
  const scriptPath = lintScriptPath();
  const hasPythonScript = await fileExists(scriptPath);

  if (!hasPythonScript) {
    return runBasicLint(wikiPath);
  }

  try {
    const { stdout } = await execFileAsync("python3", [scriptPath, wikiPath], {
      maxBuffer: 10 * 1024 * 1024,
    });
    return { issues: parseLintOutput(stdout), exitCode: 0 };
  } catch (err: unknown) {
    // Non-zero exit code — the error object carries stdout/stderr
    const execErr = err as NodeJS.ErrnoException & {
      stdout?: string;
      stderr?: string;
    };
    const stdout = execErr.stdout ?? "";
    const exitCode = execErr.code ?? (typeof (err as any).code === "number" ? (err as any).code : 1);
    return { issues: parseLintOutput(stdout), exitCode };
  }
}

// ---------------------------------------------------------------------------
// Parsing lint_wiki.py human-readable output
// ---------------------------------------------------------------------------

/**
 * Each section in the output has the form:
 *
 *   <emoji> <Category name> (N):
 *      <detail line>
 *      <detail line>
 *
 * We map known section headers to LintIssue types.
 */
interface SectionMatcher {
  pattern: RegExp;
  type: string;
  severity: string;
  /** If true, detail lines contain something like "file → [[target]]" */
  hasArrow: boolean;
}

const SECTION_MATCHERS: SectionMatcher[] = [
  { pattern: /^🔴\s*Dead wikilinks/i, type: "dead-wikilink", severity: "error", hasArrow: true },
  { pattern: /^🟡\s*Orphan pages/i, type: "orphan-page", severity: "warn", hasArrow: false },
  { pattern: /^🟡\s*Pages missing from index/i, type: "missing-index-entry", severity: "warn", hasArrow: false },
  { pattern: /^🟡\s*Frequently linked but no page/i, type: "unlinked-concept", severity: "warn", hasArrow: false },
  { pattern: /^🟡\s*log\/ shape/i, type: "log-shape", severity: "error", hasArrow: false },
  { pattern: /^🔴\s*audit\/ shape/i, type: "audit-shape", severity: "error", hasArrow: false },
  { pattern: /^🔴\s*Open audits with missing target/i, type: "missing-audit-target", severity: "error", hasArrow: true },
  { pattern: /^🟡\s*Frontmatter validation/i, type: "frontmatter", severity: "warn", hasArrow: false },
  { pattern: /^🟡\s*Stale pages/i, type: "stale-page", severity: "info", hasArrow: false },
  { pattern: /^🟡\s*Low.medium.confidence/i, type: "confidence", severity: "info", hasArrow: false },
  { pattern: /^🟡\s*Pages with contradiction/i, type: "contradiction", severity: "warn", hasArrow: false },
  { pattern: /^🟡\s*Large pages/i, type: "page-size", severity: "info", hasArrow: false },
  { pattern: /^🟡\s*Log rotation/i, type: "log-rotation", severity: "warn", hasArrow: false },
  { pattern: /^🔴\s*Source drift/i, type: "source-drift", severity: "error", hasArrow: false },
];

/** Parse human-readable lint output into structured LintIssue[] */
export function parseLintOutput(output: string): LintIssue[] {
  const issues: LintIssue[] = [];
  const lines = output.split("\n");

  let currentSection: SectionMatcher | null = null;
  let currentCount = 0; // expected from header

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();

    // Check if this line starts a new section
    let matched: SectionMatcher | null = null;
    for (const sm of SECTION_MATCHERS) {
      if (sm.pattern.test(line)) {
        matched = sm;
        break;
      }
    }

    if (matched) {
      currentSection = matched;
      // Extract count from parentheses: "🔴 Dead wikilinks (3):"
      const countMatch = line.match(/\((\d+)\)/);
      currentCount = countMatch ? parseInt(countMatch[1], 10) : 0;
      continue;
    }

    // Skip status/empty lines when not in a section
    if (!currentSection) continue;

    // Skip summary separator and summary line
    if (line.startsWith("─") || line.startsWith("✅") || line.startsWith("⚠️") || line.startsWith("✅") || line.startsWith("❌")) {
      // End of section — ✅/⚠️ lines indicate no issues for that category
      // We don't emit issues for clean sections
      // But some lines like "✅ No dead wikilinks" are standalone status lines
      // Check if this is a summary/status line outside a section
      if (line.startsWith("─") || line.startsWith("✅ Wiki is healthy") || line.startsWith("⚠️")) {
        currentSection = null;
      }
      continue;
    }

    // Detail lines are indented with 3 spaces
    if (!line.startsWith("   ")) {
      // Not a detail line — could be another section we missed, skip
      continue;
    }

    // Parse the detail line
    const detail = line.trim();

    // Build the LintIssue
    const issue: LintIssue = {
      type: currentSection.type,
      severity: currentSection.severity,
      page: "",
      detail,
    };

    if (currentSection.hasArrow && detail.includes("→")) {
      // Format: "source/file.md → [[Target]]"
      const arrowIdx = detail.indexOf("→");
      issue.page = detail.slice(0, arrowIdx).trim();
    } else {
      // Format is the page path itself
      issue.page = detail;
    }

    issues.push(issue);
  }

  return issues;
}

// ---------------------------------------------------------------------------
// TypeScript fallback — basic structural checks
// ---------------------------------------------------------------------------

const WIKILINK_RE = /\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]/g;

/**
 * Fallback lint when lint_wiki.py is not available.
 * Checks: dead wikilinks, orphan pages, missing index entries.
 */
async function runBasicLint(
  wikiPath: string,
): Promise<{ issues: LintIssue[]; exitCode: number }> {
  const issues: LintIssue[] = [];
  const wikiDir = path.join(wikiPath, "wiki");

  // Find all .md files under wiki/
  let mdFiles: string[];
  try {
    mdFiles = await findMdFiles(wikiDir);
  } catch {
    // If wiki/ doesn't exist, try wikiPath directly
    try {
      mdFiles = await findMdFiles(wikiPath);
    } catch {
      return { issues: [{ type: "error", severity: "error", page: "", detail: `Cannot read directory: ${wikiPath}` }], exitCode: 1 };
    }
  }

  if (mdFiles.length === 0) {
    return { issues: [], exitCode: 0 };
  }

  // Build page stem lookup (basename without .md, case-insensitive)
  const pageStems = new Set<string>();
  const pagePathByStem = new Map<string, string>();
  for (const f of mdFiles) {
    const stem = path.basename(f, ".md");
    pageStems.add(stem.toLowerCase());
    pagePathByStem.set(stem.toLowerCase(), f);
  }

  // ── Pass 1: dead wikilinks ────────────────────────────────
  const inbound = new Map<string, string[]>(); // stem → sources
  const deadLinks: Array<{ source: string; link: string }> = [];

  for (const filePath of mdFiles) {
    const content = await readFile(filePath, "utf-8");
    const relPath = path.relative(wikiPath, filePath);
    WIKILINK_RE.lastIndex = 0;

    let match: RegExpExecArray | null;
    while ((match = WIKILINK_RE.exec(content)) !== null) {
      const target = match[1]!.trim();
      if (!target) continue;
      const targetStem = target.toLowerCase();

      if (!pageStems.has(targetStem)) {
        deadLinks.push({ source: relPath, link: target });
      } else {
        const sourceStem = path.basename(filePath, ".md").toLowerCase();
        if (!inbound.has(targetStem)) inbound.set(targetStem, []);
        inbound.get(targetStem)!.push(sourceStem);
      }
    }
  }

  for (const dl of deadLinks) {
    issues.push({
      type: "dead-wikilink",
      severity: "error",
      page: dl.source,
      detail: `${dl.source} → [[${dl.link}]]`,
    });
  }

  // ── Pass 2: orphan pages (no inbound links) ───────────────
  const skipOrphan = new Set(["index"]);
  for (const filePath of mdFiles) {
    const stem = path.basename(filePath, ".md").toLowerCase();
    if (skipOrphan.has(stem)) continue;
    if (!inbound.has(stem) || inbound.get(stem)!.length === 0) {
      const relPath = path.relative(wikiPath, filePath);
      issues.push({
        type: "orphan-page",
        severity: "warn",
        page: relPath,
        detail: relPath,
      });
    }
  }

  // ── Pass 3: missing index entries ─────────────────────────
  const indexPath = path.join(wikiDir, "index.md");
  let indexText = "";
  try {
    indexText = await readFile(indexPath, "utf-8");
  } catch {
    // No index.md — skip this check
  }

  if (indexText) {
    for (const filePath of mdFiles) {
      const relPath = path.relative(wikiPath, filePath);
      if (path.basename(filePath) === "index.md") continue;
      const stem = path.basename(filePath, ".md");
      if (
        !indexText.includes(`[[${stem}]]`) &&
        !indexText.includes(relPath.replace(/\.md$/, ""))
      ) {
        issues.push({
          type: "missing-index-entry",
          severity: "warn",
          page: relPath,
          detail: relPath,
        });
      }
    }
  }

  return { issues, exitCode: issues.length > 0 ? 1 : 0 };
}
