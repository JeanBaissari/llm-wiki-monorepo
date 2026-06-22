#!/usr/bin/env python3
"""ingest.py — Two-Step Chain-of-Thought Ingest for LLM Wiki.

Usage: python3 ingest.py <wiki-root> <source-path> [--llm <provider>] [--force] [--batch <dir>]

Stage 1 (Analysis): LLM analyzes source → extracts entities, concepts,
claims, relationships, contradictions. Cached by SHA256.
Stage 2 (Generation): LLM takes analysis as context → produces FILE blocks
(wiki pages) and REVIEW blocks (issues).
"""
import argparse, hashlib, json, os, re, sys, subprocess
from datetime import datetime, date
from pathlib import Path
from typing import Optional
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from discover import discover_layout

CHUNK_SIZE = 55_000
STAGE1_SYSTEM = "You are analyzing a source document for a knowledge base. Extract key entities, concepts, claims, relationships, and contradictions. Be thorough and structured."
STAGE2_SYSTEM = "You are writing wiki pages for a knowledge base. Output ONLY structured blocks. Each page as ---FILE: path, each issue as ---REVIEW: type."

def slugify(path: str) -> str:
    name = Path(path).stem
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name).lower().strip("_") or "source"

def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def read_file(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f: return f.read()
    except (FileNotFoundError, IOError): return None

def write_file(path: str, content: str) -> bool:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f: f.write(content)
        return True
    except IOError as e: print(f"  \u26a0  Error writing {path}: {e}", file=sys.stderr); return False

def ts(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def tcomp(): return date.today().strftime("%Y%m%d")
def tiso(): return date.today().isoformat()
def tslug(): return datetime.now().strftime("%Y%m%d-%H%M%S")

def call_llm(system: str, user: str, provider: str = "default") -> Optional[str]:
    """Call the LLM. If a provider CLI is available, shell out; else print prompts to stdout."""
    if provider and provider != "default":
        cmds = {"claude": ["claude", "chat", "--print"], "openai": ["openai", "api", "chat.completions.create", "-m", "gpt-4o"],
                "deepseek": ["deepseek", "chat"], "together": ["together", "chat"]}
        if provider in cmds:
            try:
                proc = subprocess.run(cmds[provider], input=json.dumps({"system": system, "messages": [{"role": "user", "content": user}]}),
                                       capture_output=True, text=True, timeout=120)
                if proc.returncode == 0: return proc.stdout.strip()
                print(f"  \u26a0  LLM ({provider}) error: {proc.stderr.strip()}", file=sys.stderr); return None
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                print(f"  \u26a0  LLM ({provider}) failed: {e}", file=sys.stderr); return None
    sep = "=" * 70; print(f"\n{sep}\n  SYSTEM PROMPT [{provider}]:\n{sep}\n{system}\n\n{sep}\n  USER PROMPT [{provider}]:\n{sep}\n{user}", file=sys.stderr)
    return None

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

def stage1_analyze(text: str, orient: dict, provider: str, slug: str) -> Optional[str]:
    parts = [f"## Wiki Conventions (CLAUDE.md)\n{orient.get('CLAUDE.md','')}",
             f"## Wiki Scope (PURPOSE.md)\n{orient.get('PURPOSE.md','')}",
             f"## Current Wiki Index\n{orient.get('wiki/index.md','')}",
             f"## Source Document ({slug})\n{text}"]
    print(f"  Stage 1: Analyzing ({len(text)} chars)...", file=sys.stderr)
    result = call_llm(STAGE1_SYSTEM, "\n\n".join(parts), provider)
    return result or read_response()

def stage1_consolidate(analyses: list, provider: str) -> Optional[str]:
    if len(analyses) <= 1: return analyses[0] if analyses else None
    sys_p = "Consolidate these chunk analyses into one coherent analysis. Merge entities, concepts, claims, relationships. Remove duplicates."
    user = "## Chunk Analyses\n\n" + "\n\n---\n\n".join(f"### Chunk {i+1}\n{a}" for i,a in enumerate(analyses))
    return call_llm(sys_p, user, provider) or read_response()

def stage2_generate(analysis: str, slug: str, src_path: str, orient: dict, provider: str) -> Optional[str]:
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
    return call_llm(STAGE2_SYSTEM, "\n\n".join(parts), provider) or read_response()

FILE_RE = re.compile(r"^---FILE:\s*(.+?)\s*$\n^---$\n(.*?)(?=^---(?:FILE|REVIEW):|\Z)", re.MULTILINE|re.DOTALL)
REVIEW_RE = re.compile(r"^---REVIEW:\s*(.+?)\s*$\n(.*?)(?=^---(?:FILE|REVIEW):|\Z)", re.MULTILINE|re.DOTALL)

def parse_blocks(text: str):
    files = [(m.group(1).strip(), m.group(2).strip()) for m in FILE_RE.finditer(text)]
    reviews = [(m.group(1).strip(), m.group(2).strip()) for m in REVIEW_RE.finditer(text)]
    return files, reviews

def parse_fm(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m: return {}
    return {line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
            for line in m.group(1).splitlines() if ":" in line and not line.strip().startswith("#")}

def write_wiki(root: str, rpath: str, content: str, pages_dir: str = None) -> tuple:
    if pages_dir:
        parts = rpath.split("/", 1)
        if len(parts) == 2:
            rpath = parts[1]
        fp = os.path.join(pages_dir, rpath)
    else:
        fp = os.path.join(root, rpath)
    if os.path.exists(fp):
        if read_file(fp) and read_file(fp).strip() == content.strip(): return "skipped", True
        print(f"  \u26a0  Skipping {rpath} — exists (use --force to overwrite)", file=sys.stderr); return "skipped", True
    return ("created", True) if write_file(fp, content) else ("error", False)

def write_review(root: str, rtype: str, body: str, slug: str, audit_dir: str = None) -> Optional[str]:
    fm = parse_fm(body); ts = tslug(); fname = f"{ts}-{slug}-{rtype}.md"
    content = (f"---\nid: {ts}-{rtype}\ntarget: {fm.get('target','(unknown)')}\nseverity: suggest\nauthor: ingest-script\n"
               f"source: manual\ncreated: {datetime.now().isoformat()}\nstatus: open\ntype: {rtype}\nsource_slug: {slug}\n---\n\n"
               f"# {fm.get('title', rtype)}\n\n{fm.get('description','')}\n\n## Review body\n\n{body}\n")
    target_dir = audit_dir or os.path.join(root, "audit")
    return fname if write_file(os.path.join(target_dir, fname), content) else None

def update_index(root: str, pages: list, layout=None) -> int:
    if layout and layout.index_file:
        ip = layout.index_file
    elif layout:
        ip = os.path.join(layout.pages_dir, "index.md")
    else:
        ip = os.path.join(root, "wiki", "index.md")
    if not os.path.exists(ip): return 0
    added = 0
    with open(ip, "a", encoding="utf-8") as f:
        for p in pages:
            parts = p.split("/"); display = re.sub(r"\.md$", "", parts[-1]).replace("_"," ").replace("-"," ").title()
            f.write(f"- [[{p[:-3]}|{display}]] — (auto-added by ingest)\n"); added += 1
    return added

def append_log(root: str, slug: str, created: int, updated: int, reviews: int, log_dir: str = None) -> None:
    if log_dir:
        lp = os.path.join(log_dir, f"{tcomp()}.md")
    else:
        lp = os.path.join(root, "log", f"{tcomp()}.md")
    os.makedirs(os.path.dirname(lp) or ".", exist_ok=True)
    entry = f"\n## [{datetime.now().strftime('%H:%M')}] ingest | {slug}\n- Pages created: {created}, updated: {updated}, reviews: {reviews}\n- Timestamp: {ts()}\n"
    if os.path.exists(lp):
        with open(lp, "a", encoding="utf-8") as f: f.write(entry)
    else:
        with open(lp, "w", encoding="utf-8") as f: f.write(f"# {tiso()}\n\n{entry}")

def ingest(wiki_root: str, source_path: str, provider: str = "default", force: bool = False) -> int:
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
    
    # Stage 1: Analysis
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
                r = stage1_analyze(c, orient, provider, f"{slug}-chunk{i+1}")
                if r: analyses.append(r)
            analysis = stage1_consolidate(analyses, provider) if analyses else None
        else:
            analysis = stage1_analyze(source_text, orient, provider, slug)
        if analysis:
            try:
                with open(cache_path, "w") as f:
                    json.dump({"source_hash": s_hash, "source_slug": slug, "analysis": analysis, "timestamp": ts()}, f)
                print(f"  Cached analysis", file=sys.stderr)
            except IOError as e: print(f"  \u26a0  Cache write failed: {e}", file=sys.stderr)
    
    if not analysis:
        print("ERROR: No analysis. Set LLM_WIKI_RESPONSE_FILE with LLM output.", file=sys.stderr); return 1
    print(f"  Analysis: {len(analysis)} chars", file=sys.stderr)
    
    # Stage 2: Generation
    result = stage2_generate(analysis, slug, source_path, orient, provider)
    if not result:
        print("ERROR: No generation result. Set LLM_WIKI_RESPONSE_FILE.", file=sys.stderr); return 1
    print(f"  Generation: {len(result)} chars", file=sys.stderr)
    
    # Parse and apply
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
    args = p.parse_args()
    if args.batch:
        if not os.path.isdir(args.batch): print(f"ERROR: batch dir not found: {args.batch}", file=sys.stderr); return 1
        files = sorted(os.path.join(args.batch, f) for f in os.listdir(args.batch)
                       if f.endswith((".md",".txt",".json",".yaml",".yml")) and not f.startswith("."))
        if not files: print(f"No source files in {args.batch}", file=sys.stderr); return 1
        print(f"Batch: {len(files)} files", file=sys.stderr)
        for f in files:
            print(f"\n{'='*60}", file=sys.stderr); ec = ingest(args.wiki_root, f, args.provider, args.force)
        return ec
    return ingest(args.wiki_root, args.source_path, args.provider, args.force)

if __name__ == "__main__": sys.exit(main())
