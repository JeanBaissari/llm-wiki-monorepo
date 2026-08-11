"""LWM_033 Evidence Matrix — grounded "ask this wiki" question answering.

Covers every committed Evidence-Matrix claim from the PRD:
  * citations are real page stems (AC#1)
  * --no-llm makes ZERO LLM calls and is deterministic offline (AC#2)
  * the faithfulness filter rejects hallucinated entities (AC#3)
  * without [semantic] ask degrades to keyword+summaries byte-identically (AC#4)
  * agent-native $0.00 default — no API key needed (AC#7)
  * no community-summary pages -> flat retrieval degradation (review Q(a))
The LLM path is asserted to make exactly ONE structured call.
"""

import json

from llm_wiki.graph import ask as ask_mod
from llm_wiki.graph.ask import AskResponse, ask, retrieve_grounded_passages
from llm_wiki.search.index import index_wiki

_PAGES = {
    "neural_network.md": "A neural network learns weights via backpropagation.",
    "deep_learning.md": "Deep learning stacks many neural network layers.",
    "backpropagation.md": "A neural network learns weights via backpropagation.",
    "layers.md": "Neural network layers learn hierarchical features.",
    "gradient_descent.md": "Gradient descent minimizes loss via backpropagation.",
    "transformer.md": "The transformer uses attention over sequences.",
    "self_attention.md": "Self-attention lets sequences relate tokens directly.",
    "encoder.md": "The transformer encoder processes sequences.",
    "positional_encoding.md": "Positional encoding marks token order in transformer sequences.",
    "coffee.md": "Coffee is a brewed beverage from roasted beans.",
    "espresso.md": "Espresso is a strong brewed beverage made under pressure.",
    "latte.md": "A latte is espresso with steamed milk.",
    "caffeine.md": "Caffeine is a stimulant found in coffee.",
    "memory_management.md": "Memory management allocates and reclaims application memory.",
    "caching.md": "Caching strategies store frequently accessed data.",
}

_ML_MEMBERS = ["neural_network", "deep_learning", "backpropagation",
               "layers", "gradient_descent"]
_ATTN_MEMBERS = ["transformer", "self_attention", "encoder",
                 "positional_encoding"]
_BEV_MEMBERS = ["coffee", "espresso", "latte", "caffeine"]
_SYS_MEMBERS = ["memory_management", "caching"]


def _summary_page(stem, title, members, key_entities, body):
    m = ", ".join(f'"{x}"' for x in members)
    k = ", ".join(f'"{x}"' for x in key_entities)
    return (
        "---\n"
        f"title: {title}\n"
        "type: community-summary\n"
        "community: 0\n"
        "level: 0\n"
        f"members: [{m}]\n"
        f"key_entities: [{k}]\n"
        "generated_by: test-ask\n"
        "updated: 2026-08-11\n"
        "---\n\n"
        f"# {title}\n\n{body}\n"
    )


def _build_wiki(tmp_path, with_summaries=True):
    """Indexed (optionally NOT embedded) tmp wiki: 15 pages + 4 summaries."""
    w = tmp_path / "wiki"
    w.mkdir()
    for nm, body in _PAGES.items():
        (w / nm).write_text(
            f"---\ntitle: {nm[:-3]}\ntype: concept\n---\n\n# {nm[:-3]}\n\n{body}\n",
            encoding="utf-8",
        )
    if with_summaries:
        out = w / "communities"
        out.mkdir()
        (out / "community_ml.md").write_text(_summary_page(
            "community_ml", "Machine Learning Community", _ML_MEMBERS,
            ["Neural Network", "Deep Learning"],
            "The machine learning community covers neural networks, deep "
            "learning, backpropagation, layers, and gradient descent."), encoding="utf-8")
        (out / "community_attn.md").write_text(_summary_page(
            "community_attn", "Attention Community", _ATTN_MEMBERS,
            ["Transformer", "Self-Attention"],
            "The attention community covers the transformer, self-attention, "
            "the encoder, and positional encoding."), encoding="utf-8")
        (out / "community_bev.md").write_text(_summary_page(
            "community_bev", "Beverage Community", _BEV_MEMBERS,
            ["Coffee", "Espresso"],
            "The beverage community covers coffee, espresso, latte, and "
            "caffeine."), encoding="utf-8")
        (out / "community_sys.md").write_text(_summary_page(
            "community_sys", "Systems Community", _SYS_MEMBERS,
            ["Memory Management", "Caching"],
            "The systems community covers memory management and caching "
            "strategies."), encoding="utf-8")
    index_wiki(tmp_path, rebuild=True)
    return tmp_path


def _all_stems():
    return {nm[:-3] for nm in _PAGES} | {
        "community_ml", "community_attn", "community_bev", "community_sys"}


def _noop_llm(*args, **kwargs):  # pragma: no cover - only used as a spy target
    raise AssertionError("LLM must not be called in --no-llm mode")


def test_citations_are_real_pages(tmp_path):
    """AC#1: every citation in the output is a real page stem (asserted)."""
    root = _build_wiki(tmp_path)
    result = ask(
        str(root), "what is deep learning?",
        summarizer=lambda s, u: AskResponse(
            answer="Deep learning stacks neural network layers.",
            citations=["neural_network", "FAKE_STEM_NOT_A_PAGE"],
            key_entities=["Neural Network"],
        ),
    )
    assert result["citations"], "expected grounded citations"
    for c in result["citations"]:
        assert c in _all_stems(), f"citation {c!r} is not a real page stem"
    assert "FAKE_STEM_NOT_A_PAGE" not in result["citations"]


def test_no_llm_passes_only(tmp_path, monkeypatch):
    """AC#2: --no-llm makes ZERO LLM calls and is deterministic offline."""
    root = _build_wiki(tmp_path)
    calls = []
    monkeypatch.setattr(ask_mod, "call_llm_structured", lambda *a, **k: calls.append(1))
    r1 = ask(str(root), "what is deep learning?", no_llm=True)
    r2 = ask(str(root), "what is deep learning?", no_llm=True)
    assert calls == []  # zero LLM calls
    assert r1["llm_calls"] == 0
    assert r1["answer"] is None
    assert r1["citations"] and r1["passages"]  # grounded passages present
    assert r1 == r2  # deterministic: identical output on re-run


def test_hallucinated_entity_rejected(tmp_path):
    """AC#3: answer entities outside the cited pages' member entities are dropped."""
    root = _build_wiki(tmp_path)

    def summarizer(system, user):
        return AskResponse(
            answer="Neural networks learn weights via backpropagation.",
            citations=["neural_network"],
            key_entities=["Neural Network", "UNICORN PIXIE"],
        )

    result = ask(str(root), "how do neural networks learn?", summarizer=summarizer)
    assert result["key_entities"] == ["Neural Network"]
    assert "UNICORN PIXIE" not in result["key_entities"]
    assert result["faithfulness"] == 0.5  # 1 of 2 proposed entities kept


def test_keyword_fallback_byte_identical(tmp_path):
    """AC#4: without [semantic]/vectors, hybrid degrades to keyword+summaries
    byte-identically (same citations, same passages, same note)."""
    root = _build_wiki(tmp_path)  # indexed, NOT embedded -> no semantic layer
    hybrid = retrieve_grounded_passages(str(root), "deep learning", keyword=False)
    keyword = retrieve_grounded_passages(str(root), "deep learning", keyword=True)
    assert hybrid["mode"] == "keyword"  # degradation actually happened
    assert hybrid["citations"] == keyword["citations"]
    assert hybrid["passages"] == keyword["passages"]
    assert hybrid["note"] == keyword["note"]
    assert hybrid["confidence"] == keyword["confidence"]


def test_agent_native_zero_apikey(tmp_path, monkeypatch):
    """AC#7: provider='default' with the opencode agent provider active needs
    no API key ($0.00 agent-native path via LLM_WIKI_RESPONSE_FILE)."""
    root = _build_wiki(tmp_path)
    rf = tmp_path / "response.json"
    rf.write_text(json.dumps({
        "answer": "Deep learning stacks neural network layers.",
        "citations": ["deep_learning", "community_ml"],
        "key_entities": ["Deep Learning"],
    }), encoding="utf-8")

    monkeypatch.setenv("LLM_WIKI_RESPONSE_FILE", str(rf))
    monkeypatch.setenv("LLM_WIKI_AGENT_MODE", "1")
    monkeypatch.setenv("LLM_WIKI_OPCODE_DIR", str(tmp_path / "opcode"))
    monkeypatch.setenv("LLM_WIKI_OPCODE_TIMEOUT", "0")
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                "DEEPSEEK_API_KEY", "TOGETHER_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    from llm_wiki.providers.registry import detect_default_provider
    assert detect_default_provider() == "opencode"  # no key present

    result = ask(str(root), "what is deep learning?", provider="default")
    assert result["answer"] == "Deep learning stacks neural network layers."
    assert result["llm_calls"] == 1  # exactly one structured call
    assert "deep_learning" in result["citations"]
    assert result["key_entities"] == ["Deep Learning"]
    assert result["faithfulness"] == 1.0


def test_no_summaries_flat_degradation(tmp_path):
    """Review Q(a): no community-summary pages -> flat retrieval with a note;
    ask NEVER auto-runs summarize-communities."""
    root = _build_wiki(tmp_path, with_summaries=False)
    result = ask(str(root), "what is deep learning?", no_llm=True)
    assert result["note"] == "no summaries yet — flat retrieval"
    assert result["summary_pages"] == 0
    assert result["citations"], "flat retrieval still returns pages"
    assert not (root / "wiki" / "communities").exists()  # nothing created


def test_llm_failure_degrades_to_grounded_passages(tmp_path):
    """LLM failure (None) degrades gracefully to the deterministic passages."""
    root = _build_wiki(tmp_path)
    result = ask(str(root), "what is deep learning?", summarizer=lambda s, u: None)
    assert result["llm_calls"] == 1
    assert result["answer"] is None
    assert result["citations"], "grounded passages survive LLM failure"
    assert result["faithfulness"] == 1.0


def test_llm_mode_makes_exactly_one_call(tmp_path, monkeypatch):
    """AC#2: the LLM path is exactly ONE structured call."""
    root = _build_wiki(tmp_path)
    calls = []

    def _spy(system, user, response_model, **kwargs):
        calls.append(1)
        return AskResponse(answer="x", citations=["deep_learning"],
                           key_entities=[])

    monkeypatch.setattr(ask_mod, "call_llm_structured", _spy)
    ask(str(root), "what is deep learning?", provider="default")
    assert len(calls) == 1


def test_dry_run_prints_plan_no_calls(tmp_path, monkeypatch):
    """--dry-run returns the retrieval plan with zero LLM calls."""
    root = _build_wiki(tmp_path)
    calls = []
    monkeypatch.setattr(ask_mod, "call_llm_structured", lambda *a, **k: calls.append(1))
    result = ask(str(root), "what is deep learning?", dry_run=True)
    assert calls == []
    assert result["llm_calls"] == 0
    assert result["answer"] is None
    assert result["citations"]
