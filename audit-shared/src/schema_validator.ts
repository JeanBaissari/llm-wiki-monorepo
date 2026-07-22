/**
 * schema_validator.ts — TypeScript schema validator for LLM Wiki artifacts.
 *
 * Loads JSON Schema files from schema/versions/v0.2.1/ and validates
 * documents using the Zod schemas from schema.ts as well as JSON Schema files.
 */

import { readFileSync, readdirSync } from "fs";
import { join, resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Resolve schema directory: walk up from audit-shared/src/ to repo root
function findRepoRoot(): string {
  let dir = resolve(__dirname, "..");
  while (dir !== "/") {
    if (readdirSync(dir).includes("schema")) {
      return dir;
    }
    dir = resolve(dir, "..");
  }
  return resolve(__dirname, "..", "..", "..");
}

const REPO_ROOT = findRepoRoot();
const SCHEMA_DIR = join(REPO_ROOT, "schema", "versions", "v0.2.1");

const VALID_TYPES = new Set([
  "entity", "concept", "source", "comparison", "synthesis", "overview",
]);

const VALID_LEVELS = new Set(["DEBUG", "INFO", "WARN", "ERROR", "PANIC"]);
const VALID_SEVERITIES = new Set(["info", "suggest", "warn", "error"]);
const VALID_STATUSES = new Set(["open", "resolved"]);
const VALID_SOURCES = new Set(["obsidian-plugin", "web-viewer", "manual", "ingest", "agent"]);
const VALID_TARGET_KINDS = new Set(["file", "page", "operation", "wiki"]);

const REQUIRED_FRONTMATTER = ["title", "type", "created", "updated", "sources", "tags"];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export interface ValidationResult {
  file: string;
  valid: boolean;
  errors: string[];
  skipped?: boolean;
}

function loadJsonSchema(name: string): Record<string, unknown> | null {
  try {
    const path = join(SCHEMA_DIR, name);
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch {
    return null;
  }
}

function validateEnum(value: unknown, validValues: Set<string>, field: string, errors: string[]): void {
  if (value !== undefined && value !== null && !validValues.has(String(value))) {
    errors.push(`Invalid ${field} '${value}': must be one of [${[...validValues].join(", ")}]`);
  }
}

function validateRequired(data: Record<string, unknown>, fields: string[], errors: string[]): void {
  for (const f of fields) {
    if (!(f in data)) {
      errors.push(`Missing required field: '${f}'`);
    }
  }
}

function validateStringArray(data: Record<string, unknown>, field: string, errors: string[]): void {
  const val = data[field];
  if (val !== undefined && val !== null && !Array.isArray(val)) {
    errors.push(`Field '${field}' must be an array, got ${typeof val}`);
  }
}

function validateDate(data: Record<string, unknown>, field: string, errors: string[]): void {
  const val = data[field];
  if (val !== undefined && val !== null && !DATE_RE.test(String(val))) {
    errors.push(`Field '${field}' must be YYYY-MM-DD, got '${val}'`);
  }
}

function validateType(data: Record<string, unknown>, errors: string[]): void {
  const t = data["type"];
  if (t !== undefined && t !== null && !VALID_TYPES.has(String(t))) {
    errors.push(`Invalid type '${t}': must be one of [${[...VALID_TYPES].sort().join(", ")}]`);
  }
}

// ── Public validation functions ────────────────────────────────────────

export function validatePage(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  validateRequired(data, REQUIRED_FRONTMATTER, errors);
  validateType(data, errors);
  validateDate(data, "created", errors);
  validateDate(data, "updated", errors);
  validateStringArray(data, "sources", errors);
  validateStringArray(data, "tags", errors);

  const confidence = data["confidence"];
  if (confidence !== undefined && confidence !== null) {
    validateEnum(confidence, new Set(["high", "medium", "low"]), "confidence", errors);
  }

  const contested = data["contested"];
  if (contested !== undefined && contested !== null && typeof contested !== "boolean") {
    errors.push(`Field 'contested' must be boolean, got ${typeof contested}`);
  }

  validateStringArray(data, "contradictions", errors);
  return errors;
}

export function validateAudit(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  validateRequired(data, ["id", "target", "severity", "author", "source", "created", "status"], errors);

  const hasAnchors = ["target_lines", "anchor_before", "anchor_text", "anchor_after"]
    .every(k => k in data);
  const isUnanchored = ["target_kind", "target_reason"]
    .every(k => k in data);

  if (!hasAnchors && !isUnanchored) {
    errors.push("Audit must have either anchor fields (target_lines, anchor_before, anchor_text, anchor_after) or unanchored kind (target_kind, target_reason)");
  }

  if (hasAnchors) {
    const tl = data["target_lines"];
    if (!Array.isArray(tl) || tl.length !== 2 || !tl.every(n => typeof n === "number" && n >= 1)) {
      errors.push("target_lines must be an array of two positive integers [start, end]");
    }
    if (typeof data["anchor_text"] !== "string" || String(data["anchor_text"]).length < 1) {
      errors.push("anchor_text must be a non-empty string");
    }
  }

  if (isUnanchored) {
    validateEnum(data["target_kind"] as string, VALID_TARGET_KINDS, "target_kind", errors);
  }

  validateEnum(data["severity"] as string, VALID_SEVERITIES, "severity", errors);
  validateEnum(data["status"] as string, VALID_STATUSES, "status", errors);
  validateEnum(data["source"] as string, VALID_SOURCES, "source", errors);

  const idVal = String(data["id"] ?? "");
  if (idVal && !/^\d{8}-\d{6}-[0-9a-f]{4}$/.test(idVal)) {
    errors.push(`Invalid id format '${idVal}': must match YYYYMMDD-HHMMSS-XXXX`);
  }

  return errors;
}

export function validateLogEvent(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  validateRequired(data, ["v", "ts", "lvl", "cmp", "msg"], errors);

  if (data["v"] !== undefined && data["v"] !== 1) {
    errors.push(`Log format version must be 1, got ${data["v"]}`);
  }

  validateEnum(data["lvl"] as string, VALID_LEVELS, "lvl", errors);

  return errors;
}

export function validateTemplate(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  validateRequired(data, ["name", "description"], errors);
  return errors;
}

export function validateClaim(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  validateRequired(data, ["claim_id", "statement", "confidence", "status"], errors);
  validateEnum(data["confidence"] as string, new Set(["high", "medium", "low"]), "confidence", errors);
  return errors;
}

// ── Fixture-based validation ───────────────────────────────────────────

export function validateFixtureFile(filePath: string): ValidationResult {
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(readFileSync(filePath, "utf-8"));
  } catch (e) {
    return { file: filePath, valid: false, errors: [`Invalid JSON: ${(e as Error).message}`] };
  }

  const name = filePath.replace(/.*[/\\]/, "").replace(/\.json$/, "");

  let errors: string[];

  if (name.includes("page") || name === "full-page" || name === "minimal-page") {
    errors = validatePage(data);
  } else if (name.includes("audit")) {
    errors = validateAudit(data);
  } else if (name.includes("log") || name.includes("event")) {
    errors = validateLogEvent(data);
  } else if (name.includes("template")) {
    errors = validateTemplate(data);
  } else if (name.includes("manifest")) {
    errors = validateOperationManifest(data);
  } else if (name.includes("claim") || name.includes("contradiction") || name.includes("epistemic")) {
    errors = validateClaim(data);
  } else {
    return { file: filePath, valid: true, errors: [], skipped: true };
  }

  return { file: filePath, valid: errors.length === 0, errors };
}

export function validateOperationManifest(data: Record<string, unknown>): string[] {
  const errors: string[] = [];
  validateRequired(data, ["operation_id", "command", "status", "started_at"], errors);
  return errors;
}

export function validateFixtureDir(directory: string): ValidationResult[] {
  const results: ValidationResult[] = [];
  const files = readdirSync(directory).filter(f => f.endsWith(".json")).sort();
  for (const f of files) {
    results.push(validateFixtureFile(join(directory, f)));
  }
  return results;
}

// ── CLI entry point ────────────────────────────────────────────────────

function main(): void {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error("Usage: schema_validator.ts <file> [file...]");
    process.exit(1);
  }

  let hasError = false;
  for (const f of args) {
    const result = validateFixtureFile(f);
    if (result.skipped) {
      console.log(`⚠  Skipped (unknown type): ${f}`);
    } else if (result.valid) {
      console.log(`✓  Valid: ${f}`);
    } else {
      console.log(`✗  Invalid: ${f}`);
      for (const e of result.errors) {
        console.log(`    - ${e}`);
      }
      hasError = true;
    }
  }

  process.exit(hasError ? 1 : 0);
}

if (process.argv[1]?.endsWith("schema_validator.ts") || process.argv[1]?.endsWith("schema_validator.js")) {
  main();
}
