import re
from datetime import datetime, date

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

def slugify(path: str) -> str:
    from pathlib import Path
    name = Path(path).stem
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name).lower().strip("_") or "source"

def ts(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def tcomp(): return date.today().strftime("%Y%m%d")
def tiso(): return date.today().isoformat()
def tslug(): return datetime.now().strftime("%Y%m%d-%H%M%S")
