#!/usr/bin/env python3
"""
scaffold.py — Bootstrap a new LLM Wiki directory structure.

Usage:
    python3 scaffold.py <wiki-root> "<Topic Title>" [--template <name>]

Examples:
    python3 scaffold.py ~/wikis/ai-research "AI Research"
    python3 scaffold.py ~/wikis/my-codebase "My Project" --template codebase
    python3 scaffold.py ~/wikis/strategy-lab "Strategy Lab" --template algorithmic-trading

Templates available:
    research, codebase, finance, algorithmic-trading, cybersecurity,
    machine-learning, prompt-engineering, copywriting, marketing,
    design-systems, architecture, crypto, commodities, decompilers,
    medicine, developer-tools, personal-growth, reading, business

Creates:
    <wiki-root>/
    ├── PURPOSE.md         (project purpose — from template)
    ├── CLAUDE.md          (schema — from template's SCHEMA.md)
    ├── log/               (per-day operation log)
    ├── audit/             (human feedback inbox)
    ├── raw/               (immutable sources)
    ├── wiki/              (LLM-generated knowledge)
    └── outputs/           (query answers, charts)
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import date, datetime


TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
DEFAULT_TEMPLATE = "research"


def list_templates() -> list[str]:
    """Discover available templates in the templates/ directory."""
    if not TEMPLATES_DIR.exists():
        return [DEFAULT_TEMPLATE]
    templates = []
    for d in sorted(TEMPLATES_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith("."):
            if (d / "SCHEMA.md").exists():
                templates.append(d.name)
    return templates or [DEFAULT_TEMPLATE]


def get_template(template_name: str) -> Path:
    """Resolve template path, falling back to default if not found."""
    template_path = TEMPLATES_DIR / template_name
    if template_path.exists() and (template_path / "SCHEMA.md").exists():
        return template_path
    print(f"⚠️  Template '{template_name}' not found, falling back to '{DEFAULT_TEMPLATE}'")
    return TEMPLATES_DIR / DEFAULT_TEMPLATE


def load_extra_dirs(template_path: Path) -> list[str]:
    """Load extra directories from template's extra-dirs.json."""
    extra_json = template_path / "extra-dirs.json"
    if extra_json.exists():
        try:
            with open(extra_json) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def scaffold(root: str, title: str, template_name: str = DEFAULT_TEMPLATE) -> None:
    today = date.today()
    today_iso = today.isoformat()
    today_compact = today.strftime("%Y%m%d")
    now_hm = datetime.now().strftime("%H:%M")

    template_path = get_template(template_name)
    extra_dirs = load_extra_dirs(template_path)

    # ── Base directories ─────────────────────────────────────────────
    base_dirs = [
        "raw/articles",
        "raw/papers",
        "raw/notes",
        "raw/refs",
        "wiki/concepts",
        "wiki/entities",
        "wiki/summaries",
        "wiki/comparisons",
        "wiki/graphs",
        "wiki/synthesis",
        "outputs/queries",
        "log",
        "audit",
        "audit/resolved",
    ]

    # Add template-specific directories
    all_dirs = base_dirs + [f"wiki/{d}" for d in extra_dirs]

    for d in all_dirs:
        os.makedirs(os.path.join(root, d), exist_ok=True)
    print(f"✓ Created directory tree under {root}/")

    # .gitkeep for empty audit dirs
    _write(root, "audit/.gitkeep", "")
    _write(root, "audit/resolved/.gitkeep", "")

    # ── PURPOSE.md (from template) ────────────────────────────────────
    purpose_src = template_path / "PURPOSE.md"
    if purpose_src.exists():
        purpose_content = purpose_src.read_text(encoding="utf-8")
        _write(root, "PURPOSE.md", purpose_content)
        print(f"✓ Created PURPOSE.md (from {template_name} template)")
    else:
        _write(root, "PURPOSE.md", f"# {title}\n\n> Project purpose — define why this wiki exists.\n")
        print("✓ Created PURPOSE.md (default)")

    # ── CLAUDE.md (from template's SCHEMA.md) ─────────────────────────
    schema_src = template_path / "SCHEMA.md"
    if schema_src.exists():
        schema_content = schema_src.read_text(encoding="utf-8")
        # Replace template variables
        schema_content = schema_content.replace("<Topic Title>", title)
        schema_content = schema_content.replace("{{title}}", title)
        _write(root, "CLAUDE.md", schema_content)
        print(f"✓ Created CLAUDE.md (from {template_name} template)")
    else:
        # Fallback: generic CLAUDE.md
        claude_md = _default_claude_md(title)
        _write(root, "CLAUDE.md", claude_md)
        print("✓ Created CLAUDE.md (default)")

    # ── log/<today>.md ────────────────────────────────────────────────
    log_md = f"""# {today_iso}

## [{now_hm}] scaffold | Initialized {title} knowledge base
- Template: {template_name}
- Created directory tree (raw/, wiki/, log/, audit/, outputs/)
- Created PURPOSE.md and CLAUDE.md from {template_name} template
- Created wiki/index.md category skeleton
"""
    _write(root, f"log/{today_compact}.md", log_md)
    print(f"✓ Created log/{today_compact}.md")

    # ── wiki/index.md ─────────────────────────────────────────────────
    # Try to load template's index format if it exists
    index_template = template_path / "index-format.md"
    if index_template.exists():
        index_md = index_template.read_text(encoding="utf-8")
        index_md = index_md.replace("{{title}}", title)
    else:
        index_md = f"""# Index — {title}

> One-sentence scope of the wiki.

## 🔖 Navigation
- [[#Concepts]] · [[#Entities]] · [[#Summaries]] · [[#Comparisons]] · [[#Open Questions]]

## Concepts

*(none yet)*

## Entities

*(none yet)*

## Summaries (chronological)

*(none yet)*

## Comparisons

*(none yet)*

## Open Questions

- <First research question>
"""
    _write(root, "wiki/index.md", index_md)
    print("✓ Created wiki/index.md")

    # ── Template-specific extra files ─────────────────────────────────
    for item in template_path.iterdir():
        if item.name in ("SCHEMA.md", "PURPOSE.md", "extra-dirs.json", "index-format.md"):
            continue
        if item.is_file() and item.suffix in (".md", ".json", ".yaml", ".yml"):
            dest = os.path.join(root, item.name)
            if not os.path.exists(dest):
                shutil.copy2(item, dest)
                print(f"✓ Copied {item.name}")

    # ── Summary ───────────────────────────────────────────────────────
    extra_dir_list = "\n".join(f"  - wiki/{d}/" for d in extra_dirs) if extra_dirs else "  (none)"
    print(f"""
✅ Wiki scaffolded at: {root}/
   Template: {template_name}
   Extra dirs:
{extra_dir_list}

Next steps:
  1. Read PURPOSE.md — understand why this wiki exists
  2. Fill in CLAUDE.md — define scope and naming conventions
  3. Add sources to raw/ (use Obsidian Web Clipper or browser extension)
  4. Run ingest: python3 skill/scripts/ingest.py {root} raw/<file>.md
  5. Ask questions: "what does the wiki say about X?"
  6. Run lint periodically:  python3 skill/scripts/lint_wiki.py {root}
  7. Get graph insights:    python3 skill/scripts/graph_insights.py {root}
  8. Process feedback:      python3 skill/scripts/audit_review.py {root} --open
  9. Deep research:          python3 skill/scripts/deep_research.py {root} "<topic>"
""")


def _default_claude_md(title: str) -> str:
    return f"""# {title} Knowledge Base

> Schema document — read at the start of every session together with `wiki/index.md`.
> Update after every major compile, ingest batch, or structural change.

## Scope

What this wiki covers:
- <describe the topic area>

What this wiki deliberately excludes:
- <describe out-of-scope areas>

## Operations

This wiki follows the llm-wiki skill's operations: `compile`, `ingest`, `query`, `lint`, `audit`, `research`, `insights`.
Every operation appends an entry to `log/YYYYMMDD.md`.

## Naming conventions

- **Concept pages** (`wiki/concepts/`): Title Case noun phrases.
- **Folder-split concepts**: when a topic exceeds ~1200 words. Contains `index.md` + one file per aspect.
- **Entity pages** (`wiki/entities/`): Proper names.
- **Summary pages** (`wiki/summaries/`): kebab-case source slug.
- **Comparison pages** (`wiki/comparisons/`): `entity-a-vs-entity-b.md`

All pages require YAML frontmatter: `title`, `type`, `created`, `updated`, `sources`, `tags`.

## Current articles

*None yet — update this list after every compile.*

## Open research questions

- <What do you want to understand better?>

## Research gaps

Sources to ingest:
- [ ] <URL or paper title> — why it's relevant

## Notes for the LLM

- Language: <en>
- Tone: <neutral, academic, conversational>
- Depth: <survey-level | deep technical>
- Handling contradictions: state both, cite each, add to Open Research Questions.
"""


def _write(root: str, path: str, content: str) -> None:
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Bootstrap a new LLM Wiki directory structure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Available templates:\n  " + "\n  ".join(list_templates()),
    )
    parser.add_argument("wiki_root", nargs="?", help="Path to create the wiki at")
    parser.add_argument("title", nargs="?", help="Topic title for the wiki")
    parser.add_argument(
        "--template", "-t",
        default=DEFAULT_TEMPLATE,
        choices=list_templates(),
        help=f"Template to use (default: {DEFAULT_TEMPLATE})",
    )
    parser.add_argument(
        "--list-templates", "-l",
        action="store_true",
        help="List available templates and exit",
    )

    args = parser.parse_args()

    if args.list_templates:
        print("Available templates:")
        for t in list_templates():
            print(f"  {t}")
        sys.exit(0)

    if not args.wiki_root or not args.title:
        parser.error("wiki_root and title are required (unless using --list-templates)")

    scaffold(args.wiki_root, args.title, args.template)
