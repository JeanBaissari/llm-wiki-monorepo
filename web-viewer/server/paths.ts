import fs from "node:fs";
import path from "node:path";

export function isInside(root: string, candidate: string): boolean {
  const rel = path.relative(root, candidate);
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

export function safeRel(input: string): string | null {
  if (!input) return "wiki/index.md";
  if (input.includes("\0")) return null;
  if (path.isAbsolute(input)) return null;
  const normalized = path.posix.normalize(input);
  if (normalized.startsWith("..")) return null;
  return normalized;
}

/**
 * Resolve `rel` under `root` and verify containment twice: lexically after
 * `path.resolve` (blocks `..` traversal) and again after `fs.realpathSync`
 * (blocks symlink escapes). Returns the real path, or null when the path
 * escapes the root — callers must fail closed. Non-existent paths are
 * returned so callers can answer with their own 404.
 */
export function resolveInsideRoot(root: string, rel: string): string | null {
  const realRoot = fs.realpathSync(root);
  const full = path.resolve(realRoot, rel);
  if (!isInside(realRoot, full)) return null;
  if (!fs.existsSync(full)) return full;
  const real = fs.realpathSync(full);
  if (!isInside(realRoot, real)) return null;
  return real;
}
