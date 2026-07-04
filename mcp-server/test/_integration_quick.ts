/**
 * Quick integration test: build index with Python, search with TypeScript.
 */
import * as path from "node:path";
import * as fsSync from "node:fs";
import * as os from "node:os";
import { execFileSync } from "node:child_process";
import { search, buildIndex, clearIndex } from "../dist/search.js";

const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..");

async function main() {
  // Use the populated test fixture
  const wikiRoot = path.join(REPO_ROOT, "tests", "fixtures", "wikis", "populated");

  // Build the index via Python
  console.log("Building index...");
  const scriptPath = path.join(REPO_ROOT, "skill", "scripts", "index_wiki.py");
  const output = execFileSync("python3", [scriptPath, wikiRoot, "--json"], {
    encoding: "utf-8",
  });
  console.log("Index build output:", JSON.parse(output));

  // Search
  console.log("\n=== Search: 'deep learning' ===");
  const results = await search(wikiRoot, "deep learning", 5);
  for (const r of results) {
    console.log(`  ${r.title} (score: ${r.score.toFixed(4)}) — ${r.path}`);
    console.log(`    snippet: ${r.snippet?.slice(0, 80)}...`);
  }

  console.log("\n=== Search: 'python' ===");
  const results2 = await search(wikiRoot, "python", 3);
  for (const r of results2) {
    console.log(`  ${r.title} (score: ${r.score.toFixed(4)})`);
  }

  console.log("\n=== Search: nonexitent_term_xyz ===");
  const results3 = await search(wikiRoot, "nonexistent_term_xyz", 3);
  console.log(`  Results: ${results3.length}`);

  clearIndex();
  console.log("\nDone!");
}

main().catch(console.error);
