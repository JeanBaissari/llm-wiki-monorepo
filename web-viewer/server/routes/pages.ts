import fs from "node:fs";
import path from "node:path";
import type { Request, Response } from "express";
import type { ServerConfig } from "../config.js";
import { createRenderer } from "../render/markdown.js";
import { resolveInsideRoot, safeRel } from "../paths.js";

export function handlePage(cfg: ServerConfig) {
  const renderer = createRenderer({ wikiRoot: cfg.wikiRoot });

  return (req: Request, res: Response) => {
    const relRaw = (req.query.path as string | undefined) ?? "";
    const rel = safeRel(relRaw);
    if (!rel) {
      res.status(400).json({ error: "missing or invalid `path` query" });
      return;
    }

    // Default to wiki/index.md if a directory is requested.
    let candidate = path.join(cfg.wikiRoot, rel);
    if (fs.existsSync(candidate) && fs.statSync(candidate).isDirectory()) {
      candidate = path.join(candidate, "index.md");
    }

    if (!candidate.endsWith(".md")) candidate += ".md";

    const full = resolveInsideRoot(cfg.wikiRoot, path.relative(cfg.wikiRoot, candidate));
    if (!full) {
      res.status(403).json({ error: "path escapes wiki root" });
      return;
    }

    if (!fs.existsSync(full) || !fs.statSync(full).isFile()) {
      res.status(404).json({ error: "file not found", path: rel });
      return;
    }

    const rawMarkdown = fs.readFileSync(full, "utf-8");
    const rendered = renderer.render(rawMarkdown);
    res.json({
      path: path.relative(cfg.wikiRoot, candidate).split(path.sep).join("/"),
      title: rendered.title,
      frontmatter: rendered.frontmatter,
      html: rendered.html,
      raw: rendered.rawMarkdown,
    });
  };
}

export function handleRaw(cfg: ServerConfig) {
  return (req: Request, res: Response) => {
    const relRaw = (req.query.path as string | undefined) ?? "";
    const rel = safeRel(relRaw);
    if (!rel) {
      res.status(400).send("bad path");
      return;
    }
    const full = resolveInsideRoot(cfg.wikiRoot, rel);
    if (!full) {
      res.status(403).send("path escapes wiki root");
      return;
    }
    if (!fs.existsSync(full) || !fs.statSync(full).isFile()) {
      res.status(404).send("not found");
      return;
    }
    res.type("text/markdown").send(fs.readFileSync(full));
  };
}
