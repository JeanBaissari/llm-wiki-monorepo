// MCP Server — Lint Bridge
//
// Primary path: delegates to lint_wiki.py via the Python sidecar (LWM_07).
// Fallback: TypeScript structural checks when sidecar is unavailable.

import { readFile } from "node:fs/promises";
import path from "node:path";
import type { LintIssue } from "./types.js";
import { fileExists, findMdFiles } from "./wiki-fs.js";
import type { PythonSidecar } from "./sidecar.js";

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * Run lint checks against a wiki directory.
 *
 * Uses the Python sidecar for comprehensive 16-pass linting.
 * Falls back to basic TypeScript structural checks if the sidecar
 * is not provided or is unavailable.
 *
 * @param wikiPath  Path to the wiki root (containing wiki/, log/, audit/…)
 * @param sidecar   Optional PythonSidecar instance for zero-subprocess linting
 */
export async function runLint(
  wikiPath: string,
  sidecar?: PythonSidecar | null,
): Promise<{ issues: LintIssue[]; exitCode: number }> {
  // Try sidecar first (primary path, LWM_07)
  if (sidecar?.isRunning()) {
    try {
      const result = (await sidecar.call("lint_wiki", {
        paths: [],
        fix: false,
        check_broken_links: true,
      })) as {
        issues: { type: string; severity: string; page: string; detail: string }[];
        warnings: string[];
        passed: boolean;
      };

      if (result && Array.isArray(result.issues)) {
        const issues: LintIssue[] = result.issues.map((i) => ({
          type: i.type,
          severity: i.severity,
          page: i.page,
          detail: i.detail,
        }));
        return { issues, exitCode: result.passed ? 0 : 1 };
      }
    } catch (e) {
      // Sidecar call failed — fall through to basic lint
      console.error(`[lint] Sidecar lint failed, falling back to basic: ${e}`);
    }
  }

  // Fallback: basic TypeScript structural checks
  return runBasicLint(wikiPath);
}

// ── Parsing (for backward compat with old subprocess output) ────────────────

interface SectionMatcher {
  pattern: RegExp;
  type: string;
  severity: string;
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

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();

    let matched: SectionMatcher | null = null;
    for (const sm of SECTION_MATCHERS) {
      if (sm.pattern.test(line)) {
        matched = sm;
        break;
      }
    }

    if (matched) {
      currentSection = matched;
      continue;
    }

    if (!currentSection) continue;

    if (line.startsWith("─") || line.startsWith("✅") || line.startsWith("⚠️") || line.startsWith("❌")) {
      if (line.startsWith("─") || line.startsWith("✅ Wiki is healthy") || line.startsWith("⚠️")) {
        currentSection = null;
      }
      continue;
    }

    if (!line.startsWith("   ")) continue;

    const detail = line.trim();
    const issue: LintIssue = {
      type: currentSection.type,
      severity: currentSection.severity,
      page: "",
      detail,
    };

    if (currentSection.hasArrow && detail.includes("→")) {
      const arrowIdx = detail.indexOf("→");
      issue.page = detail.slice(0, arrowIdx).trim();
    } else {
      issue.page = detail;
    }

    issues.push(issue);
  }

  return issues;
}

// ── TypeScript fallback — basic structural checks ────────────────────────

const WIKILINK_RE = /\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]/g;

async function runBasicLint(
  wikiPath: string,
): Promise<{ issues: LintIssue[]; exitCode: number }> {
  const issues: LintIssue[] = [];
  const wikiDir = path.join(wikiPath, "wiki");

  let mdFiles: string[];
  try {
    mdFiles = await findMdFiles(wikiDir);
  } catch {
    try {
      mdFiles = await findMdFiles(wikiPath);
    } catch {
      return { issues: [{ type: "error", severity: "error", page: "", detail: `Cannot read directory: ${wikiPath}` }], exitCode: 1 };
    }
  }

  if (mdFiles.length === 0) {
    return { issues: [], exitCode: 0 };
  }

  const pageStems = new Set<string>();
  const pagePathByStem = new Map<string, string>();
  for (const f of mdFiles) {
    const stem = path.basename(f, ".md");
    pageStems.add(stem.toLowerCase());
    pagePathByStem.set(stem.toLowerCase(), f);
  }

  const inbound = new Map<string, string[]>();
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
    issues.push({ type: "dead-wikilink", severity: "error", page: dl.source, detail: `${dl.source} → [[${dl.link}]]` });
  }

  const skipOrphan = new Set(["index"]);
  for (const filePath of mdFiles) {
    const stem = path.basename(filePath, ".md").toLowerCase();
    if (skipOrphan.has(stem)) continue;
    if (!inbound.has(stem) || inbound.get(stem)!.length === 0) {
      const relPath = path.relative(wikiPath, filePath);
      issues.push({ type: "orphan-page", severity: "warn", page: relPath, detail: relPath });
    }
  }

  const indexPath = path.join(wikiDir, "index.md");
  let indexText = "";
  try { indexText = await readFile(indexPath, "utf-8"); } catch { /* no index.md */ }

  if (indexText) {
    for (const filePath of mdFiles) {
      const relPath = path.relative(wikiPath, filePath);
      if (path.basename(filePath) === "index.md") continue;
      const stem = path.basename(filePath, ".md");
      if (!indexText.includes(`[[${stem}]]`) && !indexText.includes(relPath.replace(/\.md$/, ""))) {
        issues.push({ type: "missing-index-entry", severity: "warn", page: relPath, detail: relPath });
      }
    }
  }

  return { issues, exitCode: issues.length > 0 ? 1 : 0 };
}
