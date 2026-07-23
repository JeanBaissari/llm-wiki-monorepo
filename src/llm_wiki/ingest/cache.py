import hashlib, os, json

CACHE_DIR = ".llm-wiki/cache"

def _cache_path(wiki_root: str, source_path: str) -> str:
    return os.path.join(wiki_root, CACHE_DIR, hashlib.sha256(source_path.encode()).hexdigest()[:16] + ".json")

def cache_get(wiki_root: str, source_path: str) -> dict | None:
    cp = _cache_path(wiki_root, source_path)
    if os.path.exists(cp):
        with open(cp) as f:
            return json.load(f)
    return None

def cache_set(wiki_root: str, source_path: str, data: dict) -> None:
    cp = _cache_path(wiki_root, source_path)
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(cp, "w") as f:
        json.dump(data, f)
