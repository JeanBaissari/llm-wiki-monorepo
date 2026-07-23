from llm_wiki.ops.health import main as health_main
from llm_wiki.ops.serve import main as serve_main
from llm_wiki.ops.benchmark import main as benchmark_main
from llm_wiki.ops.migrate import main as migrate_main

__all__ = ["health_main", "serve_main", "benchmark_main", "migrate_main"]
