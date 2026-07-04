import { describe, it, expect } from 'vitest';
import { buildWikiGraph } from '../dist/build.js';

describe('import test', () => {
  it('can import from dist', async () => {
    // Just verify the import works
    expect(typeof buildWikiGraph).toBe('function');
  });
});
