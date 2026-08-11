#!/usr/bin/env python3
"""ask.py — Grounded "ask this wiki" question answering over summaries + pages.

``llm-wiki ask <wiki> "<question>"`` (LWM_033) answers a question grounded in
the wiki: retrieval over the LWM_030 community-summary pages + regular pages via
the LWM_032 hybrid search, a **summary-aware rerank** (community-summary pages
whose member set/key entities overlap the query's top results get boosted), then
exactly **one** structured LLM synthesis call via ``providers/registry.py``
(agent-native ``$0.00`` default, provider/``--model``/response-file inherited).

Output contract (AC#1–AC#3): ``{answer, citations: [page stems], confidence,
faithfulness}``. Every citation is verified to be a real, **retrieved** page
stem (AC#1, invariant 7); the answer's ``key_entities`` are filtered to the
member entities of the cited pages (``⊆`` faithfulness — the LWM_030
discipline, reused verbatim). Hallucinated entities are rejected.

Offline determinism (AC#2): ``--no-llm`` makes ZERO LLM calls and returns the
grounded passages (deterministic with the concept embedder); the eval gate
scores the deterministic retrieval context, never the LLM call.

Graceful degradation: no ``community-summary`` pages → flat retrieval with a
"no summaries yet — flat retrieval" note; ``ask`` NEVER auto-runs
``summarize-communities`` (summaries stay strictly opt-in — invariant 2).
``--dry-run`` prints the retrieval plan with zero LLM calls. Without the
``[semantic]`` extra, hybrid retrieval degrades to keyword+summaries
byte-identically (invariants 3/8).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from llm_wiki.core.layout import discover_layout
from llm_wiki.core.frontmatter import parse_frontmatter
from llm_wiki.core.wikilinks import WIKILINK_RE
from llm_wiki.graph.resolve import normalize
from llm_wiki.graph.summarize import _faithful_entities
from llm_wiki.graph.suggest import extract_entities, load_pages
from llm_wiki.providers.registry import call_llm_structured

# LWM_030's per-member prompt budget (char proxy keeps the base install pure).
# Grounded-passage excerpt budget for the synthesis prompt.
PASSAGE_CHARS = 600

# Rerank tiers (deterministic). Tier 0 = matching community-summary pages,
# tier 1 = their member pages (anchored), tier 2 = everything else in raw rank
# order. Separating tiers (instead of additive boosts) keeps weak vector-KNN
# noise below the anchored members regardless of its raw RRF rank.
TIER_SUMMARY = 0   # a matching community-summary page surfaces the wiki's answer node
TIER_MEMBER = 1    # members of a matching summary are anchored to it
TIER_OTHER = 2


class AskResponse(BaseModel):
    """Structured LLM output for one grounded answer (AC#1–AC#3)."""

    answer: str
    citations: "list[str]" = Field(
        default_factory=list,
        description="Exact page stems of the wiki pages the answer was built from.",
    )
    key_entities: "list[str]" = Field(default_factory=list)


def _canonical_stem(c: str) -> str:
    """Normalize a cited reference ('[[neural_network]]', 'wiki/...md', title)."""
    s = (c or "").strip()
    s = s.strip("[]").split("|")[0].split("#")[0].strip()
    if s.lower().endswith(".md"):
        s = s[:-3]
    return Path(s).stem if ("/" in s or "\\" in s) else s


def _load_summary_pages(pages) -> "list[dict]":
    """Locate community-summary pages by FRONTMATTER TYPE — never by directory.

    Summary pages are first-class ``type: community-summary`` pages (written by
    ``summarize-communities`` into ``wiki/communities/``, but the directory is
    NOT the contract — the frontmatter type is).
    """
    out = []
    for stem, (_p, text, fm) in pages.items():
        if fm and fm.get("type") == "community-summary":
            out.append({"stem": stem, "text": text, "fm": fm})
    out.sort(key=lambda s: s["stem"])
    return out


def _resolve_members(pages, summary) -> "set[str]":
    """Member page stems of a summary: frontmatter ``members`` (titles or stems)
    + ``[[wikilinks]]`` in the body, resolved against the page set."""
    title_to_stem = {}
    for stem, (_p, _t, fm) in pages.items():
        title = (fm.get("title") if fm else None) or stem
        title_to_stem[title] = stem
        title_to_stem[stem] = stem
    stems: "set[str]" = set()
    for m in summary["fm"].get("members", []):
        s = title_to_stem.get(m)
        if s is not None:
            stems.add(s)
    for target in WIKILINK_RE.findall(summary["text"]):
        t = target.split("|")[0].strip()
        s = title_to_stem.get(t)
        if s is not None:
            stems.add(s)
    return stems


def _genuine_result(r) -> bool:
    """A retrieval hit that is actually relevant (not a 0.0-score FTS5 row).

    The FTS5 OR path can return rows at BM25 score 0.0 when a question's filler
    token happens to appear in a page; those must never anchor a summary match.
    """
    if r.get("matched") in ("vector", "both"):
        return True
    return bool(r.get("score"))


def _summary_aware_rerank(results, summaries, pages, query, top_k):
    """Tier-rerank around matching community-summary pages (deterministic).

    A community-summary page is **matching** when its member set overlaps the
    query's top *genuinely relevant* raw results (positive BM25 score or a
    vector hit), or its ``key_entities`` appear in the query text. Matching
    summaries form tier 0, their member pages tier 1, everything else stays in
    raw rank order (tier 2) — so the summary-aware ordering is
    byte-deterministic regardless of the retrieval backend; ties break on stem.
    """
    if not results:
        return []
    n = len(results)
    rank_stems = [Path(r["path"]).stem for r in results]
    genuine = [r for r in results if _genuine_result(r)][:3]
    top_stems = {Path(r["path"]).stem for r in genuine}
    ql = query.lower()

    member_of: dict = {}
    for s in summaries:
        s["member_stems"] = _resolve_members(pages, s)
        for m in s["member_stems"]:
            member_of.setdefault(m, []).append(s["stem"])

    matching: "set[str]" = set()
    for s in summaries:
        if s["member_stems"] & top_stems:
            matching.add(s["stem"])
            continue
        for ke in s["fm"].get("key_entities", []):
            if any(tok in ql for tok in str(ke).lower().split()):
                matching.add(s["stem"])
                break

    tiered = []
    for i, r in enumerate(results):
        stem = rank_stems[i]
        if stem in matching:
            tier = TIER_SUMMARY
        elif any(ms in matching for ms in member_of.get(stem, [])):
            tier = TIER_MEMBER
        else:
            tier = TIER_OTHER
        tiered.append((tier, -(n - i), stem, r))
    tiered.sort(key=lambda t: (t[0], t[1], t[2]))
    return [r for _, _, _, r in tiered][:top_k]


def _build_passages(pages, results, top_k):
    """Deterministic grounded-passage list (title, type, excerpt, provenance)."""
    out = []
    for r in results:
        stem = Path(r["path"]).stem
        item = pages.get(stem)
        text = item[1] if item else ""
        fm = item[2] if item else None
        body = text.split("\n---", 2)[-1] if text.startswith("---") else text
        # Drop the H1 (the title is carried separately) for a cleaner excerpt.
        lines = body.splitlines()
        while lines and not lines[0].strip():
            lines = lines[1:]
        if lines and lines[0].lstrip().startswith("# "):
            lines = lines[1:]
        excerpt = " ".join(" ".join(lines).split())[:PASSAGE_CHARS]
        out.append({
            "stem": stem,
            "title": r.get("title") or stem,
            "path": r["path"],
            "type": (fm.get("type") if fm else None) or "page",
            "matched": r.get("matched", ""),
            "score": r.get("score"),
            "excerpt": excerpt,
        })
    return out[:top_k]


def _confidence(citations, raw_results) -> float:
    """Deterministic retrieval-derived confidence in [0, 1].

    Mean rank-normalized relevance of the citations against the pre-rerank
    result list — deterministic offline, independent of the LLM.
    """
    n = len(raw_results)
    if not citations or n == 0:
        return 0.0
    rank: dict = {}
    for i, r in enumerate(raw_results):
        rank.setdefault(Path(r["path"]).stem, i + 1)
    scores = [1.0 - (rank.get(c, n + 1) - 1) / n for c in citations]
    return round(min(1.0, sum(scores) / len(scores)), 4)


def _search_results(wiki_root, query, keyword, k, embedder=None):
    """LWM_032 retrieval: hybrid by default, ``keyword`` escape hatch.

    Without the ``[semantic]`` extra (or vectors), ``hybrid_search`` returns
    keyword results byte-identically; the returned mode reflects the ACTUAL
    backend used (``keyword`` when nothing fused).
    """
    from llm_wiki.search.query import hybrid_search, keyword_search

    if keyword:
        res = keyword_search(wiki_root, query, k)
        mode = "keyword"
    else:
        res = hybrid_search(wiki_root, query, k, embedder=embedder)
        mode = "hybrid" if any("matched" in r for r in res) else "keyword"
    return res, mode


def retrieve_grounded_passages(
    wiki_root,
    question: str,
    *,
    keyword: bool = False,
    top_k: int = 10,
    embedder=None,
) -> dict:
    """Deterministic offline retrieval core — the grounded-context contract.

    This is what ``--no-llm`` returns and what the ask eval gate scores (never
    the LLM call). Returns the reranked passages + citation stems + confidence
    + a ``note`` when the summary layer is absent. Private keys (``pages``,
    ``entities_by_stem``) power the LLM-mode faithfulness filter.
    """
    layout = discover_layout(wiki_root)
    root = layout.root
    wiki_dir = Path(layout.pages_dir)
    out = {
        "wiki_root": str(root),
        "question": question,
        "mode": "keyword" if keyword else "hybrid",
        "summary_pages": 0,
        "note": "",
        "passages": [],
        "citations": [],
        "confidence": 0.0,
        "raw_results": [],
        "matching_summaries": [],
        "pages": {},
        "entities_by_stem": {},
    }
    if not wiki_dir.is_dir():
        return out
    skip_files = frozenset(f"{s}.md" for s in layout.skip_stems)
    pages = load_pages(wiki_dir, skip_files)
    if not pages:
        return out
    out["pages"] = pages

    summaries = _load_summary_pages(pages)
    if not summaries:
        out["note"] = "no summaries yet — flat retrieval"
    else:
        out["summary_pages"] = len(summaries)

    raw, mode = _search_results(root, question, keyword, max(top_k * 3, 20),
                                embedder)
    out["mode"] = mode
    out["raw_results"] = raw
    ranked = _summary_aware_rerank(raw, summaries, pages, question, top_k)
    passages = _build_passages(pages, ranked, top_k)
    out["passages"] = passages
    out["citations"] = [p["stem"] for p in passages]
    out["confidence"] = _confidence(out["citations"], raw)
    out["entities_by_stem"] = {
        stem: {normalize(e) for e in extract_entities(text)}
        for stem, (_p, text, _fm) in pages.items()
    }
    return out


def _build_prompt(question: str, passages) -> "tuple[str, str]":
    system = (
        "You are a grounded question-answering assistant for a knowledge-base "
        "wiki. Answer the user's question using ONLY the provided passages. "
        "Cite sources using the exact page stem of each passage (the stem is the "
        "filename without .md, e.g. 'neural_network'). Cite at least one stem "
        "and ONLY stems that appear in the passage list. Draw key_entities ONLY "
        "from entities that actually appear in the cited passages."
    )
    lines = [
        f"[{i + 1}] {p['title']} (stem: {p['stem']}, type: {p['type']})\n{p['excerpt']}"
        for i, p in enumerate(passages)
    ]
    user = f"QUESTION: {question}\n\nPASSAGES:\n\n" + "\n\n".join(lines)
    return system, user


def _default_summarizer(provider: str, model, timeout):
    def _fn(system: str, user: str):
        return call_llm_structured(system, user, AskResponse,
                                   provider=provider, model=model,
                                   total_timeout=timeout)

    return _fn


def _finalize_llm_result(result, resp, retrieval) -> None:
    """Apply AC#1 (real stems) + AC#3 (answer entities ⊆ cited entities)."""
    real_stems = set(retrieval["citations"])
    title_to_stem = {}
    for stem, (_p, _t, fm) in retrieval["pages"].items():
        title = (fm.get("title") if fm else None) or stem
        title_to_stem[title] = stem
        title_to_stem[stem] = stem

    cited: "list[str]" = []
    for c in resp.citations or []:
        cand = _canonical_stem(c)
        stem = title_to_stem.get(cand, cand)
        if stem in real_stems and stem not in cited:
            cited.append(stem)
    # Faithfulness contract (invariant 7): never cite outside the retrieved set.
    if not cited:
        cited = list(retrieval["citations"])
    result["citations"] = cited
    result["answer"] = (resp.answer or "").strip() or None

    member_ents: "set[str]" = set()
    for stem in cited:
        member_ents |= retrieval["entities_by_stem"].get(stem, set())
    proposed = list(resp.key_entities or [])
    kept = _faithful_entities(proposed, member_ents)
    result["key_entities"] = kept
    result["faithfulness"] = round(len(kept) / len(proposed), 4) if proposed else 1.0


def ask(
    wiki_root,
    question: str,
    *,
    no_llm: bool = False,
    keyword: bool = False,
    provider: str = "default",
    model: Optional[str] = None,
    top_k: int = 10,
    dry_run: bool = False,
    summarizer=None,
    embedder=None,
    timeout: Optional[int] = 60,
) -> dict:
    """The ask operation. Deterministic offline when ``no_llm``/``dry_run``.

    Returns ``{answer, citations, confidence, faithfulness, passages, note, ...}``.
    LLM mode makes exactly ONE structured ``call_llm_structured`` call
    (AC#2), then verifies citations and applies the faithfulness filter.
    """
    retrieval = retrieve_grounded_passages(
        wiki_root, question, keyword=keyword, top_k=top_k, embedder=embedder
    )
    result = {
        "question": question,
        "mode": retrieval["mode"],
        "no_llm": bool(no_llm),
        "answer": None,
        "citations": list(retrieval["citations"]),
        "confidence": retrieval["confidence"],
        "faithfulness": 1.0,
        "key_entities": [],
        "passages": list(retrieval["passages"]),
        "note": retrieval["note"],
        "summary_pages": retrieval["summary_pages"],
        "llm_calls": 0,
        "top_k": top_k,
    }
    if dry_run or no_llm or not result["passages"]:
        return result

    if summarizer is None:
        summarizer = _default_summarizer(provider, model, timeout)
    system, user = _build_prompt(question, result["passages"])
    resp = summarizer(system, user)
    result["llm_calls"] = 1
    if resp is not None:
        _finalize_llm_result(result, resp, retrieval)
    return result


# ── CLI ──────────────────────────────────────────────────────────────────────

_PUBLIC_KEYS = (
    "question", "mode", "no_llm", "answer", "citations", "confidence",
    "faithfulness", "key_entities", "passages", "note", "summary_pages",
    "llm_calls", "top_k",
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-wiki ask",
        description="Ask a question grounded in the wiki: summaries + pages via "
                    "the LWM_032 hybrid path, then one grounded LLM synthesis. "
                    "LWM_033 / ADR-0029.",
    )
    parser.add_argument("wiki_root", help="Path to the wiki project root")
    parser.add_argument("question", help="The question to answer")
    parser.add_argument("--no-llm", action="store_true",
                        help="Deterministic offline mode: return the grounded "
                             "passages only (zero LLM calls)")
    parser.add_argument("--keyword", action="store_true",
                        help="Force lexical-only retrieval (no semantic fusion)")
    parser.add_argument("--provider", default="default",
                        help="LLM provider (default: detect_default_provider — "
                             "agent-native $0.00 when an agent is active)")
    parser.add_argument("--model", default=None, help="LLM model override")
    parser.add_argument("--top-k", type=int, default=10, dest="top_k",
                        help="Number of grounded passages / citations (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the retrieval plan; zero LLM calls")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    return parser


def _print_dry_run(result) -> None:
    print(f"# Ask plan: {result['question']}")
    if result.get("note"):
        print(f"Note: {result['note']}")
    print(f"Retrieval: mode={result['mode']}, top_k={result['top_k']}")
    print(f"Community-summary pages found: {result['summary_pages']}")
    print("Candidate passages (grounded context — no LLM call):")
    for i, p in enumerate(result["passages"], 1):
        print(f"  {i}. {p['title']} ({p['stem']})")
    est = sum(len(p["excerpt"]) // 4 + 1 for p in result["passages"])
    print(f"Estimated prompt tokens: ~{est}")
    print("LLM calls: 0 (dry-run; exactly 1 would be made in LLM mode)")


def _print_result(result, as_json: bool) -> None:
    if as_json:
        public = {k: result[k] for k in _PUBLIC_KEYS if k in result}
        print(json.dumps(public, indent=2, default=str))
        return
    print(f"# Ask: {result['question']}")
    if result.get("note"):
        print(f"Note: {result['note']}")
    print(f"Mode: {result['mode']}   no_llm: {result['no_llm']}   "
          f"LLM calls: {result['llm_calls']}")
    if result.get("answer"):
        print(f"Answer: {result['answer']}")
    else:
        print("Answer: (none — no_llm / dry-run / no grounded passages)")
    if result["citations"]:
        print("Citations: " + ", ".join(f"[[{c}]]" for c in result["citations"]))
    print(f"Confidence: {result['confidence']}   Faithfulness: {result['faithfulness']}")
    if result.get("key_entities"):
        print("Key entities: " + ", ".join(result["key_entities"]))
    for i, p in enumerate(result["passages"], 1):
        tag = f" [{p['matched']}]" if p.get("matched") else ""
        print(f"{i}. {p['title']} ({p['stem']}){tag}")
        if p.get("excerpt"):
            snippet = " ".join(p["excerpt"].split())[:120]
            print(f"     {snippet}…")


def run(argv: "list[str]") -> int:
    """Parse ``argv`` (without the program name) and run the ask operation."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.top_k < 1:
        parser.error("--top-k must be >= 1")
    result = ask(
        args.wiki_root, args.question,
        no_llm=args.no_llm, keyword=args.keyword, provider=args.provider,
        model=args.model, top_k=args.top_k, dry_run=args.dry_run,
    )
    if args.dry_run:
        _print_dry_run(result)
    else:
        _print_result(result, args.json)
    return 0


def main() -> int:
    """CLI entry point (mirrors cli.py's UTF-8 reconfigure convention)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            break
    return run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
