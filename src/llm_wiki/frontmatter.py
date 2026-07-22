"""frontmatter.py — Canonical frontmatter parser for LLM Wiki.

This is the single source of truth for parsing YAML frontmatter from
wiki and audit markdown files. All other modules should import from here.

Usage:
    from llm_wiki.frontmatter import parse_frontmatter
    fm = parse_frontmatter(text)  # dict or None
"""

import re


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict | None:
    """Minimal YAML-ish frontmatter parser.

    Handles the flat key:value fields and one-level lists/arrays actually
    used by wiki and audit files.  Does not handle arbitrary YAML —
    intentional, to avoid a pyyaml dependency.

    Returns None if no frontmatter block is found.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    body = m.group(1)
    result: dict = {}
    for line in body.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                parts = [p.strip() for p in inner.split(",")]
                parsed: list = []
                for p in parts:
                    if p.isdigit() or (p.startswith("-") and p[1:].isdigit()):
                        parsed.append(int(p))
                    else:
                        parsed.append(p.strip('"').strip("'"))
                result[key] = parsed
        elif val.startswith('"') and val.endswith('"'):
            result[key] = val[1:-1].replace("\\n", "\n").replace('\\"', '"')
        elif val.startswith("'") and val.endswith("'"):
            result[key] = val[1:-1]
        else:
            result[key] = val
    return result
