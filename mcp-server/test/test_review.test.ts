/**
 * mcp-server/test/test_review.ts — Review System Tests
 *
 * Covers:
 *   - createReview: creates a review file
 *   - listReviews: lists open, resolved, all
 *   - resolveReview: marks as resolved, moves to audit/resolved/
 *   - getOpenReviewsForFile: filters by target
 *   - Review file has valid frontmatter format
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'node:fs/promises';
import * as fsSync from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import {
  createReview,
  listReviews,
  resolveReview,
  getOpenReviewsForFile,
} from '../dist/review.js';
import type { ReviewItem } from '../dist/types.js';

let tmpDir: string;

beforeEach(() => {
  tmpDir = fsSync.mkdtempSync(path.join(os.tmpdir(), 'review-test-'));
});

afterEach(async () => {
  await fs.rm(tmpDir, { recursive: true, force: true });
});

// ── Helpers ──────────────────────────────────────────────────────────────

function makeReview(overrides: Partial<Omit<ReviewItem, 'id' | 'created'>> = {}): Omit<ReviewItem, 'id' | 'created'> {
  return {
    target: overrides.target ?? 'wiki/entities/test.md',
    type: overrides.type ?? 'suggestion',
    title: overrides.title ?? 'Test Review',
    description: overrides.description ?? 'Test description',
    severity: overrides.severity ?? 'suggest',
    status: overrides.status ?? 'open',
    author: overrides.author ?? 'test-runner',
    affectedPages: overrides.affectedPages,
  };
}

// ══════════════════════════════════════════════════════════════════════════
// createReview
// ══════════════════════════════════════════════════════════════════════════

describe('createReview', () => {
  it('creates a review file in audit/', async () => {
    const review = await createReview(tmpDir, makeReview({
      target: 'wiki/entities/my-page.md',
      title: 'Fix Typo',
      type: 'suggestion',
    }));

    expect(review.id).toBeTruthy();
    expect(review.status).toBe('open');
    expect(review.target).toBe('wiki/entities/my-page.md');

    // Verify file exists
    const auditDir = path.join(tmpDir, 'audit');
    const files = await fs.readdir(auditDir);
    const reviewFile = files.find(f => f.includes(review.id));
    expect(reviewFile).toBeTruthy();
  });

  it('generates unique IDs', async () => {
    const r1 = await createReview(tmpDir, makeReview({ title: 'Review 1' }));
    const r2 = await createReview(tmpDir, makeReview({ title: 'Review 2' }));
    expect(r1.id).not.toBe(r2.id);
  });

  it('review file contains valid frontmatter', async () => {
    await createReview(tmpDir, makeReview({ target: 'wiki/test.md' }));

    const auditDir = path.join(tmpDir, 'audit');
    const files = await fs.readdir(auditDir);
    const reviewFiles = files.filter(f => f.endsWith('.md') && f !== '.gitkeep');
    expect(reviewFiles.length).toBeGreaterThan(0);

    const content = await fs.readFile(path.join(auditDir, reviewFiles[0]), 'utf-8');
    expect(content).toMatch(/^---\n/); // starts with frontmatter
    expect(content).toContain('target:');
    expect(content).toContain('type:');
    expect(content).toContain('status:');
  });
});

// ══════════════════════════════════════════════════════════════════════════
// listReviews
// ══════════════════════════════════════════════════════════════════════════

describe('listReviews', () => {
  it('lists open reviews', async () => {
    await createReview(tmpDir, makeReview({ target: 'wiki/a.md', title: 'Open A' }));
    await createReview(tmpDir, makeReview({ target: 'wiki/b.md', title: 'Open B' }));

    const openReviews = await listReviews(tmpDir, 'open');
    expect(openReviews).toHaveLength(2);
  });

  it('returns empty for resolved when no resolved reviews', async () => {
    await createReview(tmpDir, makeReview({ target: 'wiki/a.md' }));

    const resolved = await listReviews(tmpDir, 'resolved');
    expect(resolved).toHaveLength(0);
  });

  it('lists all reviews', async () => {
    await createReview(tmpDir, makeReview({ target: 'wiki/a.md' }));

    const all = await listReviews(tmpDir, 'all');
    expect(all.length).toBeGreaterThanOrEqual(1);
  });

  it('resolved reviews appear in resolved list', async () => {
    const review = await createReview(tmpDir, makeReview({ target: 'wiki/a.md' }));
    await resolveReview(tmpDir, review.id, 'Fixed the issue.');

    const resolved = await listReviews(tmpDir, 'resolved');
    expect(resolved).toHaveLength(1);
    expect(resolved[0].id).toBe(review.id);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// resolveReview
// ══════════════════════════════════════════════════════════════════════════

describe('resolveReview', () => {
  it('moves review to audit/resolved/', async () => {
    const review = await createReview(tmpDir, makeReview({ target: 'wiki/page.md' }));
    await resolveReview(tmpDir, review.id, 'Fixed.');

    // Original file should be gone
    const auditDir = path.join(tmpDir, 'audit');
    const files = await fs.readdir(auditDir);
    const inOpen = files.filter(f => f.includes(review.id) && f.endsWith('.md'));
    expect(inOpen).toHaveLength(0);

    // Should be in resolved/
    const resolvedDir = path.join(tmpDir, 'audit', 'resolved');
    const resolvedFiles = await fs.readdir(resolvedDir);
    const inResolved = resolvedFiles.filter(f => f.includes(review.id));
    expect(inResolved.length).toBeGreaterThan(0);
  });

  it('throws for non-existent review ID', async () => {
    await expect(
      resolveReview(tmpDir, 'nonexistent-id', 'Fixed.')
    ).rejects.toThrow('not found');
  });
});

// ══════════════════════════════════════════════════════════════════════════
// getOpenReviewsForFile
// ══════════════════════════════════════════════════════════════════════════

describe('getOpenReviewsForFile', () => {
  it('returns only open reviews for target file', async () => {
    await createReview(tmpDir, makeReview({ target: 'wiki/target_a.md', title: 'Issue A' }));
    await createReview(tmpDir, makeReview({ target: 'wiki/target_a.md', title: 'Issue B' }));
    await createReview(tmpDir, makeReview({ target: 'wiki/target_b.md', title: 'Issue C' }));

    const forA = await getOpenReviewsForFile(tmpDir, 'wiki/target_a.md');
    expect(forA).toHaveLength(2);
    for (const r of forA) {
      expect(r.target).toBe('wiki/target_a.md');
    }
  });

  it('returns empty for file with no reviews', async () => {
    const results = await getOpenReviewsForFile(tmpDir, 'wiki/nonexistent.md');
    expect(results).toHaveLength(0);
  });
});
