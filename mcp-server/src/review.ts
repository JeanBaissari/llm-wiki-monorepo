// MCP Server — Bidirectional Review System
// Reviews stored as markdown files in audit/ with YAML frontmatter
// Uses simple regex-based YAML parser (no external dependencies)

import { readFile, writeFile, fileExists, ensureDir } from "./wiki-fs.js";
import type { ReviewItem } from "./types.js";
import * as path from "node:path";
import * as fs from "node:fs/promises";

// ─── Helpers ───────────────────────────────────────────────

/** Generate a review ID: YYYYMMDD-HHmmss-<4hex> (e.g. 20260622-093000-a1b2) */
function generateId(): string {
  const now = new Date();
  const pad = (n: number, w = 2) => String(n).padStart(w, "0");
  const ts =
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-` +
    `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  const random = Math.random().toString(16).slice(2, 6);
  return `${ts}-${random}`;
}

/** Filesystem-safe slug from a title */
function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "untitled";
}

/** Read all .md files in a single directory (non-recursive) */
async function readMdFilesInDir(dirPath: string): Promise<string[]> {
  const files: string[] = [];
  try {
    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isFile() && entry.name.endsWith(".md")) {
        files.push(path.join(dirPath, entry.name));
      }
    }
  } catch {
    // Directory doesn't exist yet
  }
  return files;
}

// ─── Simple YAML Frontmatter Parser ────────────────────────

/** Parse frontmatter from markdown content into a key-value map */
function parseFrontmatter(content: string): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return result;

  const yaml = match[1];
  const lines = yaml.split("\n");
  let currentKey: string | null = null;

  for (const line of lines) {
    // New key-value pair
    const kvMatch = line.match(/^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*?)\s*$/);
    if (kvMatch) {
      currentKey = kvMatch[1];
      let value: unknown = kvMatch[2].trim();

      if (typeof value === "string" && value !== "") {
        const strVal = value as string;
        // Quoted strings
        if (
          (strVal.startsWith('"') && strVal.endsWith('"')) ||
          (strVal.startsWith("'") && strVal.endsWith("'"))
        ) {
          value = strVal.slice(1, -1);
        } else if (strVal === "true") {
          value = true;
        } else if (strVal === "false") {
          value = false;
        } else if (/^\d{4}-\d{2}-\d{2}T/.test(strVal)) {
          value = strVal; // keep ISO string
        }
      }

      result[currentKey] = value;
      continue;
    }

    // Array item under current key (e.g. "  - \"value\"")
    if (currentKey) {
      const itemMatch = line.match(/^\s*-\s*["']?(.+?)["']?\s*$/);
      if (itemMatch) {
        const existing = result[currentKey];
        const arr = Array.isArray(existing) ? existing : [];
        arr.push(itemMatch[1].replace(/^["']|["']$/g, ""));
        result[currentKey] = arr;
      }
    }
  }

  return result;
}

/** Build YAML frontmatter string from an object */
function buildFrontmatter(data: Record<string, unknown>): string {
  const lines: string[] = ["---"];
  for (const [key, value] of Object.entries(data)) {
    if (value === null || value === undefined) continue;
    if (typeof value === "string") {
      // Quote strings that contain special characters
      if (/[:\n#"']/.test(value)) {
        lines.push(`${key}: "${value.replace(/"/g, '\\"')}"`);
      } else {
        lines.push(`${key}: ${value}`);
      }
    } else if (typeof value === "boolean" || typeof value === "number") {
      lines.push(`${key}: ${value}`);
    } else if (Array.isArray(value) && value.length > 0) {
      lines.push(`${key}:`);
      for (const item of value) {
        lines.push(`  - "${String(item)}"`);
      }
    }
  }
  lines.push("---");
  return lines.join("\n");
}

/** Extract the body text after frontmatter */
function extractBody(content: string): string {
  return content.replace(/^---\n[\s\S]*?\n---\n?/, "").trim();
}

/** Construct a ReviewItem from a file's content and its basename id */
function reviewFromFile(id: string, content: string): ReviewItem {
  const fm = parseFrontmatter(content);
  const body = extractBody(content);

  return {
    id: (fm.id as string) || id,
    target: (fm.target as string) || "",
    type: (fm.type as ReviewItem["type"]) || "suggestion",
    title: (fm.title as string) || "",
    description: body || (fm.description as string) || "",
    severity: (fm.severity as ReviewItem["severity"]) || "suggest",
    status: (fm.status as ReviewItem["status"]) || "open",
    author: (fm.author as string) || "unknown",
    created: (fm.created as string) || new Date().toISOString(),
    affectedPages: fm.affectedPages as string[] | undefined,
  };
}

// ─── Public API ────────────────────────────────────────────

/**
 * List all review items in the wiki's audit/ directory.
 * @param wikiPath Root path of the wiki
 * @param status  Filter: "open" (audit/), "resolved" (audit/resolved/), or "all" (both)
 */
export async function listReviews(
  wikiPath: string,
  status: "open" | "resolved" | "all" = "all",
): Promise<ReviewItem[]> {
  const auditDir = path.join(wikiPath, "audit");
  const resolvedDir = path.join(auditDir, "resolved");
  const items: ReviewItem[] = [];

  // Open reviews live in audit/*.md (top-level only)
  if (status === "open" || status === "all") {
    const files = await readMdFilesInDir(auditDir);
    for (const filePath of files) {
      try {
        const content = await readFile(filePath);
        const id = path.basename(filePath, ".md");
        const item = reviewFromFile(id, content);
        if (item.status === "open") {
          items.push(item);
        }
      } catch {
        // Skip unreadable files
      }
    }
  }

  // Resolved reviews live in audit/resolved/*.md
  if (status === "resolved" || status === "all") {
    const files = await readMdFilesInDir(resolvedDir);
    for (const filePath of files) {
      try {
        const content = await readFile(filePath);
        const id = path.basename(filePath, ".md");
        const item = reviewFromFile(id, content);
        if (item.status === "resolved") {
          items.push(item);
        }
      } catch {
        // Skip unreadable files
      }
    }
  }

  return items;
}

/**
 * Create a new review file in audit/.
 * Returns the fully formed ReviewItem with generated id and timestamp.
 */
export async function createReview(
  wikiPath: string,
  item: Omit<ReviewItem, "id" | "created">,
): Promise<ReviewItem> {
  const id = generateId();
  const created = new Date().toISOString();
  const slug = slugify(item.title || item.type);
  const filename = `${id}-${slug}.md`;

  const auditDir = path.join(wikiPath, "audit");
  await ensureDir(auditDir);

  const review: ReviewItem = {
    id,
    target: item.target,
    type: item.type,
    title: item.title,
    description: item.description,
    severity: item.severity,
    status: item.status || "open",
    author: item.author,
    created,
    affectedPages: item.affectedPages,
  };

  const fmData: Record<string, unknown> = {
    id: review.id,
    target: review.target,
    type: review.type,
    title: review.title,
    severity: review.severity,
    author: review.author,
    status: review.status,
    created: review.created,
  };
  if (review.affectedPages && review.affectedPages.length > 0) {
    fmData.affectedPages = review.affectedPages;
  }

  const frontmatter = buildFrontmatter(fmData);
  const content = `${frontmatter}\n\n${review.description}`;

  await writeFile(path.join(auditDir, filename), content);
  return review;
}

/**
 * Resolve a review: mark status as resolved, move file from audit/ to
 * audit/resolved/, and append a resolution note.
 */
export async function resolveReview(
  wikiPath: string,
  id: string,
  resolution: string,
): Promise<void> {
  const auditDir = path.join(wikiPath, "audit");
  const resolvedDir = path.join(auditDir, "resolved");
  await ensureDir(resolvedDir);

  // Find the source file by matching id prefix
  let sourceFile: string | null = null;
  const files = await readMdFilesInDir(auditDir);
  for (const filePath of files) {
    if (path.basename(filePath, ".md").startsWith(id)) {
      sourceFile = filePath;
      break;
    }
  }

  if (!sourceFile) {
    throw new Error(`Review with id "${id}" not found in audit/`);
  }

  const content = await readFile(sourceFile);

  // Update status in frontmatter
  const updatedContent = content.replace(
    /^status:\s*open/m,
    "status: resolved",
  );

  // Append resolution
  const now = new Date().toISOString();
  const finalContent = `${updatedContent}\n\n## Resolution\n\n${resolution}\n\n*Resolved at ${now}*`;

  // Write to resolved dir, remove original
  const destFile = path.join(resolvedDir, path.basename(sourceFile));
  await writeFile(destFile, finalContent);
  await fs.unlink(sourceFile);
}

/**
 * Get all open reviews that target a specific file.
 */
export async function getOpenReviewsForFile(
  wikiPath: string,
  targetFile: string,
): Promise<ReviewItem[]> {
  const all = await listReviews(wikiPath, "open");
  return all.filter((r) => r.target === targetFile);
}
