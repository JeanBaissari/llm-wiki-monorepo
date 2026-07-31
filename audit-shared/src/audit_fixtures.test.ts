import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { AuditEntrySchema } from "./schema.js";
import { fromMarkdown } from "./serialize.js";

const FIXTURES_DIR = join(import.meta.dirname, "..", "..", "tests", "fixtures", "audit_entries");

describe("Audit Entry Fixtures", () => {
  it("valid_anchored parses and validates", () => {
    const content = readFileSync(join(FIXTURES_DIR, "valid_anchored.md"), "utf-8");
    const entry = fromMarkdown(content);
    expect(entry).toBeDefined();
    expect(entry.target).toBe("wiki/concepts/example.md");
    expect(entry.severity).toBe("suggest");
    expect(entry.target_lines).toEqual([10, 15]);
    const result = AuditEntrySchema.safeParse(entry);
    expect(result.success).toBe(true);
  });

  it("unanchored_review parses with target_kind", () => {
    const content = readFileSync(join(FIXTURES_DIR, "unanchored_review.md"), "utf-8");
    const entry = fromMarkdown(content);
    expect(entry).toBeDefined();
    expect(entry.target_kind).toBe("operation");
    expect(entry.target_lines).toBeUndefined();
    const result = AuditEntrySchema.safeParse(entry);
    expect(result.success).toBe(true);
  });

  it("duplicate_anchor parses with context", () => {
    const content = readFileSync(join(FIXTURES_DIR, "duplicate_anchor.md"), "utf-8");
    const entry = fromMarkdown(content);
    expect(entry).toBeDefined();
    expect(entry.anchor_text).toContain("ambiguous");
    const result = AuditEntrySchema.safeParse(entry);
    expect(result.success).toBe(true);
  });

  it("invalid_range parses even with out-of-bounds lines", () => {
    const content = readFileSync(join(FIXTURES_DIR, "invalid_range.md"), "utf-8");
    const entry = fromMarkdown(content);
    expect(entry).toBeDefined();
    expect(entry.target_lines).toEqual([99999, 100000]);
    // It should STILL parse as valid schema (invalid lines are a content issue, not schema)
    const result = AuditEntrySchema.safeParse(entry);
    expect(result.success).toBe(true);
  });
});
