#!/usr/bin/env python3
"""ingest.py (pipeline) — Two-Step Chain-of-Thought Ingest for LLM Wiki.

Usage: python3 ingest.py <wiki-root> <source-path> [--llm <provider>] [--force] [--batch <dir>]

Stage 1 (Analysis): LLM analyzes source → extracts entities, concepts,
claims, relationships, contradictions. Cached by SHA256.
Stage 2 (Generation): LLM takes analysis as context → produces FILE blocks
(wiki pages) and REVIEW blocks (issues).
"""
import argparse, hashlib, json, os, sys
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from llm_wiki.ingest.blocks import slugify, parse_blocks, ts, tiso
from llm_wiki.ingest.writer import write_wiki, write_review, update_index, append_log, read_file
from llm_wiki.core.layout import discover_layout
from llm_wiki.providers.registry import call_llm

CHUNK_SIZE = 55_000
STAGE1_SYSTEM = "You are analyzing a source document for a knowledge base. Extract key entities, concepts, claims, relationships, and contradictions. Be thorough and structured."
STAGE2_SYSTEM = "You are writing wiki pages for a knowledge base. Output ONLY structured blocks. Each page as ---FILE: path, each issue as ---REVIEW: type."

def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def read_response() -> Optional[str]:
    rf = os.environ.get("LLM_WIKI_RESPONSE_FILE")
    return read_file(rf) if rf else None

def read_orientation(wiki_root: str, layout=None) -> dict:
    if layout:
        path_map = {
            "CLAUDE.md": layout.schema_file or os.path.join(wiki_root, "CLAUDE.md"),
            "PURPOSE.md": layout.purpose_file or os.path.join(wiki_root, "PURPOSE.md"),
            "wiki/index.md": layout.index_file or os.path.join(wiki_root, "wiki", "index.md"),
        }
        return {k: read_file(v) or f"({k} not found)" for k, v in path_map.items()}
    return {f: read_file(os.path.join(wiki_root, f)) or f"({f} not found)"
            for f in ("CLAUDE.md", "PURPOSE.md", "wiki/index.md")}

def stage1_analyze(text: str, orient: dict, provider: str, slug: str,
                   llm_timeout: Optional[int] = None) -> Optional[str]:
    parts = [f"## Wiki Conventions (CLAUDE.md)\n{orient.get('CLAUDE.md','')}",
             f"## Wiki Scope (PURPOSE.md)\n{orient.get('PURPOSE.md','')}",
             f"## Current Wiki Index\n{orient.get('wiki/index.md','')}",
             f"## Source Document ({slug})\n{text}"]
    print(f"  Stage 1: Analyzing ({len(text)} chars)...", file=sys.stderr)
    result = call_llm(STAGE1_SYSTEM, "\n\n".join(parts), provider, total_timeout=llm_timeout)
    return result or read_response()

def stage1_consolidate(analyses: list, provider: str,
                       llm_timeout: Optional[int] = None) -> Optional[str]:
    if len(analyses) <= 1: return analyses[0] if analyses else None
    sys_p = "Consolidate these chunk analyses into one coherent analysis. Merge entities, concepts, claims, relationships. Remove duplicates."
    user = "## Chunk Analyses\n\n" + "\n\n---\n\n".join(f"### Chunk {i+1}\n{a}" for i,a in enumerate(analyses))
    return call_llm(sys_p, user, provider, total_timeout=llm_timeout) or read_response()

def stage2_generate(analysis: str, slug: str, src_path: str, orient: dict, provider: str,
                    llm_timeout: Optional[int] = None) -> Optional[str]:
    parts = [f"## Wiki Conventions (CLAUDE.md)\n{orient.get('CLAUDE.md','')}",
             f"## Wiki Scope (PURPOSE.md)\n{orient.get('PURPOSE.md','')}",
             f"## Current Wiki Index\n{orient.get('wiki/index.md','')}",
             f"## Source: {src_path}\nSource slug: {slug}",
             "\n---\n## Stage 1 Analysis (context only — do not echo)\n" + analysis,
             "\n---\n## Instructions\nProduce structured blocks:\n---FILE: wiki/entities/name.md\n---\ntitle: Entity Name\ntype: entity\n"
             f"created: {tiso()}\nupdated: {tiso()}\nsources: [{slug}]\ntags: [tag1, tag2]\n---\n\n# Entity Name\n\n<content>\n\n"
             "---REVIEW: missing-page\ntarget: wiki/entities/name.md\ntitle: Missing Entity\ndescription: ...\n\n"
             "Valid REVIEW types: missing-page, duplicate-page, contradiction, suggestion\n"
             "Output ONLY structured blocks. No commentary."]
    print(f"  Stage 2: Generating pages...", file=sys.stderr)
    return call_llm(STAGE2_SYSTEM, "\n\n".join(parts), provider, total_timeout=llm_timeout) or read_response()

def ingest(wiki_root: str, source_path: str, provider: str = "default", force: bool = False,
           llm_timeout: Optional[int] = None) -> int:
    """Ingest a source document into the wiki.

    Args:
        wiki_root: Path to the wiki root directory.
        source_path: Path to the source document.
        provider: LLM provider name.
        force: Skip cache and force re-ingest.
        llm_timeout: Total LLM call deadline in seconds (spans retries).
                     Default: None (no limit).

    Returns:
        0 on success, 1 on failure.
    """
    layout = discover_layout(wiki_root)
    if not os.path.isdir(wiki_root): print(f"ERROR: wiki root not found: {wiki_root}", file=sys.stderr); return 1
    source_text = read_file(source_path)
    if source_text is None: print(f"ERROR: source file not found: {source_path}", file=sys.stderr); return 1
    slug, s_hash = slugify(source_path), sha256_of(source_text)
    print(f"Ingesting: {source_path}  SHA256: {s_hash[:16]}... ({len(source_text)} chars)", file=sys.stderr)
    orient = read_orientation(wiki_root, layout)
    raw_base = layout.raw_dir or os.path.join(wiki_root, "raw")
    cache_dir = os.path.join(raw_base, ".cache"); os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{s_hash}.json")

    analysis = None
    if not force and os.path.exists(cache_path):
        try:
            with open(cache_path) as f: analysis = json.load(f).get("analysis")
            if analysis: print(f"  Using cached analysis", file=sys.stderr)
        except (json.JSONDecodeError, IOError): pass

    if analysis is None:
        if len(source_text) > CHUNK_SIZE:
            print(f"  Long source ({len(source_text)} chars). Chunking...", file=sys.stderr)
            overlap = 2000
            chunks = [source_text[i:min(i+CHUNK_SIZE, len(source_text))]
                      for i in range(0, len(source_text), CHUNK_SIZE - overlap)]
            analyses = []
            for i, c in enumerate(chunks):
                print(f"  Chunk {i+1}/{len(chunks)}...", file=sys.stderr)
                r = stage1_analyze(c, orient, provider, f"{slug}-chunk{i+1}", llm_timeout=llm_timeout)
                if r: analyses.append(r)
            analysis = stage1_consolidate(analyses, provider, llm_timeout=llm_timeout) if analyses else None
        else:
            analysis = stage1_analyze(source_text, orient, provider, slug, llm_timeout=llm_timeout)
        if analysis:
            from llm_wiki.core.atomic import atomic_write
            try:
                atomic_write(cache_path, json.dumps({"source_hash": s_hash, "source_slug": slug, "analysis": analysis, "timestamp": ts()}))
                print(f"  Cached analysis", file=sys.stderr)
            except IOError as e: print(f"  \u26a0  Cache write failed: {e}", file=sys.stderr)

    if not analysis:
        print("ERROR: No analysis. Set LLM_WIKI_RESPONSE_FILE with LLM output.", file=sys.stderr); return 1
    print(f"  Analysis: {len(analysis)} chars", file=sys.stderr)

    result = stage2_generate(analysis, slug, source_path, orient, provider, llm_timeout=llm_timeout)
    if not result:
        print("ERROR: No generation result. Set LLM_WIKI_RESPONSE_FILE.", file=sys.stderr); return 1
    print(f"  Generation: {len(result)} chars", file=sys.stderr)

    files, reviews = parse_blocks(result)
    print(f"  Parsed: {len(files)} FILE blocks, {len(reviews)} REVIEW blocks", file=sys.stderr)
    pages_created = pages_updated = 0; new_pages = []
    for p, c in files:
        status, ok = write_wiki(wiki_root, p, c, layout.pages_dir)
        if ok:
            if status == "created": pages_created += 1; new_pages.append(p); print(f"  \u2713 Created: {p}", file=sys.stderr)
            elif status == "updated": pages_updated += 1; print(f"  \u2713 Updated: {p}", file=sys.stderr)

    reviews_written = 0
    for rt, body in reviews:
        fn = write_review(wiki_root, rt, body, slug, layout.audit_dir)
        if fn: reviews_written += 1; print(f"  \u2713 Review: audit/{fn}", file=sys.stderr)

    if new_pages:
        a = update_index(wiki_root, new_pages, layout)
        if a: print(f"  \u2713 Added {a} entries to wiki/index.md", file=sys.stderr)
    append_log(wiki_root, slug, pages_created, pages_updated, reviews_written, layout.log_dir)
    print(f"\n\u2705 Ingest complete: {slug}\n   Created: {pages_created}  Updated: {pages_updated}  Reviews: {reviews_written}", file=sys.stderr)
    return 0

def main() -> int:
    p = argparse.ArgumentParser(description="Two-Step Chain-of-Thought Ingest for LLM Wiki", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("wiki_root"); p.add_argument("source_path")
    p.add_argument("--llm", dest="provider", default="default", help="LLM provider")
    p.add_argument("--force", action="store_true", help="Skip cache, force overwrite")
    p.add_argument("--batch", metavar="DIR", help="Batch process all sources in DIR")
    p.add_argument("--llm-timeout", type=int, default=None,
                   help="Total LLM call deadline in seconds (spans retries; budget/cost control)")
    args = p.parse_args()
    llm_timeout = args.llm_timeout

    from llm_wiki.operation import OperationContext

    if args.batch:
        if not os.path.isdir(args.batch): print(f"ERROR: batch dir not found: {args.batch}", file=sys.stderr); return 1
        files = sorted(os.path.join(args.batch, f) for f in os.listdir(args.batch)
                       if f.endswith((".md",".txt",".json",".yaml",".yml")) and not f.startswith("."))
        if not files: print(f"No source files in {args.batch}", file=sys.stderr); return 1
        print(f"Batch: {len(files)} files", file=sys.stderr)
        for f in files:
            print(f"\n{'='*60}", file=sys.stderr)
            with OperationContext("ingest", wiki_root=args.wiki_root,
                                   inputs={"source": f, "provider": args.provider, "batch": True}) as ctx:
                ec = ingest(args.wiki_root, f, args.provider, args.force, llm_timeout=llm_timeout)
                if ec != 0:
                    ctx.fail()
                else:
                    ctx.succeed()
        return ec

    with OperationContext("ingest", wiki_root=args.wiki_root,
                           inputs={"source": args.source_path, "provider": args.provider}) as ctx:
        ec = ingest(args.wiki_root, args.source_path, args.provider, args.force, llm_timeout=llm_timeout)
        if ec != 0:
            ctx.fail()
        else:
            ctx.succeed()
    return ec

if __name__ == "__main__": sys.exit(main())

def ingest_source(wiki_root: str, source_path: str, provider: str = "default",
                  force: bool = False, llm_timeout: Optional[int] = None,
                  **options) -> dict:
    """Structured ingest wrapper that returns a dict result.

    This is a convenience wrapper around ingest() for programmatic use.
    Returns a dict with success, error, pages_created, pages_updated, reviews_written.
    """
    ec = ingest(wiki_root, source_path, provider, force, llm_timeout=llm_timeout)
    if ec == 0:
        return {"success": True, "pages_created": 0, "pages_updated": 0,
                "reviews_written": 0, "error": None}
    return {"success": False, "pages_created": 0, "pages_updated": 0,
            "reviews_written": 0, "error": "ingest failed"}
