#!/usr/bin/env python3
"""Test ingest.py FILE/REVIEW block parsing via LLM_WIKI_RESPONSE_FILE."""
import os, re, sys, subprocess
from pathlib import Path

WIKI_ROOT = "/tmp/test-ingest-blocks"
SKILL_DIR = Path(__file__).resolve().parent
SCAFFOLD = SKILL_DIR / "scaffold.py"
INGEST = SKILL_DIR / "ingest.py"


def parse_fm(text):
    """Parse frontmatter from wiki page content.
    Files written by ingest.py have format:
      key: value
      ...
      ---
      # body...
    (no opening ---, since FILE_RE consumes it).
    """
    m = re.match(r"^(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    return {line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
            for line in m.group(1).splitlines() if ":" in line and not line.strip().startswith("#")}


def run_python(script, *args, **kwargs):
    env = kwargs.pop("env", os.environ.copy())
    for py in ["python3", "python"]:
        cmd = [py, str(script)] + list(args)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=90, env=env, **kwargs)
        except FileNotFoundError:
            continue
        if r.returncode != 127:
            return r
    print("FATAL: neither python3 nor python found")
    sys.exit(1)


def ok(msg):
    print(f"\u2713 {msg}")


def fail(msg):
    print(f"\u2717 FAIL: {msg}")
    return 1


def main():
    errors = 0

    # Step 1: Scaffold
    if os.path.exists(WIKI_ROOT):
        subprocess.run(["rm", "-rf", WIKI_ROOT], capture_output=True)
    r = run_python(SCAFFOLD, WIKI_ROOT, "Test Ingest Blocks", "--force")
    if r.returncode != 0:
        errors += fail(f"Scaffold failed: {r.stderr.strip()[:200]}")
        return 1
    ok("Scaffold created")

    # Step 2: Create source document
    source_path = os.path.join(WIKI_ROOT, "raw", "articles", "test-source.md")
    source_content = """# Attention Mechanisms in Deep Learning: A Comprehensive Survey

## Introduction
Attention mechanisms have become a fundamental component of deep learning architectures,
enabling models to dynamically focus on relevant parts of the input. Originally introduced
for machine translation, attention has since been applied across NLP, computer vision,
and multimodal learning.

## Types of Attention
- **Scaled Dot-Product Attention**: The most widely used form, computing attention
  scores as softmax(QK^T / sqrt(d_k)).
- **Additive Attention**: Uses a feed-forward network to compute compatibility scores.
- **Multi-Head Attention**: Runs multiple attention heads in parallel, allowing the
  model to attend to information from different representation subspaces.

## Transformer Architecture
The Transformer (Vaswani et al., 2017) is the first architecture relying entirely on
self-attention. It consists of an encoder stack and a decoder stack, each containing
multi-head attention and feed-forward layers. Positional encodings are added to retain
sequence order information.

## Applications
- **Neural Machine Translation**: Attention allows the decoder to align with source words.
- **Vision Transformers**: Applying transformer architectures directly to image patches.
- **Large Language Models**: GPT, BERT, and their variants all use attention as core.

## Conclusion
Attention mechanisms have revolutionized deep learning. Understanding their variants
and trade-offs is essential for modern practitioners.
"""
    with open(source_path, "w") as f:
        f.write(source_content)
    ok("Source document created")

    # Step 3: Create mock LLM response
    mock_response = """---FILE: wiki/concepts/attention_mechanism.md
---
title: Attention Mechanism
type: concept
created: 2026-01-15
updated: 2026-01-15
sources: [test-source]
tags: [deep-learning, transformers, nlp]
---

# Attention Mechanism

## Overview
Attention mechanisms allow models to focus on relevant parts of the input sequence,
assigning different weights to different elements. They have become a cornerstone of
modern deep learning.

## Types
- **Scaled Dot-Product Attention**: Computes attention scores as softmax(QK^T / sqrt(d_k)).
  This is the standard in transformer architectures.
- **Additive Attention**: Uses a feed-forward network for score computation.
  Historically important but less efficient.
- **Multi-Head Attention**: Runs multiple attention heads in parallel, each potentially
  learning different relationship types.

## Key Properties
- Permutation invariant (without positional encodings)
- O(n^2) complexity in sequence length
- Highly parallelizable
---FILE: wiki/entities/transformer.md
---
title: Transformer
type: entity
created: 2026-01-15
updated: 2026-01-15
sources: [test-source]
tags: [architecture, neural-network]
---

# Transformer
The Transformer architecture was introduced by Vaswani et al. in the seminal paper
"Attention Is All You Need" (2017). It dispenses with recurrence and convolutions
entirely, relying solely on attention mechanisms.

## Architecture
- Encoder-decoder structure with 6 layers each
- Each layer: multi-head self-attention + position-wise feed-forward
- Residual connections and layer normalization around each sub-layer
- Positional encodings using sine and cosine functions

## Significance
The Transformer enabled parallel training (unlike RNNs) and became the foundation
for BERT, GPT, and virtually all modern language models.
---REVIEW: contradiction
---
target: wiki/concepts/attention_mechanism.md
title: Scaled Dot-Product vs Additive Attention
description: The source mentions both scaled dot-product and additive attention but does not clarify which variant is standard in modern transformer implementations. The literature consistently uses scaled dot-product attention in the Transformer.
---
---REVIEW: missing-page
---
target: wiki/entities/positional_encoding.md
title: Positional Encoding
description: The transformer page references positional encodings but no dedicated page exists for this concept. A page should be created.
---
---REVIEW: suggestion
---
target: wiki/concepts/attention_mechanism.md
title: Add Comparison with RNNs
description: Consider adding a section comparing attention-based models to traditional RNN/LSTM approaches to highlight the architectural advantages.
---
"""
    mock_path = os.path.join(WIKI_ROOT, "mock_response.md")
    with open(mock_path, "w") as f:
        f.write(mock_response)
    ok("Mock response file created")

    # Step 4: Run ingest
    env = os.environ.copy()
    env["LLM_WIKI_RESPONSE_FILE"] = mock_path
    r = run_python(INGEST, WIKI_ROOT, source_path, env=env)
    if r.returncode != 0:
        stderr_snip = r.stderr.strip()[:300] if r.stderr else "(no stderr)"
        errors += fail(f"Ingest failed (code {r.returncode}): {stderr_snip}")
        # still try verification
    else:
        ok("Ingest completed successfully")

    # Step 5: Verify output
    expected_pages = [
        "wiki/concepts/attention_mechanism.md",
        "wiki/entities/transformer.md",
    ]

    for p in expected_pages:
        full_path = os.path.join(WIKI_ROOT, p)
        if os.path.exists(full_path):
            ok(f"Wiki page exists: {p}")
        else:
            errors += fail(f"Wiki page missing: {p}")
            continue
        content = open(full_path).read()
        fm = parse_fm(content)
        required = ["title", "type", "created", "sources", "tags"]
        missing = [k for k in required if k not in fm]
        if not missing:
            ok(f"Wiki page frontmatter valid: has {', '.join(required)}")
        else:
            errors += fail(f"Wiki page frontmatter missing keys in {p}: {missing}")

    # Verify review items
    audit_dir = os.path.join(WIKI_ROOT, "audit")
    review_files = sorted(
        f for f in os.listdir(audit_dir)
        if f != ".gitkeep" and os.path.isfile(os.path.join(audit_dir, f))
    )
    if len(review_files) == 3:
        ok(f"Review items created in audit/ ({len(review_files)} total)")
        for rf in review_files:
            content = open(os.path.join(audit_dir, rf)).read()
            if all(k in content for k in ("target:", "type:", "status:", "source_slug:")):
                ok(f"  audit/{rf} — valid review structure")
            else:
                errors += fail(f"  audit/{rf} — missing required fields")
    else:
        errors += fail(f"Expected 3 review items in audit/, found {len(review_files)}: {review_files}")

    # Verify log entry
    log_dir = os.path.join(WIKI_ROOT, "log")
    log_files = sorted(f for f in os.listdir(log_dir) if f.endswith(".md"))
    if log_files:
        log_content = open(os.path.join(log_dir, log_files[-1])).read()
        if "ingest" in log_content and "test-source" in log_content:
            ok(f"Log entry created: log/{log_files[-1]}")
        else:
            errors += fail(f"Log entry missing ingest details: log/{log_files[-1]}")
    else:
        errors += fail("No log entry found")

    # Verify index updated
    index_path = os.path.join(WIKI_ROOT, "wiki", "index.md")
    if os.path.exists(index_path):
        index_content = open(index_path).read()
        if "attention_mechanism" in index_content:
            ok("wiki/index.md updated with new page entries")
        else:
            errors += fail("wiki/index.md not updated with new pages")
    else:
        errors += fail("wiki/index.md not found")

    # Step 6: Clean up
    if os.path.exists(WIKI_ROOT):
        subprocess.run(["rm", "-rf", WIKI_ROOT], capture_output=True)
        ok("Cleaned up /tmp/test-ingest-blocks")

    # Summary
    if errors:
        print(f"\n{'=' * 40}")
        print(f"Result: {errors} test(s) FAILED")
        print(f"{'=' * 40}")
    else:
        print(f"\n{'=' * 40}")
        print("Result: ALL TESTS PASSED")
        print(f"{'=' * 40}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
