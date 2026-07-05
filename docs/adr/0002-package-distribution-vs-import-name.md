# ADR 002: Package Distribution Name vs Import Name Separation

- **Status:** accepted
- **Date:** 2026-07-04
- **Context:** The package needed a PyPI-distinct name while keeping Python imports ergonomic. `baissarienterprises-llm-wiki` (the distribution name) would be an awkward and non-standard Python identifier. PEP 8 mandates lowercase with underscores for importable modules. Additionally, the CLI entry points needed a short, memorable command name (`llm-wiki`).
- **Decision:** Three distinct names are used: distribution name `baissarienterprises-llm-wiki` on PyPI (dashes, org-scoped), import name `llm_wiki` in Python code (underscores, PEP 8 compliant), and CLI command `llm-wiki` via `[project.scripts]` entry points that map to `llm_wiki.cli:main`. The `[tool.setuptools.packages.find]` directive constrains discovery to `src/`.
- **Consequences:** Easier: users `pip install baissarienterprises-llm-wiki` but `import llm_wiki` — standard Python convention. The 13 CLI entry points all follow the `llm-wiki-*` pattern. Harder: the name mismatch occasionally confuses newcomers who expect `import baissarienterprises_llm_wiki`. The docs must explicitly call out the mapping.
