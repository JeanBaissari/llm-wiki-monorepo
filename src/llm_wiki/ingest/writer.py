import os, re, sys
from pathlib import Path
from typing import Optional

from llm_wiki.core.atomic import atomic_write
from llm_wiki.core.hashing import compute_hash, read_hash, inject_hash
from llm_wiki.core.locking import WikiLock, DEFAULT_LOCK_TIMEOUT
from llm_wiki.ingest.blocks import parse_fm, ts, tcomp, tslug

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

def write_wiki(root: str, rpath: str, content: str, pages_dir: str = None,
               force: bool = False, lock_timeout=None) -> tuple:
    if pages_dir:
        parts = rpath.split("/", 1)
        if len(parts) == 2:
            rpath = parts[1]
        fp = os.path.join(pages_dir, rpath)
    else:
        fp = os.path.join(root, rpath)
    try:
        lock = WikiLock(fp, timeout=lock_timeout or DEFAULT_LOCK_TIMEOUT)
        try:
            lock.__enter__()
        except TimeoutError:
            return ("locked", False)
        try:
            current = read_file(fp)
            if current and not force:
                if current.strip() == content.strip():
                    return ("skipped", True)
                expected = read_hash(content)
                current_hash = read_hash(current) if current else ""
                if expected and current_hash and expected != current_hash:
                    conflict_path = fp.replace(".md", " (conflict).md")
                    if atomic_write(conflict_path, content):
                        print(f"  \u26a0  CONFLICT: {rpath} was modified. Changes saved to {os.path.basename(conflict_path)}.", file=sys.stderr)
                        return ("conflict", True)
                    return ("error", False)
            final = inject_hash(content)
            ok = atomic_write(fp, final)
            status = "updated" if current else "created"
            return (status, True) if ok else ("error", False)
        finally:
            try:
                lock.__exit__(None, None, None)
            except Exception:
                pass
    except ImportError:
        if os.path.exists(fp):
            if read_file(fp) and read_file(fp).strip() == content.strip(): return ("skipped", True)
            print(f"  \u26a0  Skipping {rpath} \u2014 exists (use --force to overwrite)", file=sys.stderr); return ("skipped", True)
        return ("created", True) if write_file(fp, content) else ("error", False)

def write_review(root: str, rtype: str, body: str, slug: str, audit_dir: str = None) -> Optional[str]:
    from datetime import datetime
    fm = parse_fm(body); ts_slug = tslug(); fname = f"{ts_slug}-{slug}-{rtype}.md"
    content = (f"---\nid: {ts_slug}-{rtype}\ntarget: {fm.get('target','(unknown)')}\nseverity: suggest\nauthor: ingest-script\n"
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
    existing = set()
    if os.path.exists(ip):
        with open(ip, "r", encoding="utf-8") as f:
            existing = set(re.findall(r'\[\[([^\]|#]+)', f.read()))
    added = 0
    lines_to_add = []
    for p in pages:
        link = p[:-3]
        if link in existing: continue
        existing.add(link)
        display = re.sub(r"\.md$", "", p.split("/")[-1]).replace("_"," ").replace("-"," ").title()
        lines_to_add.append(f"- [[{link}|{display}]] \u2014 (auto-added by ingest)\n"); added += 1
    if lines_to_add:
        current = read_file(ip) or ""
        if not current.endswith("\n"):
            current += "\n"
        current += "".join(lines_to_add)
        atomic_write(ip, current)
    return added

def append_log(root: str, slug: str, created: int, updated: int, reviews: int, log_dir: str = None, operation_id: str = "") -> None:
    if log_dir:
        lp = os.path.join(log_dir, f"{tcomp()}.md")
    else:
        lp = os.path.join(root, "log", f"{tcomp()}.md")
    os.makedirs(os.path.dirname(lp) or ".", exist_ok=True)
    from datetime import datetime
    op_ref = f" [op: {operation_id[:12]}]" if operation_id else ""
    entry = f"\n## [{datetime.now().strftime('%H:%M')}] ingest | {slug}{op_ref}\n- Pages created: {created}, updated: {updated}, reviews: {reviews}\n- Timestamp: {ts()}\n"
    if os.path.exists(lp):
        current = read_file(lp) or ""
        atomic_write(lp, current + entry)
    else:
        atomic_write(lp, f"# {ts()[:10]}\n\n{entry}")
