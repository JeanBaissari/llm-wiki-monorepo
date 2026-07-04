/**
 * mcp-server/test/test_wiki_fs.ts — Filesystem Adapter Tests
 *
 * Covers:
 *   - readFile: reads file content
 *   - writeFile: creates file with parent directories
 *   - fileExists: detects existing/non-existing files
 *   - ensureDir: creates directory, idempotent on existing
 *   - findMdFiles: finds .md files recursively
 *   - normalizePath: resolves relative paths
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs/promises';
import * as path from 'node:path';
import * as os from 'node:os';
import { readFile, writeFile, fileExists, ensureDir, findMdFiles, normalizePath, } from '../src/wiki-fs.js';
// ── Temp dir helpers ─────────────────────────────────────────────────────
let tmpDir;
beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wiki-fs-test-'));
});
afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
});
// ══════════════════════════════════════════════════════════════════════════
describe('wiki-fs — readFile', () => {
    it('reads file content', async () => {
        const filePath = path.join(tmpDir, 'test.md');
        await fs.writeFile(filePath, '# Hello World', 'utf-8');
        const content = await readFile(filePath);
        expect(content).toBe('# Hello World');
    });
    it('throws on non-existent file', async () => {
        await expect(readFile(path.join(tmpDir, 'nope.md'))).rejects.toThrow();
    });
});
describe('wiki-fs — writeFile', () => {
    it('creates file in nested directory', async () => {
        const filePath = path.join(tmpDir, 'a', 'b', 'c.md');
        await writeFile(filePath, 'nested content');
        const content = await fs.readFile(filePath, 'utf-8');
        expect(content).toBe('nested content');
    });
    it('overwrites existing file', async () => {
        const filePath = path.join(tmpDir, 'existing.md');
        await writeFile(filePath, 'first write');
        await writeFile(filePath, 'second write');
        const content = await fs.readFile(filePath, 'utf-8');
        expect(content).toBe('second write');
    });
});
describe('wiki-fs — fileExists', () => {
    it('returns true for existing file', async () => {
        const filePath = path.join(tmpDir, 'exists.md');
        await fs.writeFile(filePath, '');
        expect(await fileExists(filePath)).toBe(true);
    });
    it('returns false for non-existent file', async () => {
        expect(await fileExists(path.join(tmpDir, 'nope.md'))).toBe(false);
    });
});
describe('wiki-fs — ensureDir', () => {
    it('creates a new directory', async () => {
        const dirPath = path.join(tmpDir, 'newdir');
        await ensureDir(dirPath);
        const stat = await fs.stat(dirPath);
        expect(stat.isDirectory()).toBe(true);
    });
    it('is idempotent on existing directory', async () => {
        const dirPath = path.join(tmpDir, 'adir');
        await ensureDir(dirPath);
        await ensureDir(dirPath); // Should not throw
        const stat = await fs.stat(dirPath);
        expect(stat.isDirectory()).toBe(true);
    });
});
describe('wiki-fs — findMdFiles', () => {
    it('finds .md files recursively', async () => {
        const wikiDir = path.join(tmpDir, 'wiki');
        await fs.mkdir(path.join(wikiDir, 'entities'), { recursive: true });
        await fs.mkdir(path.join(wikiDir, 'concepts'), { recursive: true });
        await fs.writeFile(path.join(wikiDir, 'index.md'), '');
        await fs.writeFile(path.join(wikiDir, 'entities', 'python.md'), '');
        await fs.writeFile(path.join(wikiDir, 'concepts', 'ml.md'), '');
        // Non-.md file should be excluded
        await fs.writeFile(path.join(wikiDir, 'notes.txt'), '');
        const files = await findMdFiles(wikiDir);
        expect(files).toHaveLength(3);
        expect(files).toContain(path.join(wikiDir, 'index.md'));
        expect(files).toContain(path.join(wikiDir, 'entities', 'python.md'));
        expect(files).toContain(path.join(wikiDir, 'concepts', 'ml.md'));
    });
    it('returns empty array for non-existent directory', async () => {
        const files = await findMdFiles(path.join(tmpDir, 'nope'));
        expect(files).toHaveLength(0);
    });
    it('skips hidden directories', async () => {
        const wikiDir = path.join(tmpDir, 'wiki');
        await fs.mkdir(path.join(wikiDir, '.hidden'), { recursive: true });
        await fs.writeFile(path.join(wikiDir, '.hidden', 'secret.md'), '');
        await fs.writeFile(path.join(wikiDir, 'visible.md'), '');
        const files = await findMdFiles(wikiDir);
        expect(files).toHaveLength(1);
        expect(files[0]).toBe(path.join(wikiDir, 'visible.md'));
    });
});
describe('wiki-fs — normalizePath', () => {
    it('resolves relative paths', () => {
        const result = normalizePath('./foo/bar');
        expect(path.isAbsolute(result)).toBe(true);
    });
    it('strips trailing slashes', () => {
        const result = normalizePath('/foo/bar/');
        expect(result).not.toMatch(/\/$/);
    });
});
