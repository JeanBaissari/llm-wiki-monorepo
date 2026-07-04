"""Build fixture wikis for testing.

Creates:
  - tests/fixtures/wikis/minimal/    — 5 pages, 2 sources, 10 wikilinks
  - tests/fixtures/wikis/stale/       — Pages with dead links, orphans, stale dates
  - tests/fixtures/wikis/populated/   — 50+ pages, 100+ wikilinks, 3+ sources
  - tests/fixtures/sources/           — short.md, long.md, malformed.md
"""
import os, sys, hashlib, shutil
from pathlib import Path

REPO = Path("/home/jeanbaissari/Documents/programming/projects/llm-wiki-monorepo")
FIXTURES = REPO / "tests" / "fixtures"


def write_page(path: Path, title: str, ptype: str, body: str,
               tags: list[str] = None, sources: list[str] = None,
               created: str = "2026-01-15", updated: str = "2026-06-15",
               extra_fm: str = "", confidence: str = "high") -> None:
    """Write a wiki page with proper frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tags_str = ", ".join(tags) if tags else "test"
    sources_str = ", ".join(sources) if sources else ""
    fm = f"""---
title: {title}
type: {ptype}
created: {created}
updated: {updated}
sources: [{sources_str}]
tags: [{tags_str}]
confidence: {confidence}
{extra_fm}---

"""
    path.write_text(fm + body)


def write_source(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def write_review(audit_dir: Path, review_id: str, target: str, rtype: str,
                 title: str, desc: str, severity: str = "suggest",
                 status: str = "open", author: str = "test-script",
                 created: str = "2026-06-15") -> None:
    audit_dir.mkdir(parents=True, exist_ok=True)
    content = f"""---
id: {review_id}
target: {target}
type: {rtype}
title: {title}
severity: {severity}
author: {author}
source: manual
created: {created}
status: {status}
source_slug: test-fixture
---

# {title}

{desc}
"""
    (audit_dir / f"{review_id}.md").write_text(content)


def write_log(log_dir: Path, date_str: str, entries: list[str]) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{date_str}.md"
    content = f"# {date_str}\n\n"
    content += "\n".join(entries)
    path.write_text(content)


# ══════════════════════════════════════════════════════════════════════════
# MINIMAL WIKI — 5 pages, 2 sources, 10 wikilinks
# ══════════════════════════════════════════════════════════════════════════
def build_minimal():
    """Build the minimal fixture wiki."""
    root = FIXTURES / "wikis" / "minimal"
    if root.exists():
        shutil.rmtree(root)

    # Scaffold first
    import subprocess
    subprocess.run([
        sys.executable, str(REPO / "skill" / "scripts" / "scaffold.py"),
        str(root), "Minimal Test Wiki", "--template", "codebase", "--force",
    ], capture_output=True)

    pages = root / "wiki"

    # Entity pages
    write_page(pages / "entities" / "python.md", "Python", "entity",
        """# Python

Python is a high-level programming language.

## Related
- [[PyTorch]] is a deep learning framework built on Python.
- [[TensorFlow]] also uses Python as its primary interface.
- See [[Transfer Learning]] for an important ML concept.
""", tags=["programming", "language"], sources=["python-org"])

    write_page(pages / "entities" / "pytorch.md", "PyTorch", "entity",
        """# PyTorch

PyTorch is a deep learning framework by Meta.

## Related
- Built on [[Python]].
- Competes with [[TensorFlow]].
- Frequently used for [[Transfer Learning]].
""", tags=["deep-learning", "framework"], sources=["pytorch-docs"])

    write_page(pages / "entities" / "tensorflow.md", "TensorFlow", "entity",
        """# TensorFlow

TensorFlow is a deep learning framework by Google.

## Related
- Uses [[Python]] for its API.
- Competes with [[PyTorch]].
""", tags=["deep-learning", "framework"], sources=["tf-docs"])

    # Concept pages
    write_page(pages / "concepts" / "transfer_learning.md", "Transfer Learning", "concept",
        """# Transfer Learning

Transfer learning is reusing a pre-trained model on a new task.

## Frameworks
- [[PyTorch]] provides extensive transfer learning support.
- [[TensorFlow]] also has transfer learning capabilities.

## Related Concepts
- [[Fine Tuning]] is a form of transfer learning.
""", tags=["ml", "technique"], sources=["ml-textbook"])

    write_page(pages / "concepts" / "fine_tuning.md", "Fine Tuning", "concept",
        """# Fine Tuning

Fine-tuning adjusts pre-trained model weights for a specific dataset.

## Relationship
- Fine-tuning is a specific technique within [[Transfer Learning]].
- Both [[PyTorch]] and [[TensorFlow]] support fine-tuning.
""", tags=["ml", "technique"], sources=["ml-textbook"])

    # Update index
    index = pages / "index.md"
    index.write_text(index.read_text() + """
## Entities
- [[entities/python|Python]]
- [[entities/pytorch|PyTorch]]
- [[entities/tensorflow|TensorFlow]]

## Concepts
- [[concepts/transfer_learning|Transfer Learning]]
- [[concepts/fine_tuning|Fine Tuning]]
""")

    # Sources
    write_source(root / "raw" / "articles" / "python-org.md",
        "# Python.org\nPython official documentation overview.")
    write_source(root / "raw" / "articles" / "pytorch-docs.md",
        "# PyTorch Documentation\nOfficial PyTorch documentation and tutorials.")

    print(f"  Minimal wiki built: {root}")


# ══════════════════════════════════════════════════════════════════════════
# STALE WIKI — Pages with deliberate issues
# ══════════════════════════════════════════════════════════════════════════
def build_stale():
    """Build the stale fixture wiki with deliberate issues."""
    root = FIXTURES / "wikis" / "stale"
    if root.exists():
        shutil.rmtree(root)

    import subprocess
    subprocess.run([
        sys.executable, str(REPO / "skill" / "scripts" / "scaffold.py"),
        str(root), "Stale Test Wiki", "--template", "codebase", "--force",
    ], capture_output=True)

    pages = root / "wiki"

    # Good pages
    write_page(pages / "entities" / "active_project.md", "Active Project", "entity",
        """# Active Project

## Links
- Related to [[Active Concept]].
- See also [[Maintained Page]].
""", tags=["project"], updated="2026-07-01")

    write_page(pages / "concepts" / "active_concept.md", "Active Concept", "concept",
        """# Active Concept

## Links
- Used in [[Active Project]].
- Connects to [[Maintained Page]].
""", tags=["concept"], updated="2026-07-01")

    write_page(pages / "concepts" / "maintained_page.md", "Maintained Page", "concept",
        """# Maintained Page

Regularly updated with new content.
""", tags=["concept"], updated="2026-06-20")

    # Stale page (>90 days old)
    write_page(pages / "entities" / "stale_entity.md", "Stale Entity", "entity",
        """# Stale Entity

This page has not been updated in over 90 days.

## Links
- [[Active Concept]]
""", tags=["entity"], updated="2025-01-01")

    # Page with dead wikilinks
    write_page(pages / "concepts" / "dead_link_page.md", "Dead Link Page", "concept",
        """# Dead Link Page

This page contains broken wikilinks.

## Dead Links
- [[Non Existent Page]] does not exist.
- [[Also Missing]] is also missing.
- [[Active Concept]] is valid.
""", tags=["concept"], updated="2026-06-15")

    # Orphan page (no inbound links)
    write_page(pages / "entities" / "orphan_entity.md", "Orphan Entity", "entity",
        """# Orphan Entity

## Overview
No other page links to this entity. It's completely isolated.
""", tags=["entity"], updated="2026-06-15")

    # Low confidence page
    write_page(pages / "concepts" / "low_confidence.md", "Low Confidence Concept", "concept",
        """# Low Confidence Concept

This page is marked low confidence.
""", tags=["concept"], confidence="low", updated="2026-06-15")

    # Large page (>200 lines)
    large_body = "# Large Page\n\n" + "\n".join(
        [f"## Section {i}\n\nContent for section {i}. " +
         "This section contains analytical content about the topic.\n" for i in range(1, 60)]
    )
    write_page(pages / "concepts" / "large_page.md", "Large Page", "concept",
        large_body, tags=["concept"], updated="2026-06-15")

    # Page with contradiction signals
    write_page(pages / "entities" / "contested_entity.md", "Contested Entity", "entity",
        """# Contested Entity

This entity has some contradiction signals.
""", tags=["entity"], extra_fm="contested: true", updated="2026-06-15")

    write_page(pages / "concepts" / "contradiction_page.md", "Contradiction Page", "concept",
        """# Contradiction Page

Has explicit contradictions.
""", tags=["concept"],
        extra_fm="contradictions:\n  - \"Claim A vs Claim B\"",
        updated="2026-06-15")

    # Source files for SHA256 drift detection
    raw_dir = root / "raw" / "sources"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Source that has drifted (write then modify)
    drift_source = raw_dir / "clean_source.md"
    drift_source.write_text("""---
title: Clean Source
type: source
sha256: PLACEHOLDER
---

# Clean Source

Original content for testing."""
    )
    # Compute SHA256 of body
    body = "".join(drift_source.read_text().split("---\n", 2)[-1:])
    computed_sha = hashlib.sha256(body.encode()).hexdigest()
    drift_source.write_text(f"""---
title: Clean Source
type: source
sha256: {computed_sha}
---

# Clean Source

Original content for testing.""")

    # Source that has NOT drifted
    clean_source = raw_dir / "dirty_source.md"
    clean_content = """---
title: Dirty Source
type: source
sha256: WRONG_HASH
---

# Dirty Source

This content was modified after the hash was recorded."""
    clean_source.write_text(clean_content)

    # Audit reviews
    audit_dir = root / "audit"
    write_review(audit_dir, "rev-001", "wiki/entities/stale_entity.md",
                 "suggestion", "Update Stale Entity",
                 "This entity page needs updating — last modified in 2025.")

    # Log file
    write_log(root / "log", "20260615", [
        "## [14:30] ingest | test-source\n- Pages created: 3, reviews: 1",
        "## [15:00] link-suggest | auto\n- Suggested 5 links",
    ])

    # Update index
    index = pages / "index.md"
    index.write_text(index.read_text() + """
## Entities
- [[entities/active_project|Active Project]]
- [[entities/stale_entity|Stale Entity]]
- [[entities/orphan_entity|Orphan Entity]]
- [[entities/contested_entity|Contested Entity]]

## Concepts
- [[concepts/active_concept|Active Concept]]
- [[concepts/maintained_page|Maintained Page]]
- [[concepts/dead_link_page|Dead Link Page]]
- [[concepts/low_confidence|Low Confidence Concept]]
- [[concepts/large_page|Large Page]]
- [[concepts/contradiction_page|Contradiction Page]]
""")

    print(f"  Stale wiki built: {root}")


# ══════════════════════════════════════════════════════════════════════════
# POPULATED WIKI — 50+ pages, 100+ wikilinks, complex graph
# ══════════════════════════════════════════════════════════════════════════
def build_populated():
    """Build the populated fixture wiki with 50+ pages."""
    root = FIXTURES / "wikis" / "populated"
    if root.exists():
        shutil.rmtree(root)

    import subprocess
    subprocess.run([
        sys.executable, str(REPO / "skill" / "scripts" / "scaffold.py"),
        str(root), "Populated Test Wiki", "--template", "codebase", "--force",
    ], capture_output=True)

    pages = root / "wiki"

    pages_config = {
        # ML Framework entities
        "entities/pytorch": ("PyTorch", "entity",
            ["deep-learning", "framework", "meta"],
            "# PyTorch\nDeep learning framework by Meta.\n\nRelated: [[TensorFlow]], [[JAX]], [[Python]], [[CUDA]]"),
        "entities/tensorflow": ("TensorFlow", "entity",
            ["deep-learning", "framework", "google"],
            "# TensorFlow\nDeep learning framework by Google.\n\nRelated: [[PyTorch]], [[Keras]], [[TPU]], [[Python]]"),
        "entities/jax": ("JAX", "entity",
            ["deep-learning", "framework", "google"],
            "# JAX\nHigh-performance numerical computing.\n\nRelated: [[TensorFlow]], [[NumPy]], [[XLA]]"),
        "entities/keras": ("Keras", "entity",
            ["deep-learning", "api"],
            "# Keras\nHigh-level neural networks API.\n\nRelated: [[TensorFlow]], [[PyTorch]], [[JAX]]"),
        "entities/python": ("Python", "entity",
            ["programming", "language"],
            "# Python\nGeneral-purpose programming language.\n\nRelated: [[PyTorch]], [[TensorFlow]], [[NumPy]]"),
        "entities/numpy": ("NumPy", "entity",
            ["python", "library", "numerical"],
            "# NumPy\nFundamental package for scientific computing.\n\nRelated: [[Python]], [[JAX]], [[SciPy]]"),
        "entities/cuda": ("CUDA", "entity",
            ["nvidia", "gpu", "parallel"],
            "# CUDA\nParallel computing platform by NVIDIA.\n\nRelated: [[PyTorch]], [[TensorFlow]], [[GPU]]"),
        "entities/tpu": ("TPU", "entity",
            ["google", "hardware", "accelerator"],
            "# TPU\nTensor Processing Unit by Google.\n\nRelated: [[TensorFlow]], [[JAX]], [[GPU]]"),
        "entities/gpu": ("GPU", "entity",
            ["hardware", "computing"],
            "# GPU\nGraphics Processing Unit.\n\nRelated: [[CUDA]], [[TPU]], [[Deep Learning]]"),

        # ML Concepts
        "concepts/transfer_learning": ("Transfer Learning", "concept",
            ["ml", "technique"],
            "# Transfer Learning\nReusing pre-trained models.\n\nRelated: [[Fine Tuning]], [[PyTorch]], [[TensorFlow]], [[Pre-training]]"),
        "concepts/fine_tuning": ("Fine Tuning", "concept",
            ["ml", "technique"],
            "# Fine Tuning\nAdjusting pre-trained weights.\n\nRelated: [[Transfer Learning]], [[LoRA]], [[Hyperparameters]]"),
        "concepts/deep_learning": ("Deep Learning", "concept",
            ["ml", "ai"],
            "# Deep Learning\nSubset of machine learning.\n\nRelated: [[Neural Network]], [[PyTorch]], [[TensorFlow]], [[GPU]]"),
        "concepts/neural_network": ("Neural Network", "concept",
            ["ml", "architecture"],
            "# Neural Network\nComputing system inspired by biological brains.\n\nRelated: [[Deep Learning]], [[CNN]], [[Transformer]], [[Backpropagation]]"),
        "concepts/cnn": ("Convolutional Neural Network", "concept",
            ["ml", "architecture", "vision"],
            "# CNN\nConvolutional Neural Network.\nRelated: [[Neural Network]], [[ResNet]], [[Computer Vision]]"),
        "concepts/transformer": ("Transformer Architecture", "concept",
            ["ml", "architecture", "attention"],
            "# Transformer\nAttention-based architecture.\n\nRelated: [[Attention Mechanism]], [[BERT]], [[GPT]], [[Neural Network]]"),
        "concepts/attention_mechanism": ("Attention Mechanism", "concept",
            ["ml", "attention"],
            "# Attention\nMechanism to focus on relevant input.\n\nRelated: [[Transformer]], [[Self-Attention]], [[Multi-Head Attention]]"),
        "concepts/lora": ("LoRA", "concept",
            ["ml", "fine-tuning", "efficient"],
            "# LoRA\nLow-Rank Adaptation for efficient fine-tuning.\n\nRelated: [[Fine Tuning]], [[QLoRA]], [[PEFT]]"),
        "concepts/pre_training": ("Pre-training", "concept",
            ["ml", "training"],
            "# Pre-training\nInitial training on large datasets.\n\nRelated: [[Transfer Learning]], [[Fine Tuning]], [[BERT]]"),
        "concepts/backpropagation": ("Backpropagation", "concept",
            ["ml", "optimization"],
            "# Backpropagation\nAlgorithm for training neural networks.\n\nRelated: [[Neural Network]], [[Gradient Descent]], [[Loss Function]]"),
        "concepts/gradient_descent": ("Gradient Descent", "concept",
            ["ml", "optimization"],
            "# Gradient Descent\nOptimization algorithm.\n\nRelated: [[Backpropagation]], [[SGD]], [[Adam Optimizer]], [[Loss Function]]"),

        # Research papers
        "entities/attention_is_all_you_need": ("Attention Is All You Need", "entity",
            ["paper", "transformer", "2017"],
            "# Attention Is All You Need\nSeminal paper by Vaswani et al. (2017).\n\nRelated: [[Transformer]], [[Attention Mechanism]], [[Vaswani]]"),
        "entities/vaswani": ("Vaswani et al.", "entity",
            ["author", "researcher"],
            "# Vaswani et al.\nAuthors of the Transformer paper.\n\nRelated: [[Attention Is All You Need]], [[Transformer]]"),
        "entities/resnet_paper": ("Deep Residual Learning", "entity",
            ["paper", "cnn", "2015"],
            "# Deep Residual Learning\nResNet paper by He et al. (2015).\n\nRelated: [[CNN]], [[ResNet]], [[Computer Vision]]"),
        "entities/bert_paper": ("BERT", "entity",
            ["paper", "transformer", "nlp"],
            "# BERT\nPre-training of Deep Bidirectional Transformers.\n\nRelated: [[Transformer]], [[GPT]], [[NLP]], [[Pre-training]]"),

        # NLP
        "concepts/nlp": ("Natural Language Processing", "concept",
            ["ai", "language"],
            "# NLP\nAI subfield for language tasks.\n\nRelated: [[BERT]], [[GPT]], [[Transformer]], [[Tokenization]]"),
        "entities/gpt": ("GPT", "entity",
            ["nlp", "transformer", "openai"],
            "# GPT\nGenerative Pre-trained Transformer.\n\nRelated: [[Transformer]], [[BERT]], [[NLP]], [[LLM]]"),
        "concepts/llm": ("Large Language Model", "concept",
            ["ai", "nlp"],
            "# LLM\nLarge Language Models.\n\nRelated: [[GPT]], [[BERT]], [[Transformer]], [[Prompt Engineering]]"),
        "concepts/prompt_engineering": ("Prompt Engineering", "concept",
            ["nlp", "technique"],
            "# Prompt Engineering\nCrafting effective prompts for LLMs.\n\nRelated: [[LLM]], [[GPT]], [[Few-Shot Learning]]"),
        "concepts/tokenization": ("Tokenization", "concept",
            ["nlp", "preprocessing"],
            "# Tokenization\nSplitting text into tokens.\n\nRelated: [[NLP]], [[BPE]], [[WordPiece]]"),
    }

    # Write all pages
    for slug, (title, ptype, tags, body) in pages_config.items():
        write_page(pages / f"{slug}.md", title, ptype, body, tags=tags,
                   sources=["populated-fixture"], updated="2026-06-20")

    # Additional pages to hit 50+
    for i in range(1, 25):
        slug = f"concepts/topic_{i:02d}"
        title = f"Topic {i:02d}"
        body = f"# {title}\n\nAuxiliary topic {i} for the populated test wiki.\n\nRelated: [[Deep Learning]], [[Python]]"
        write_page(pages / f"{slug}.md", title, "concept", body,
                   tags=["test", "auxiliary"], sources=["populated-fixture"])

    # Source files (3+)
    write_source(root / "raw" / "articles" / "ml-survey.md",
        "# Machine Learning Survey\n\nComprehensive survey of ML techniques.\n" * 500)
    write_source(root / "raw" / "articles" / "transformer-paper-notes.md",
        "# Transformer Paper Notes\n\nNotes on Attention Is All You Need.\n" * 200)
    write_source(root / "raw" / "articles" / "framework-comparison.md",
        "# Framework Comparison\n\nComparing PyTorch, TensorFlow, and JAX.\n" * 300)

    # Update index with all pages
    index_entries = []
    for slug in sorted(pages_config.keys()):
        name = pages_config[slug][0]
        index_entries.append(f"- [[{slug}|{name}]]")
    for i in range(1, 25):
        index_entries.append(f"- [[concepts/topic_{i:02d}|Topic {i:02d}]]")

    index = pages / "index.md"
    index.write_text(index.read_text() + "\n" + "\n".join(index_entries))

    print(f"  Populated wiki built: {root}")
    print(f"    Pages: {len(pages_config) + 24}")


# ══════════════════════════════════════════════════════════════════════════
# SOURCE FILES
# ══════════════════════════════════════════════════════════════════════════
def build_sources():
    """Create sample source files for testing."""
    src_dir = FIXTURES / "sources"

    # Short source (< CHUNK_SIZE)
    short_content = """# Short Test Source

## Introduction
This is a short source document for testing single-chunk ingest.

## Key Topics
- Python programming language
- Machine learning frameworks
- Data science tools

## Details
Python is widely used in data science and machine learning.
Popular frameworks include PyTorch, TensorFlow, and JAX.

## Conclusion
This short document demonstrates basic ingest functionality.
"""
    (src_dir / "short.md").write_text(short_content)

    # Long source (> CHUNK_SIZE = 55,000)
    long_content = "# Long Test Source Document\n\n## Introduction\nThis document exceeds the CHUNK_SIZE threshold.\n\n"
    paragraph = ("The field of artificial intelligence and machine learning has grown "
                 "exponentially over the past decade. Researchers have developed numerous "
                 "architectures, algorithms, and frameworks to tackle increasingly complex "
                 "problems. From computer vision to natural language processing, AI systems "
                 "are now capable of performing tasks that were once thought impossible. ")
    # Generate ~60K chars
    long_content += paragraph * 1200
    long_content += "\n\n## Final Section\nThis is the end of a long document.\n"
    (src_dir / "long.md").write_text(long_content)

    # Malformed source
    malformed_content = """---
broken_frontmatter: [missing closing bracket
no_type_field: true
---

# Malformed Source

## Empty Section
###

## Special Characters
Unicode: 😀 🚀 ñ é ç
Math: f(x) = ∑ᵢ₌₁ⁿ xᵢ²
SQL injection: '; DROP TABLE pages; --

## Very Long Line
""" + "x" * 5000 + """

## End
"""
    (src_dir / "malformed.md").write_text(malformed_content)

    print(f"  Source files created in {src_dir}")
    print(f"    short.md: {len(short_content)} chars")
    print(f"    long.md: {len(long_content)} chars (exceeds CHUNK_SIZE={55000})")
    print(f"    malformed.md: created")


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Building fixture wikis...")
    build_minimal()
    build_stale()
    build_populated()
    build_sources()
    print("\nDone.")
