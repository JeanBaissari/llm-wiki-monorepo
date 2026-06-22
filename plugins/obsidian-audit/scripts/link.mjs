#!/usr/bin/env node
// Usage: npm run link -- "/path/to/your/vault"
//
// Symlinks this plugin folder into <vault>/.obsidian/plugins/llm-wiki-audit/
// so you can hot-reload it from Obsidian's Community Plugins pane.

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const vault = process.argv[2];
if (!vault) {
  console.error("Usage: npm run link -- \"/path/to/your/vault\"");
  process.exit(1);
}

const pluginDir = path.resolve(path.join(path.dirname(new URL(import.meta.url).pathname), ".."));
const targetDir = path.join(vault, ".obsidian", "plugins", "llm-wiki-audit");

fs.mkdirSync(path.dirname(targetDir), { recursive: true });

if (fs.existsSync(targetDir)) {
  const stat = fs.lstatSync(targetDir);
  if (stat.isSymbolicLink()) {
    fs.unlinkSync(targetDir);
  } else {
    console.error(`Refusing to overwrite non-symlink at ${targetDir}`);
    process.exit(1);
  }
}

fs.symlinkSync(pluginDir, targetDir, "dir");
console.log(`Linked ${pluginDir}\n      -> ${targetDir}`);
console.log("Now enable 'LLM Wiki Audit' in Obsidian → Settings → Community plugins.");
