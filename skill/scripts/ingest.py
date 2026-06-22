#!/usr/bin/env python3
"""
ingest.py — Two-Step Chain-of-Thought Ingest for LLM Wiki.

Usage:
    python3 ingest.py <wiki-root> <source-path> [--llm <provider>] [--force] [--batch <dir>]

Pipeline:
    Stage 1 (Analysis):  LLM analyzes source → extracts entities, concepts,
                         claims, relationships, contradictions
    Stage 2 (Generation): LLM takes analysis as context → produces FILE blocks
                          (wiki pages) and REVIEW blocks (issues)

Output:
    - Wiki pages written to <wiki-root>/wiki/
    - Review items written to <wiki-root>/audit/<ts>-<slug>.md
    - wiki/index.md updated with new page entries
    - log/YYYYMMDD.md updated with ingest entry
"""

import argparse
import hashlib
import json
import os
import re
import sys
import subprocess
from datetime import datetime, date
from pathlib import Path
from typing import Optional


# ── Constants ──────────────────────────────────────────────────────────────
CHUNK_SIZE = 55_000  # chars per chunk for long sources (below ~60K limit)
STAGE1_SYSTEM = (
    "You are analyzing a source document for a knowledge base. "
    "Extract key entities, concepts, claims, relationships, and contradictions. "
    "Be thorough and structured."
)
STAGE2_SYSTEM = (
    "You are writing wiki pages for a knowledge base. "
    "Output ONLY structured blocks. "
    "Each page as ---FILE: path, each issue as ---REVIEW: type."
)
SHEBANG = "#!/usr/bin/env python3"
AUDIT_SEVERITY = "suggest"  # default severity for auto-generated review items


# ── Helpers ────────────────────────────────────────────────────────────────

def slugify(path: str) -> str:
    """Derive a short slug from a file path."""
    name = Path(path).stem
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    return name.lower().strip("_") or "source"


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_file_safe(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return None


def write_file_safe(path: str, content: str) -> bool:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except IOError as e:
        print(f"  ⚠  Error writing {path}: {e}", file=sys.stderr)
        return False


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_compact() -> str:
    return date.today().strftime("%Y%m%d")


def today_iso() -> str:
    return date.today().isoformat()


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# ── LLM call ───────────────────────────────────────────────────────────────

def call_llm(system: str, user: str, provider: str = "default") -> Optional[str]:
    """Call the LLM. If no provider override is given, print prompts to stdout
    so the agent can read them and execute the LLM call externally.
    
    When a provider is set (e.g. 'claude', 'openai'), shell out to the
    appropriate CLI tool if installed.
    """
    if provider and provider != "default":
        # Try known CLI tools
        cli_map = {
            "claude": ("claude", ["claude", "chat", "--print"]),
            "openai": ("openai", ["openai", "api", "chat.completions.create",
                                  "-m", "gpt-4o"]),
            "deepseek": ("deepseek", ["deepseek", "chat"]),
            "together": ("together", ["together", "chat"]),
        }
        if provider in cli_map:
            cmd = cli_map[provider][1]
            try:
                proc = subprocess.run(
                    cmd,
                    input=json.dumps({"system": system, "messages": [
                        {"role": "user", "content": user}
                    ]}),
                    capture_output=True, text=True, timeout=120,
                )
                if proc.returncode == 0:
                    return proc.stdout.strip()
                else:
                    print(f"  ⚠  LLM ({provider}) error: {proc.stderr.strip()}",
                          file=sys.stderr)
                    return None
            except FileNotFoundError:
                print(f"  ⚠  CLI tool for '{provider}' not found. "
                      "Falling back to prompt printing.", file=sys.stderr)
            except subprocess.TimeoutExpired:
                print(f"  ⚠  LLM ({provider}) timed out after 120s.",
                      file=sys.stderr)
                return None

    # Default: print prompts to stdout for agent to read and respond
    sep = "=" * 70
    print(f"\n{sep}", file=sys.stderr)
    print(f"  SYSTEM PROMPT [{provider}]:", file=sys.stderr)
    print(f"{sep}", file=sys.stderr)
    print(system, file=sys.stderr)
    print(f"\n{sep}", file=sys.stderr)
    print(f"  USER PROMPT [{provider}]:", file=sys.stderr)
    print(f"{sep}", file=sys.stderr)
    print(user)
    return None  # Agent reads and provides response externally


def read_llm_response() -> Optional[str]:
    """Read LLM response from stderr prompt for agent execution."""
    # This is a placeholder — the real flow is: agent reads the printed
    # prompts, runs them through the LLM, and calls back via pipe.
    # For interactive use, reads from a temp file if set.
    response_file = os.environ.get("LLM_WIKI_RESPONSE_FILE")
    if response_file and os.path.exists(response_file):
        content = read_file_safe(response_file)
        if content:
            return content.strip()
    return None


# ── Orientation ────────────────────────────────────────────────────────────

def read_orientation(wiki_root: str) -> dict:
    """Read CLAUDE.md, PURPOSE.md and wiki/index.md for context."""
    result = {}
    for fname in ("CLAUDE.md", "PURPOSE.md", "wiki/index.md"):
        fpath = os.path.join(wiki_root, fname)
        content = read_file_safe(fpath)
        if content is not None:
            result[fname] = content
        else:
            result[fname] = f"({fname} not found)"
    return result


# ── Stage 1: Analysis ──────────────────────────────────────────────────────

def stage1_analyze(source_text: str, orientation: dict,
                   provider: str, source_slug: str) -> Optional[str]:
    """Run Stage 1 analysis of the source document."""
    user_parts = []
    
    # Add orientation context
    user_parts.append("## Wiki Conventions (CLAUDE.md)")
    user_parts.append(orientation.get("CLAUDE.md", ""))
    user_parts.append("\n## Wiki Scope (PURPOSE.md)")
    user_parts.append(orientation.get("PURPOSE.md", ""))
    user_parts.append("\n## Current Wiki Index (wiki/index.md)")
    user_parts.append(orientation.get("wiki/index.md", ""))
    user_parts.append(f"\n## Source Document ({source_slug})")
    user_parts.append(source_text)
    
    user_prompt = "\n\n".join(user_parts)
    
    print(f"  Stage 1: Analyzing source ({len(source_text)} chars)...",
          file=sys.stderr)
    result = call_llm(STAGE1_SYSTEM, user_prompt, provider)
    if result is None:
        # Agent mode: attempt to read response
        result = read_llm_response()
    return result


def stage1_consolidate(analyses: list[str], provider: str) -> Optional[str]:
    """Merge multiple chunk analyses into one coherent analysis."""
    if len(analyses) == 1:
        return analyses[0]
    
    system = (
        "You are consolidating multiple analyses of a long source document "
        "into one coherent, structured analysis. Merge entities, concepts, "
        "claims, relationships, and contradictions. Remove duplicates."
    )
    user = "## Chunk Analyses to Consolidate\n\n" + "\n\n---\n\n".join(
        f"### Chunk {i+1}\n{a}" for i, a in enumerate(analyses)
    )
    result = call_llm(system, user, provider)
    if result is None:
        result = read_llm_response()
    return result


# ── Stage 2: Generation ────────────────────────────────────────────────────

def stage2_generate(analysis: str, source_slug: str, source_path: str,
                    orientation: dict, provider: str) -> Optional[str]:
    """Run Stage 2 generation of wiki pages from analysis."""
    user_parts = []
    user_parts.append("## Wiki Conventions (CLAUDE.md)")
    user_parts.append(orientation.get("CLAUDE.md", ""))
    user_parts.append("\n## Wiki Scope (PURPOSE.md)")
    user_parts.append(orientation.get("PURPOSE.md", ""))
    user_parts.append("\n## Current Wiki Index")
    user_parts.append(orientation.get("wiki/index.md", ""))
    user_parts.append(f"\n## Source: {source_path}")
    user_parts.append(f"Source slug: {source_slug}")
    user_parts.append("\n---")
    user_parts.append("## Stage 1 Analysis (use as context — do NOT echo it)")
    user_parts.append(analysis)
    user_parts.append("\n---")
    user_parts.append(
        "## Instructions\n\n"
        "Based on the analysis above, produce structured blocks for new wiki "
        "pages and review items.\n\n"
        "### FILE blocks (new/updated wiki pages):\n"
        "```\n"
        "---FILE: wiki/entities/entity-name.md\n"
        "---\n"
        "title: Entity Name\n"
        "type: entity\n"
        f"created: {today_iso()}\n"
        f"updated: {today_iso()}\n"
        f"sources: [{source_slug}]\n"
        "tags: [tag1, tag2]\n"
        "---\n\n"
        "# Entity Name\n\n"
        "<page content>\n"
        "```\n\n"
        "### REVIEW blocks (issues requiring attention):\n"
        "```\n"
        "---REVIEW: missing-page\n"
        "target: wiki/entities/name.md\n"
        "title: Missing Entity\n"
        "description: This entity is referenced but has no page.\n"
        "```\n\n"
        "Valid REVIEW types: missing-page, duplicate-page, contradiction, suggestion\n\n"
        "Output ONLY structured blocks. No commentary before or after."
    )
    
    user_prompt = "\n\n".join(user_parts)
    
    print(f"  Stage 2: Generating wiki pages from analysis...",
          file=sys.stderr)
    result = call_llm(STAGE2_SYSTEM, user_prompt, provider)
    if result is None:
        result = read_llm_response()
    return result


# ── Parsing ────────────────────────────────────────────────────────────────

FILE_BLOCK_RE = re.compile(
    r"^---FILE:\s*(.+?)\s*$\n^---$\n(.*?)(?=^---(?:FILE|REVIEW):|\Z)",
    re.MULTILINE | re.DOTALL
)
REVIEW_BLOCK_RE = re.compile(
    r"^---REVIEW:\s*(.+?)\s*$\n(.*?)(?=^---(?:FILE|REVIEW):|\Z)",
    re.MULTILINE | re.DOTALL
)


def parse_file_blocks(text: str) -> list[tuple[str, str]]:
    """Parse ---FILE: blocks from LLM output. Returns [(path, content), ...]."""
    blocks = []
    for m in FILE_BLOCK_RE.finditer(text):
        path = m.group(1).strip()
        content = m.group(2).strip()
        blocks.append((path, content))
    return blocks


def parse_review_blocks(text: str) -> list[tuple[str, str]]:
    """Parse ---REVIEW: blocks from LLM output. Returns [(type, body), ...]."""
    blocks = []
    for m in REVIEW_BLOCK_RE.finditer(text):
        rtype = m.group(1).strip()
        body = m.group(2).strip()
        blocks.append((rtype, body))
    return blocks


def parse_frontmatter_fields(text: str) -> dict:
    """Extract YAML frontmatter fields from a markdown text block."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()
    return fields


# ── File writing ───────────────────────────────────────────────────────────

def write_wiki_page(wiki_root: str, rel_path: str, content: str,
                    force: bool = False) -> tuple[str, bool]:
    """Write a wiki page. Returns ('created'|'updated'|'skipped', success)."""
    full_path = os.path.join(wiki_root, rel_path)
    if not force and os.path.exists(full_path):
        # Only update if existing, unless --force
        existing = read_file_safe(full_path) or ""
        # Skip if content is the same
        if existing.strip() == content.strip():
            return ("skipped", True)
        # Overwrite — but only if the user is ok with it (log as updated)
        if not force:
            # Don't overwrite existing pages unless --force
            print(f"  ⚠  Skipping {rel_path} — exists (use --force to overwrite)",
                  file=sys.stderr)
            return ("skipped", True)
    
    ok = write_file_safe(full_path, content)
    if ok:
        status = "updated" if os.path.exists(full_path) and not force else "created"
        return (status, True)
    return ("error", False)


def write_review_item(wiki_root: str, rtype: str, body: str,
                      source_slug: str) -> tuple[str, bool]:
    """Write a review item to audit/. Returns (filename, success)."""
    ts = timestamp_slug()
    filename = f"{ts}-{source_slug}-{rtype}.md"
    audit_dir = os.path.join(wiki_root, "audit")
    os.makedirs(audit_dir, exist_ok=True)
    
    # Parse basic fields from body
    fields = parse_frontmatter_fields(body)
    target = fields.get("target", "(unknown)")
    title = fields.get("title", rtype)
    description = fields.get("description", f"Auto-generated {rtype} review")
    
    content = f"""---
id: {ts}-{rtype}
target: {target}
severity: {AUDIT_SEVERITY}
author: ingest-script
source: manual
created: {datetime.now().isoformat()}
status: open
type: {rtype}
source_slug: {source_slug}
---

# {title}

{description}

## Review body

{body}
"""
    full_path = os.path.join(audit_dir, filename)
    ok = write_file_safe(full_path, content)
    return (filename, ok)


# ── Index update ───────────────────────────────────────────────────────────

def update_index(wiki_root: str, new_pages: list[str]) -> int:
    """Add new pages to wiki/index.md under appropriate sections."""
    index_path = os.path.join(wiki_root, "wiki", "index.md")
    content = read_file_safe(index_path)
    if content is None:
        return 0
    
    added = 0
    with open(index_path, "a", encoding="utf-8") as f:
        for page in new_pages:
            # Derive section from path prefix
            parts = page.split("/")
            if len(parts) >= 3:
                section = parts[1]  # e.g., entities, concepts
                stem = re.sub(r"\.md$", "", parts[-1])
                display = stem.replace("_", " ").replace("-", " ").title()
                entry = f"- [[{page[:-3]}|{display}]] — (auto-added by ingest)\n"
                f.write(entry)
                added += 1
    return added


# ── Log append ─────────────────────────────────────────────────────────────

def append_log(wiki_root: str, slug: str, pages_created: int,
               pages_updated: int, reviews: int) -> bool:
    """Append an ingest entry to log/YYYYMMDD.md."""
    log_dir = os.path.join(wiki_root, "log")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{today_compact()}.md")
    now = datetime.now().strftime("%H:%M")
    
    entry = f"""## [{now}] ingest | {slug}
- Source ingested: {slug}
- Pages created: {pages_created}
- Pages updated: {pages_updated}
- Reviews generated: {reviews}
- Timestamp: {now_ts()}

"""
    
    if os.path.exists(log_path):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    else:
        header = f"# {today_iso()}\n\n"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(header + entry)
    return True


# ── Main pipeline ──────────────────────────────────────────────────────────

def ingest(wiki_root: str, source_path: str, provider: str = "default",
           force: bool = False) -> int:
    """Run the full two-step ingest pipeline."""
    # Validate wiki root
    if not os.path.isdir(wiki_root):
        print(f"ERROR: wiki root not found: {wiki_root}", file=sys.stderr)
        return 1
    
    # Read source
    source_text = read_file_safe(source_path)
    if source_text is None:
        print(f"ERROR: source file not found: {source_path}", file=sys.stderr)
        return 1
    
    source_slug = slugify(source_path)
    source_hash = sha256_of(source_text)
    
    print(f"Ingesting: {source_path}", file=sys.stderr)
    print(f"  Wiki root: {wiki_root}", file=sys.stderr)
    print(f"  Source slug: {source_slug}", file=sys.stderr)
    print(f"  SHA256: {source_hash[:16]}...", file=sys.stderr)
    
    # Orientation
    print("  Reading orientation files...", file=sys.stderr)
    orientation = read_orientation(wiki_root)
    
    # Cache setup
    cache_dir = os.path.join(wiki_root, "raw", ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{source_hash}.json")
    
    # ── Stage 1: Analysis ─────────────────────────────────────────────
    analysis = None
    cached = False
    
    if not force and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            analysis = cache_data.get("analysis")
            if analysis:
                cached = True
                print(f"  Using cached analysis from {cache_path}", file=sys.stderr)
        except (json.JSONDecodeError, IOError):
            pass
    
    if analysis is None:
        if len(source_text) > CHUNK_SIZE:
            # Long source: chunk it
            print(f"  Source is long ({len(source_text)} chars). Chunking...",
                  file=sys.stderr)
            chunk_size = CHUNK_SIZE
            overlaps = 2000
            chunks = []
            start = 0
            while start < len(source_text):
                end = min(start + chunk_size, len(source_text))
                chunks.append(source_text[start:end])
                if end >= len(source_text):
                    break
                start = end - overlaps
            
            print(f"  Split into {len(chunks)} chunks", file=sys.stderr)
            chunk_analyses = []
            for i, chunk in enumerate(chunks):
                print(f"  Analyzing chunk {i+1}/{len(chunks)}...", file=sys.stderr)
                result = stage1_analyze(chunk, orientation, provider,
                                        f"{source_slug}-chunk{i+1}")
                if result:
                    chunk_analyses.append(result)
                else:
                    print(f"  ⚠  Chunk {i+1} analysis failed", file=sys.stderr)
            
            if chunk_analyses:
                if len(chunk_analyses) > 1:
                    print("  Consolidating chunk analyses...", file=sys.stderr)
                    analysis = stage1_consolidate(chunk_analyses, provider)
                else:
                    analysis = chunk_analyses[0]
        else:
            analysis = stage1_analyze(source_text, orientation, provider, source_slug)
        
        if analysis is None:
            analysis = read_llm_response()
        
        if analysis:
            # Cache the analysis
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump({"source_hash": source_hash,
                               "source_slug": source_slug,
                               "analysis": analysis,
                               "timestamp": now_ts()}, f)
                print(f"  Cached analysis to {cache_path}", file=sys.stderr)
            except IOError as e:
                print(f"  ⚠  Failed to cache analysis: {e}", file=sys.stderr)
    
    if not analysis:
        print("ERROR: Stage 1 analysis failed (no LLM response received)",
              file=sys.stderr)
        print("  The prompts were printed above. Run them through your LLM, "
              "set LLM_WIKI_RESPONSE_FILE=/path/to/response, and re-run.",
              file=sys.stderr)
        return 1
    
    print(f"  Analysis complete ({len(analysis)} chars)", file=sys.stderr)
    
    # ── Stage 2: Generation ───────────────────────────────────────────
    result = stage2_generate(analysis, source_slug, source_path,
                             orientation, provider)
    if result is None:
        result = read_llm_response()
    
    if not result:
        print("ERROR: Stage 2 generation failed (no LLM response received)",
              file=sys.stderr)
        return 1
    
    print(f"  Generation complete ({len(result)} chars)", file=sys.stderr)
    
    # ── Parse output ──────────────────────────────────────────────────
    file_blocks = parse_file_blocks(result)
    review_blocks = parse_review_blocks(result)
    
    print(f"  Parsed: {len(file_blocks)} FILE blocks, "
          f"{len(review_blocks)} REVIEW blocks", file=sys.stderr)
    
    # ── Write wiki pages ──────────────────────────────────────────────
    pages_created = 0
    pages_updated = 0
    new_page_paths = []
    
    for page_path, page_content in file_blocks:
        status, ok = write_wiki_page(wiki_root, page_path, page_content, force)
        if ok:
            if status == "created":
                pages_created += 1
                new_page_paths.append(page_path)
                print(f"  ✓ Created: {page_path}", file=sys.stderr)
            elif status == "updated":
                pages_updated += 1
                print(f"  ✓ Updated: {page_path}", file=sys.stderr)
            else:
                print(f"  - Skipped: {page_path}", file=sys.stderr)
        else:
            print(f"  ⚠  Error writing: {page_path}", file=sys.stderr)
    
    # ── Write review items ────────────────────────────────────────────
    reviews_written = 0
    for rtype, body in review_blocks:
        fname, ok = write_review_item(wiki_root, rtype, body, source_slug)
        if ok:
            reviews_written += 1
            print(f"  ✓ Review: audit/{fname}", file=sys.stderr)
        else:
            print(f"  ⚠  Error writing review", file=sys.stderr)
    
    # ── Update index ──────────────────────────────────────────────────
    if new_page_paths:
        added = update_index(wiki_root, new_page_paths)
        if added > 0:
            print(f"  ✓ Added {added} entries to wiki/index.md", file=sys.stderr)
    
    # ── Log ───────────────────────────────────────────────────────────
    append_log(wiki_root, source_slug, pages_created, pages_updated,
               reviews_written)
    
    # ── Report ────────────────────────────────────────────────────────
    print(f"\n✅ Ingest complete: {source_slug}", file=sys.stderr)
    print(f"   Pages created:  {pages_created}", file=sys.stderr)
    print(f"   Pages updated:  {pages_updated}", file=sys.stderr)
    print(f"   Reviews:        {reviews_written}", file=sys.stderr)
    
    return 0


# ── CLI entry point ────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Two-Step Chain-of-Thought Ingest for LLM Wiki",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("wiki_root", help="Path to the wiki root directory")
    parser.add_argument("source_path", help="Path to the source document")
    parser.add_argument("--llm", dest="provider", default="default",
                        help="LLM provider (default, claude, openai, deepseek, together)")
    parser.add_argument("--force", action="store_true",
                        help="Skip cache, overwrite existing pages")
    parser.add_argument("--batch", metavar="DIR",
                        help="Batch mode: process all sources in a directory")
    
    args = parser.parse_args()
    
    if args.batch:
        # Batch mode: process all files in directory
        batch_dir = args.batch
        if not os.path.isdir(batch_dir):
            print(f"ERROR: batch directory not found: {batch_dir}", file=sys.stderr)
            return 1
        
        files = sorted(
            os.path.join(batch_dir, f) for f in os.listdir(batch_dir)
            if f.endswith((".md", ".txt", ".json", ".yaml", ".yml"))
            and not f.startswith(".")
        )
        if not files:
            print(f"No source files found in {batch_dir}", file=sys.stderr)
            return 1
        
        print(f"Batch mode: processing {len(files)} files from {batch_dir}",
              file=sys.stderr)
        total_created = 0
        total_updated = 0
        total_reviews = 0
        exit_code = 0
        
        for fpath in files:
            print(f"\n{'='*60}", file=sys.stderr)
            ec = ingest(args.wiki_root, fpath, args.provider, args.force)
            if ec != 0:
                exit_code = ec
                print(f"  ⚠  Failed: {fpath}", file=sys.stderr)
        
        return exit_code
    
    return ingest(args.wiki_root, args.source_path, args.provider, args.force)


if __name__ == "__main__":
    sys.exit(main())
