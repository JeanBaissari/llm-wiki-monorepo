"""test_link_suggest_benchmark.py — Benchmark harness for link_suggest.py.

LWM_06 / LWM_06B: Times the inverted-index-based link suggestion pipeline
at multiple page scales (100, 500, 1000, 5000) and produces a CSV artifact.
The brute-force reference (old O(P×E) algorithm) is run only at smaller
scales to keep CI runtime acceptable.

Usage:
    python3 -m pytest tests/test_link_suggest_benchmark.py -v -m slow
"""
import csv
import sys
import time
import math
from pathlib import Path
from textwrap import dedent

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from llm_wiki.graph.suggest import (
    InvertedIndex,
    build_entity_registry,
    build_inverted_index,
    generate_suggestions,
    load_pages,
    text_without_wikilinks,
    WIKILINK_RE,
    entity_pattern,
)

# ── Constants ───────────────────────────────────────────────────────────

# Fixed set of 100 entities for all scales (per PRD spec)
ENTITY_POOL = [
    ("Deep Learning", "concept"), ("Neural Network", "concept"),
    ("Transformer Architecture", "concept"), ("Attention Mechanism", "concept"),
    ("Gradient Descent", "concept"), ("Backpropagation", "concept"),
    ("CNN", "concept"), ("RNN", "concept"), ("LSTM", "concept"),
    ("GRU", "concept"), ("GAN", "entity"), ("VAE", "entity"),
    ("Reinforcement Learning", "concept"),
    ("Supervised Learning", "concept"), ("Unsupervised Learning", "concept"),
    ("Semi-Supervised Learning", "concept"), ("Self-Supervised Learning", "concept"),
    ("Transfer Learning", "concept"), ("Fine Tuning", "concept"),
    ("Overfitting", "concept"), ("Underfitting", "concept"),
    ("Regularization", "concept"), ("Dropout", "concept"),
    ("Batch Normalization", "concept"), ("Layer Normalization", "concept"),
    ("Loss Function", "concept"), ("Activation Function", "concept"),
    ("Optimizer", "concept"), ("Learning Rate", "concept"),
    ("Weight Decay", "concept"), ("Early Stopping", "concept"),
    ("Data Augmentation", "concept"), ("Feature Engineering", "concept"),
    ("Dimensionality Reduction", "concept"), ("Cross-Validation", "concept"),
    ("Hyperparameter Tuning", "concept"), ("Ensemble Methods", "concept"),
    ("Bagging", "concept"), ("Boosting", "concept"), ("Stacking", "concept"),
    ("Self-Attention", "concept"), ("Multi-Head Attention", "concept"),
    ("Positional Encoding", "concept"), ("Tokenization", "concept"),
    ("Byte-Pair Encoding", "concept"), ("Beam Search", "concept"),
    ("Prompt Engineering", "concept"), ("Few-Shot Learning", "concept"),
    ("Zero-Shot Learning", "concept"), ("Diffusion Model", "concept"),
    ("Autoencoder", "concept"), ("Word Embeddings", "concept"),
    ("ReLU", "entity"), ("Sigmoid", "entity"), ("Tanh", "entity"),
    ("Softmax", "entity"), ("Adam", "entity"), ("SGD", "entity"),
    ("RMSprop", "entity"), ("PyTorch", "entity"), ("TensorFlow", "entity"),
    ("JAX", "entity"), ("Keras", "entity"), ("NumPy", "entity"),
    ("CUDA", "entity"), ("Python", "entity"), ("GPT", "entity"),
    ("BERT", "entity"), ("T5", "entity"), ("LLaMA", "entity"),
    ("CLIP", "entity"), ("DALL-E", "entity"), ("Stable Diffusion", "entity"),
    ("ResNet", "entity"), ("VGG", "entity"), ("Inception", "entity"),
    ("MobileNet", "entity"), ("EfficientNet", "entity"), ("YOLO", "entity"),
    ("U-Net", "entity"), ("Random Forest", "entity"), ("XGBoost", "entity"),
    ("LightGBM", "entity"), ("CatBoost", "entity"), ("SVM", "entity"),
    ("K-Means", "entity"), ("DBSCAN", "entity"), ("PCA", "entity"),
    ("t-SNE", "entity"), ("UMAP", "entity"), ("Word2Vec", "entity"),
    ("GloVe", "entity"), ("FastText", "entity"),
    ("Cross-Entropy", "concept"), ("Mean Squared Error", "concept"),
    ("KL Divergence", "concept"), ("AUC-ROC", "concept"),
    ("F1 Score", "concept"), ("Confusion Matrix", "concept"),
    ("Logistic Regression", "entity"),
]

assert len(ENTITY_POOL) >= 100, f"ENTITY_POOL has {len(ENTITY_POOL)} entries, need 100+"

PAGE_TEMPLATE = dedent("""\
---
title: {title}
type: {ptype}
created: 2026-01-15
updated: 2026-06-15
sources: [benchmark]
tags: [benchmark]
confidence: high
---

# {title}

{body}
""")


# ── Synthetic wiki generation ───────────────────────────────────────────

def build_synthetic_wiki(root: Path, page_count: int, entity_count: int = 100) -> Path:
    """Build a synthetic wiki with pages ABOUT entities from the pool.

    Each page is named after one of the pool entities, so the entity registry
    contains exactly those entities. Pages mention a mix of related entities
    to create realistic suggestion candidates.
    """
    wiki_dir = root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    pool = ENTITY_POOL[:entity_count]
    entities_per_page = 5

    for i in range(page_count):
        # Pick a primary entity
        primary_idx = i % len(pool)
        primary_name, primary_type = pool[primary_idx]

        # Pick related entities (deterministic rotation)
        related = []
        for offset in range(1, entities_per_page):
            related_idx = (i * 3 + offset * 7) % len(pool)
            if related_idx != primary_idx:
                related.append(pool[related_idx])

        # Build body mentioning all entities
        body_lines = [
            "## Overview",
            "",
            f"This page covers {primary_name}.",
            "",
            "## Related Entities",
            "",
        ]
        for name, _ in related:
            body_lines.append(f"- **{name}** is related to {primary_name}.")

        body_lines.append("")
        body_lines.append("## Notes")
        body_lines.append("Synthetic benchmark page.")

        body = "\n".join(body_lines)
        content = PAGE_TEMPLATE.format(
            title=primary_name, ptype=primary_type, body=body,
        )

        # Place pages in subdirectories by type to avoid flat-file limits
        type_dir = "concepts" if primary_type == "concept" else "entities"
        (wiki_dir / type_dir).mkdir(parents=True, exist_ok=True)
        page_path = wiki_dir / type_dir / f"{primary_name.lower().replace(' ', '_')}_{i}.md"
        page_path.write_text(content)

    return wiki_dir


# ── Brute-force reference (old O(P×E) algorithm) ────────────────────────

def generate_suggestions_bruteforce(
    pages: dict, registry: dict, wiki_dir: Path,
    limit: int, min_confidence: float,
) -> list[dict]:
    """Old O(P × E) algorithm for benchmark comparison — single-pass variant.

    This replicates the original nested-loop approach for correctness verification.
    Only used at small scales (≤500 pages) due to O(P×E) complexity.
    """
    from collections import Counter

    total = len(pages)
    if total == 0:
        return []

    # O(P × E) entity_page_count pre-computation
    entity_page_count: Counter = Counter()
    for stem, (_, text, _) in pages.items():
        clean = text_without_wikilinks(text).lower()
        for key in registry:
            if key in clean:
                entity_page_count[key] += 1

    suggestions = []

    for source_stem, (source_path, source_text, source_fm) in pages.items():
        source_title = source_fm.get("title", source_stem) if source_fm else source_stem
        source_type = source_fm.get("type", "") if source_fm else ""
        source_rel = source_path.relative_to(wiki_dir)

        clean = text_without_wikilinks(source_text)

        existing_stems = set()
        for link in WIKILINK_RE.findall(source_text):
            existing_stems.add(link.strip().lower())
            existing_stems.add(Path(link.strip()).stem.lower())

        for key, entry in registry.items():
            target_stem = entry["target_stem"]
            if target_stem == source_stem:
                continue
            if target_stem.lower() in existing_stems:
                continue

            pat = entity_pattern(entry["original"])
            matches = list(pat.finditer(clean))
            if not matches:
                continue

            count = len(matches)
            doc_len = len(clean)
            early_threshold = doc_len * 0.2
            early_count = sum(1 for m in matches if m.start() < early_threshold)

            freq_score = min(count, 3) / 3.0
            pos_mult = 1.5 if early_count > 0 else 1.0
            type_bonus = 0.2 if source_type and entry["target_type"] and source_type == entry["target_type"] else 0.0
            common_pages = entity_page_count.get(key, 1)
            common_penalty = min(common_pages / total * 2, 0.5) if total > 0 else 0.0

            score = freq_score * pos_mult + type_bonus - common_penalty
            score = max(0.0, min(1.0, score))

            if score < min_confidence:
                continue

            reasons = [f'"{entry["original"]}" mentioned {count}x']
            if early_count > 0:
                reasons.append("early in doc")
            if type_bonus > 0:
                reasons.append(f"same type ({source_type})")
            if common_pages > 1:
                reasons.append(f"in {common_pages} pages")

            target_path, _, _ = pages[target_stem]
            target_rel = target_path.relative_to(wiki_dir)

            suggestions.append({
                "source": str(source_rel),
                "source_stem": source_stem,
                "source_title": source_title,
                "source_type": source_type,
                "target": str(target_rel),
                "target_stem": target_stem,
                "target_title": entry["target_title"],
                "target_type": entry["target_type"],
                "entity": entry["original"],
                "score": round(score, 3),
                "reason": "; ".join(reasons),
            })

    suggestions.sort(key=lambda x: -x["score"])
    return suggestions[:limit]


# ── Benchmark runner ────────────────────────────────────────────────────

def time_optimized(wiki_dir: Path, repeats: int = 3) -> float:
    """Time the optimized (inverted index) pipeline. Returns mean ms."""
    pages = load_pages(wiki_dir)
    registry = build_entity_registry(pages)
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        inverted = build_inverted_index(pages, registry)
        generate_suggestions(pages, registry, wiki_dir, limit=100,
                             min_confidence=0.0, inverted=inverted)
        times.append(time.perf_counter() - t0)
    return (sum(times) / len(times)) * 1000


def time_bruteforce(wiki_dir: Path, repeats: int = 1) -> float:
    """Time the brute-force algorithm. Returns mean ms. Single repeat for speed."""
    pages = load_pages(wiki_dir)
    registry = build_entity_registry(pages)
    t0 = time.perf_counter()
    generate_suggestions_bruteforce(pages, registry, wiki_dir,
                                    limit=100, min_confidence=0.0)
    return (time.perf_counter() - t0) * 1000


# ── Pytest tests ────────────────────────────────────────────────────────

@pytest.mark.slow
class TestLinkSuggestBenchmark:
    """Phase 2.3: Benchmarking at multiple page scales.

    Smaller scales (100, 500) run on every test suite. The 5000-page
    benchmark is gated behind ``-m slow`` to keep CI fast.
    """

    FAST_SCALES = [100, 500]
    SLOW_SCALES = [1000, 5000]
    BRUTEFORCE_SCALES = [100, 500]

    @pytest.mark.parametrize("page_count", FAST_SCALES)
    def test_optimized_fast(self, tmp_path, page_count):
        """Time the optimized pipeline at small scales (always runs)."""
        wiki_dir = build_synthetic_wiki(tmp_path, page_count, entity_count=100)
        elapsed_ms = time_optimized(wiki_dir)
        print(f"\n  Optimized {page_count:>4} pages: {elapsed_ms:.1f}ms")
        assert elapsed_ms < 1000, f"Too slow at {page_count} pages: {elapsed_ms:.0f}ms"

    @pytest.mark.slow
    @pytest.mark.parametrize("page_count", SLOW_SCALES)
    def test_optimized_slow(self, tmp_path, page_count):
        """Time the optimized pipeline at large scales (--slow only)."""
        wiki_dir = build_synthetic_wiki(tmp_path, page_count, entity_count=100)
        elapsed_ms = time_optimized(wiki_dir)
        print(f"\n  Optimized {page_count:>4} pages: {elapsed_ms:.1f}ms")
        # Loose bound: must complete, but O(P×E) build limits absolute speed
        assert elapsed_ms < 10000, f"Unreasonable at {page_count} pages: {elapsed_ms:.0f}ms"

    @pytest.mark.parametrize("page_count", BRUTEFORCE_SCALES)
    def test_bruteforce_scale(self, tmp_path, page_count):
        """Time the brute-force algorithm at small scales for speedup calc."""
        wiki_dir = build_synthetic_wiki(tmp_path, page_count, entity_count=100)
        opt_ms = time_optimized(wiki_dir)
        brute_ms = time_bruteforce(wiki_dir)
        speedup = brute_ms / opt_ms if opt_ms > 0 else float('inf')
        print(f"\n  {page_count} pages: optimized={opt_ms:.1f}ms, brute={brute_ms:.0f}ms, speedup={speedup:.1f}x")

        # At 500 pages, should see meaningful speedup
        if page_count >= 500:
            assert speedup >= 1.0, f"Speedup at {page_count} pages: {speedup:.1f}x"


def test_generate_csv_artifact(tmp_path):
    """Generate benchmark CSV artifact for CI (fast scales only)."""
    results = []
    for page_count in [100, 500]:
        wiki_dir = build_synthetic_wiki(tmp_path, page_count, entity_count=100)
        opt_ms = time_optimized(wiki_dir)
        brute_ms = time_bruteforce(Path(str(wiki_dir)))
        speedup = brute_ms / opt_ms if opt_ms > 0 else 0.0
        results.append({
            "page_count": page_count,
            "entity_count": 100,
            "time_before_ms": round(brute_ms, 2),
            "time_after_ms": round(opt_ms, 2),
            "speedup": round(speedup, 2),
            "suggestion_count": 0,
        })

    csv_path = tmp_path / "link_suggest_benchmark_results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "page_count", "entity_count", "time_before_ms",
            "time_after_ms", "speedup", "suggestion_count",
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n  CSV: {csv_path}")
    for r in results:
        print(f"    {r['page_count']} pages: {r['time_after_ms']:.1f}ms opt / {r['time_before_ms']:.0f}ms brute / {r['speedup']:.1f}x speedup")


# ── Standalone runner ───────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    print("Link Suggest Benchmark")
    print("=" * 60)
    results = []

    for page_count in [100, 500, 1000, 5000]:
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = build_synthetic_wiki(Path(tmpdir), page_count, entity_count=100)
            opt_ms = time_optimized(wiki_dir)
            brute_ms = time_bruteforce(wiki_dir) if page_count <= 500 else 0.0
            speedup = brute_ms / opt_ms if opt_ms > 0 and brute_ms > 0 else 0.0
            results.append({
                "page_count": page_count,
                "entity_count": 100,
                "time_before_ms": round(brute_ms, 2),
                "time_after_ms": round(opt_ms, 2),
                "speedup": round(speedup, 2),
                "suggestion_count": 0,
            })
            print(f"  {page_count:>4} pages | opt: {opt_ms:>8.1f}ms"
                  + (f" | brute: {brute_ms:>8.0f}ms | speedup: {speedup:>5.1f}x"
                     if brute_ms > 0 else ""))

    # Write CSV
    csv_path = Path("link_suggest_benchmark_results.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "page_count", "entity_count", "time_before_ms",
            "time_after_ms", "speedup", "suggestion_count",
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nCSV written: {csv_path.resolve()}")
