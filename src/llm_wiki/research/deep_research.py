#!/usr/bin/env python3
"""
deep_research.py — Agent-driven deep research for LLM Wiki.

Orchestrates multi-source research: discovers URLs, prompts the agent to fetch
sources, auto-ingests each one, creates a synthesis page, and logs progress.

Usage:
    python3 deep_research.py <wiki-root> "<topic>" [--depth <n>] [--sources <n>] [--urls <url1,url2>]

Phases executed in a single pass:
    1. Source discovery — prints search query, reads URLs from --urls or stdin
    2. Source fetching — prints fetch instructions for each URL; checks results
    3. Auto-ingest — calls ingest.py as subprocess for each fetched source
    4. Synthesis — creates stub synthesis page in wiki/synthesis/
    5. Logging — appends entry to log/YYYYMMDD.md
    6. Report — prints summary table
"""

import argparse
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path


from llm_wiki.core.layout import discover_layout
from llm_wiki.operation import OperationContext


def slugify(text: str) -> str:
    """Convert text to a kebab-case slug."""
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', text.lower().strip())).strip('-')


def derive_slug(url: str, fallback_idx: int) -> str:
    """Derive a readable slug from a URL."""
    parsed = urllib.parse.urlparse(url)
    stem = parsed.path.rstrip('/').split('/')[-1] if parsed.path.strip('/') else ''
    # Strip common extensions
    for ext in ('.html', '.htm', '.php', '.asp', '.aspx', '.jsp'):
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
            break
    base = stem or parsed.netloc.replace('.', '-')
    s = slugify(base)
    return s or f'source-{fallback_idx + 1}'


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Agent-driven deep research for LLM Wiki'
    )
    parser.add_argument('wiki_root', help='Path to the wiki root directory')
    parser.add_argument('topic', help='Research topic')
    parser.add_argument('--depth', type=int, default=2,
                        help='Research depth (default: 2)')
    parser.add_argument('--sources', type=int, default=5,
                        help='Max sources to collect (default: 5)')
    parser.add_argument('--urls', help='Comma-separated URLs to use directly')

    args = parser.parse_args()

    with OperationContext("deep-research", wiki_root=args.wiki_root,
                          inputs={"topic": args.topic, "urls": args.urls,
                                  "depth": args.depth, "sources": args.sources}) as ctx:
        root = Path(args.wiki_root)
        layout = discover_layout(args.wiki_root)
        topic = args.topic
        topic_slug = slugify(topic)
        now = datetime.now()
        date_iso = now.strftime('%Y-%m-%d')
        today = now.strftime('%Y%m%d')
        now_ts = now.strftime('%H:%M')

        # ── Phase 1: Source discovery ──────────────────────────────────────────
        urls: list[str] = []
        if args.urls:
            urls = [u.strip() for u in args.urls.split(',') if u.strip()]
        else:
            print(f'SEARCH: Search the web for: {topic} '
                  f'(depth {args.depth}, up to {args.sources} sources)',
                  flush=True)
            print('STDIN: Provide URLs now (one per line, then Ctrl+D / EOF):',
                  file=sys.stderr, flush=True)
            try:
                for line in sys.stdin:
                    line = line.strip()
                    if line:
                        urls.append(line)
            except (EOFError, KeyboardInterrupt):
                pass

        if not urls:
            print('No URLs provided. Re-run with --urls or pipe URLs via stdin.')
            ctx.succeed()
            return 0

        # ── Phase 2: Source fetching instructions ──────────────────────────────
        raw_dir = Path(layout.raw_dir) / 'articles' if layout.raw_dir else root / 'raw' / 'articles'
        syn_dir = Path(layout.pages_dir) / 'synthesis'
        log_dir = Path(layout.log_dir) if layout.log_dir else root / 'log'
        for d in (raw_dir, syn_dir, log_dir):
            d.mkdir(parents=True, exist_ok=True)

        fetch_targets: list[tuple[str, str, Path]] = []
        for i, url in enumerate(urls):
            slug = derive_slug(url, i)
            target = raw_dir / f'{slug}.md'
            fetch_targets.append((url, slug, target))
            print(f'FETCH: Fetch and save this URL as markdown: '
                  f'{url} → raw/articles/{slug}.md', flush=True)

        # Check which were actually fetched by the agent
        fetched = [(u, s, t) for u, s, t in fetch_targets if t.exists()]
        if not fetched:
            print('WAITING: No sources fetched yet. Run this script again '
                  'after the agent fetches the URLs above.', flush=True)
            for _, _, target in fetch_targets:
                ctx.add_touched("read", str(target))
            ctx.succeed()
            return 0

        for _, _, target in fetched:
            ctx.add_touched("read", str(target))

        # ── Phase 3: Auto-ingest ───────────────────────────────────────────────
        ingest_mod_path = 'llm_wiki.ingest.pipeline'
        ingested: list[str] = []

        for url, slug, target in fetched:
            print(f'INGEST: python3 -m {ingest_mod_path} {root} {target}', flush=True)
            result = subprocess.run(
                [sys.executable, '-m', ingest_mod_path, str(root), str(target)],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                ingested.append(slug)
                print(f'  ✓ Ingested: {slug}', flush=True)
            else:
                print(f'  ✗ Ingest failed (exit {result.returncode}): '
                      f'{result.stderr[:200]}', flush=True)
                ctx.add_error("ingest-failed",
                              result.stderr[:500] if result.stderr else "Unknown error",
                              path=str(target), recoverable=True)

        # ── Phase 4: Synthesis page ────────────────────────────────────────────
        syn_path = syn_dir / f'{topic_slug}.md'
        source_bullets = '\n'.join(
            f'- [[raw/articles/{s}|{s}]]' for _, s, _ in fetched
        )
        syn_content = f'''---
title: "Research Synthesis: {topic}"
type: synthesis
created: {date_iso}
updated: {date_iso}
sources: [{', '.join(s for _, s, _ in fetched)}]
tags: [research, synthesis]
---

# Research Synthesis: {topic}

> Agent: Replace this with a thorough synthesis across all sources below.

## Sources

{source_bullets}

## Key Findings

<!-- Agent: synthesize key findings across all sources -->

## Cross-Source Analysis

<!-- Agent: compare perspectives, identify agreements and contradictions -->

## Open Questions

<!-- Agent: what remains unanswered or needs further research? -->
'''
        from llm_wiki.core.atomic import atomic_write
        syn_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(str(syn_path), syn_content)
        ctx.add_touched("created", str(syn_path))
        print(f'SYNTHESIS: Created stub → {syn_path}', flush=True)
        print(f'SYNTHESIS_INSTRUCT: Fill in the synthesis content at '
              f'wiki/synthesis/{topic_slug}.md', flush=True)

        # ── Phase 5: Log ──────────────────────────────────────────────────────
        log_file = log_dir / f'{today}.md'
        log_entry = (
            f'## [{now_ts}] research | {topic}\n'
            f'- URLs: {len(urls)} found, {len(fetched)} fetched, '
            f'{len(ingested)} ingested\n'
            f'- Synthesis: [[synthesis/{topic_slug}]]\n'
        )
        if log_file.exists():
            current = log_file.read_text(encoding='utf-8')
            atomic_write(str(log_file), current + log_entry)
        else:
            atomic_write(str(log_file), f'# {date_iso}\n\n{log_entry}')
        ctx.add_touched("updated", str(log_file))
        print(f'LOG: Appended to {log_file}', flush=True)

        # ── Phase 6: Report ────────────────────────────────────────────────────
        print(f'''
{'=' * 55}
 DEEP RESEARCH SUMMARY
{'=' * 55}
 Topic:      {topic}
 URLs found: {len(urls)}
 Fetched:    {len(fetched)}
 Ingested:   {len(ingested)}
 Synthesis:  {syn_path}
 Wiki root:  {root}
{'=' * 55}
''', flush=True)

        ctx.succeed()
        return 0


if __name__ == '__main__':
    sys.exit(main())
