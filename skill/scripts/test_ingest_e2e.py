#!/usr/bin/env python3
"""test_ingest_e2e.py — Multi-step agent loop integration test for ingest.py.

Runs ingest.py in 2 passes using LLM_WIKI_RESPONSE_FILE, simulating
what a real agent/LLM would produce at each stage — no API keys needed.

Usage:
    python3 skill/scripts/test_ingest_e2e.py
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent.parent
INGEST_SCRIPT = REPO_DIR / "skill" / "scripts" / "ingest.py"
SCAFFOLD_SCRIPT = REPO_DIR / "skill" / "scripts" / "scaffold.py"

WORKSPACE = Path("/tmp/test-ingest-e2e")
STAGE1_RESPONSE_FILE = WORKSPACE / "stage1_response.txt"
STAGE2_RESPONSE_FILE = WORKSPACE / "stage2_response.txt"
SOURCE_FILE = WORKSPACE / "raw" / "articles" / "attention-is-all-you-need.md"
CACHE_DIR = WORKSPACE / "raw" / ".cache"

PASS = 0
FAIL = 0

def check(description: str, condition: bool):
    global PASS, FAIL
    if condition:
        print(f"  \u2713 {description}")
        PASS += 1
    else:
        print(f"  \u2717 {description}")
        FAIL += 1

def run_python(script: str, *args, env=None):
    cmd = [sys.executable, script] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    return result.returncode, result.stdout, result.stderr

def sha256_file(path: str) -> str:
    return hashlib.sha256(Path(path).read_text(encoding="utf-8").encode()).hexdigest()

def main() -> int:
    global PASS, FAIL

    # ── Setup ──────────────────────────────────────────────────────────
    if WORKSPACE.exists():
        import shutil
        shutil.rmtree(WORKSPACE)

    print("=== Setup ===")
    rc, _, stderr = run_python(str(SCAFFOLD_SCRIPT), str(WORKSPACE), "Ingest E2E Test", "--template", "research", "--force")
    check(f"Scaffold wiki (exit {rc})", rc == 0)

    # ── Create source document ─────────────────────────────────────────
    os.makedirs(str(SOURCE_FILE.parent), exist_ok=True)
    source_text = """# Attention Is All You Need

## Abstract
The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.

## Key Contributions
1. Transformer architecture: purely attention-based
2. Multi-Head Attention: allows the model to jointly attend to information from different representation subspaces
3. Position-wise Feed-Forward Networks
4. Positional Encoding: necessary since the model has no recurrence

## Architecture
The Transformer follows an encoder-decoder structure using stacked self-attention and point-wise, fully connected layers.

### Encoder
The encoder is composed of a stack of N=6 identical layers. Each layer has two sub-layers: a multi-head self-attention mechanism, and a position-wise fully connected feed-forward network.

### Decoder
The decoder is also composed of a stack of N=6 identical layers. In addition to the two sub-layers in each encoder layer, the decoder inserts a third sub-layer, which performs multi-head attention over the output of the encoder stack.

## Attention Mechanism
An attention function can be described as mapping a query and a set of key-value pairs to an output, where the query, keys, values, and output are all vectors. The output is computed as a weighted sum of the values, where the weight assigned to each value is computed by a compatibility function of the query with the corresponding key.

### Scaled Dot-Product Attention
We call our particular attention "Scaled Dot-Product Attention". The input consists of queries and keys of dimension dk, and values of dimension dv. We compute the dot products of the query with all keys, divide each by sqrt(dk), and apply a softmax function to obtain the weights on the values.

### Multi-Head Attention
Instead of performing a single attention function, we found it beneficial to linearly project the queries, keys and values h times with different, learned linear projections to dk, dk and dv dimensions, respectively.

## Results
The Transformer achieves 28.4 BLEU on the WMT 2014 English-to-German translation task, improving over the previous best results by over 2 BLEU.
"""
    SOURCE_FILE.write_text(source_text, encoding="utf-8")
    source_sha = sha256_file(str(SOURCE_FILE))
    check("Source document created", SOURCE_FILE.exists())

    # ── Generate Stage 1 response (agent acts as LLM) ─────────────────
    # This simulates what an LLM would produce after reading the source.
    stage1_analysis = """## Entity Extraction
- Transformer: Neural network architecture based solely on attention mechanisms
- Multi-Head Attention: Parallel attention computation across representation subspaces
- Scaled Dot-Product Attention: Attention mechanism using dot products scaled by sqrt(dk)
- Positional Encoding: Method to inject sequence position information
- Encoder: Stack of N=6 identical layers with self-attention and FFN
- Decoder: Stack of N=6 identical layers with self-attention, cross-attention, and FFN
- BLEU: Translation quality metric (28.4 achieved on WMT 2014 En-De)

## Concept Extraction
- Attention Mechanism: Mapping queries and key-value pairs to weighted outputs
- Self-Attention: Attention within the same sequence
- Cross-Attention: Attention between encoder and decoder
- Position-wise Feed-Forward Networks: FFN applied to each position separately
- Sequence Transduction: Converting one sequence to another

## Key Claims
- Transformer outperforms recurrent and convolutional models on translation
- Attention alone is sufficient for sequence transduction
- Multi-head attention allows joint attention to different representation subspaces
- Scaled dot-product attention is more efficient than additive attention

## Relationships
- Transformer uses Multi-Head Attention which uses Scaled Dot-Product Attention
- Positional Encoding compensates for lack of recurrence
- Encoder feeds into Decoder via cross-attention
- Higher BLEU scores indicate better translation quality

## Contradictions
- The paper claims dispensing with recurrence entirely, yet positional encoding provides position information
- Trade-off between parallelization (good) and ability to model sequential order (needs positional encoding)
"""

    STAGE1_RESPONSE_FILE.write_text(stage1_analysis, encoding="utf-8")
    check("Stage 1 analysis written", STAGE1_RESPONSE_FILE.exists())

    # ── Pass 1: Run ingest with Stage 1 response ──────────────────────
    print("\n=== Pass 1: Stage 1 Analysis ===")
    env = {"LLM_WIKI_RESPONSE_FILE": str(STAGE1_RESPONSE_FILE)}
    rc, _, stderr = run_python(str(INGEST_SCRIPT), str(WORKSPACE), str(SOURCE_FILE), env=env)
    # Stage 1 reads the analysis and caches it. Stage 2 also reads the same
    # response (not FILE blocks) so nothing is written, but script exits 0.
    stage1_cached = "Cached analysis" in stderr or "Using cached analysis" in stderr
    check(f"Pass 1 exit code {rc}", rc == 0)
    check("Stage 1 analysis cached", stage1_cached)

    # Verify cache file exists
    cache_files = list(CACHE_DIR.glob("*.json"))
    check(f"Cache file created ({len(cache_files)})", len(cache_files) == 1)
    if cache_files:
        with open(cache_files[0]) as f:
            cached = json.load(f)
        check("Cache contains analysis", "analysis" in cached and len(cached["analysis"]) > 100)
        check("Cache contains source_hash", cached.get("source_hash") == source_sha)
        check("Cache has source_slug field", "source_slug" in cached)

    # ── Generate Stage 2 response (agent acts as LLM) ─────────────────
    stage2_response = """---FILE: wiki/concepts/transformer_architecture.md
---
title: Transformer Architecture
type: concept
created: 2026-06-22
updated: 2026-06-22
sources: [attention_is_all_you_need]
tags: [deep-learning, nlp, architecture, attention]
---

# Transformer Architecture

## Overview
The Transformer is a neural network architecture introduced in "Attention Is All You Need" (Vaswani et al., 2017). It is based solely on attention mechanisms, dispensing with recurrence and convolutions.

## Architecture
The Transformer follows an encoder-decoder structure:
- **Encoder**: Stack of N=6 identical layers, each with multi-head self-attention and feed-forward network
- **Decoder**: Stack of N=6 identical layers, with additional cross-attention over encoder output

## Key Components
- [[Multi-Head Attention]]
- [[Positional Encoding]]
- Position-wise Feed-Forward Networks

## Results
Achieved 28.4 BLEU on WMT 2014 English-to-German translation.
---FILE: wiki/entities/vaswani_2017.md
---
title: Vaswani et al. (2017)
type: entity
created: 2026-06-22
updated: 2026-06-22
sources: [attention_is_all_you_need]
tags: [authors, paper, transformer]
---

# Vaswani et al. (2017)

Authors of "Attention Is All You Need", the paper that introduced the [[Transformer Architecture]].

## Citation
Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention Is All You Need. *Advances in Neural Information Processing Systems*.
---FILE: wiki/concepts/multi_head_attention.md
---
title: Multi-Head Attention
type: concept
created: 2026-06-22
updated: 2026-06-22
sources: [attention_is_all_you_need]
tags: [attention, deep-learning, transformer]
---

# Multi-Head Attention

## Overview
Multi-Head Attention allows the model to jointly attend to information from different representation subspaces at different positions.

## Mechanism
Instead of performing a single attention function, queries, keys, and values are linearly projected *h* times with different learned projections. Attention is performed in parallel on each projection, and the results are concatenated.

## Relationship
Used within the [[Transformer Architecture]] as a core component.
---FILE: wiki/concepts/scaled_dot_product_attention.md
---
title: Scaled Dot-Product Attention
type: concept
created: 2026-06-22
updated: 2026-06-22
sources: [attention_is_all_you_need]
tags: [attention, deep-learning]
---

# Scaled Dot-Product Attention

## Overview
The specific attention mechanism used in the Transformer. Computes dot products of queries with keys, scales by sqrt(dk), and applies softmax.

## Formula
$$\\text{Attention}(Q, K, V) = \\text{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right)V$$

## Relation
This is the core attention function used in [[Multi-Head Attention]].
---FILE: wiki/concepts/positional_encoding.md
---
title: Positional Encoding
type: concept
created: 2026-06-22
updated: 2026-06-22
sources: [attention_is_all_you_need]
tags: [transformer, architecture, sequence-modeling]
---

# Positional Encoding

## Overview
Since the [[Transformer Architecture]] has no recurrence, positional encodings are added to give the model information about the relative or absolute position of tokens in the sequence.

## Method
Uses sine and cosine functions of different frequencies:
$$PE_{(pos,2i)} = \\sin(pos/10000^{2i/d_{\\text{model}}})$$
$$PE_{(pos,2i+1)} = \\cos(pos/10000^{2i/d_{\\text{model}}})$$
---REVIEW: missing-page
target: wiki/concepts/feed_forward_network.md
title: Feed-Forward Network
description: The Transformer uses position-wise feed-forward networks. Consider creating a dedicated page.
"""

    STAGE2_RESPONSE_FILE.write_text(stage2_response, encoding="utf-8")
    check("Stage 2 response written with FILE and REVIEW blocks", STAGE2_RESPONSE_FILE.exists())

    # ── Pass 2: Run ingest with Stage 2 response ──────────────────────
    print("\n=== Pass 2: Stage 2 Generation ===")
    env = {"LLM_WIKI_RESPONSE_FILE": str(STAGE2_RESPONSE_FILE)}
    rc, _, stderr = run_python(str(INGEST_SCRIPT), str(WORKSPACE), str(SOURCE_FILE), env=env)
    check(f"Pass 2 exit code {rc} (expected 0)", rc == 0)
    check("Stage 1 used cached analysis", "Using cached analysis" in stderr)

    # ── Verify output ──────────────────────────────────────────────────
    print("\n=== Verification ===")

    # Check wiki pages were created
    expected_pages = [
        "wiki/concepts/transformer_architecture.md",
        "wiki/entities/vaswani_2017.md",
        "wiki/concepts/multi_head_attention.md",
        "wiki/concepts/scaled_dot_product_attention.md",
        "wiki/concepts/positional_encoding.md",
    ]
    for page in expected_pages:
        path = WORKSPACE / page
        check(f"Page created: {page}", path.exists())
        if path.exists():
            text = path.read_text(encoding="utf-8")
            # FILE_RE in ingest.py consumes the opening --- delimiter,
            # so content starts with key: val directly.
            has_fm = bool(re.match(r"^[a-zA-Z_]+:", text, re.MULTILINE))
            has_closing = bool(re.search(r"\n---\n\s*#", text))
            has_title = "'title:' in text or text.startswith('title:') or ': \"' in text[:200]"
            check(f"  Page has frontmatter keys", has_fm)
            check(f"  Page has closing --- separator", has_closing)

    # Check review items were created in audit/
    audit_dir = WORKSPACE / "audit"
    audit_files = list(audit_dir.glob("*.md"))
    check(f"Review items created in audit/ ({len(audit_files)})", len(audit_files) >= 1)

    # Check log entry was created
    log_dir = WORKSPACE / "log"
    log_files = sorted(log_dir.glob("*.md"))
    check(f"Log entry created ({len(log_files)})", len(log_files) >= 1)
    if log_files:
        log_text = log_files[-1].read_text(encoding="utf-8")
        check("Log mentions ingest", "ingest" in log_text.lower())

    # Check index.md was updated
    index_path = WORKSPACE / "wiki" / "index.md"
    if index_path.exists():
        index_text = index_path.read_text(encoding="utf-8")
        check("Index updated with new page references", "transformer_architecture" in index_text)

    # Check page content is correct (frontmatter parsed correctly)
    transformer_page = WORKSPACE / "wiki/concepts/transformer_architecture.md"
    if transformer_page.exists():
        text = transformer_page.read_text(encoding="utf-8")
        check("Content mentions Transformer", "Transformer" in text)
        check("Content has wikilinks", "[[Multi-Head Attention]]" in text)

    # Check the page has correct frontmatter fields (format: key: val\n...\n---\n)
    pages_text = transformer_page.read_text(encoding="utf-8")
    # ingest.py FILE_RE consumes the opening ---, so content starts with key: val
    fm_match = re.match(r"^([a-zA-Z_].*?)\n---\n", pages_text, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        check("Frontmatter has title", 'title:' in fm_text)
        check("Frontmatter has type", 'type:' in fm_text)
        check("Frontmatter has sources", 'sources:' in fm_text)
        check("Frontmatter has tags", 'tags:' in fm_text)
        check("Frontmatter has created", 'created:' in fm_text)
        check("Frontmatter has updated", 'updated:' in fm_text)

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'='*50}")

    # Cleanup
    import shutil
    shutil.rmtree(WORKSPACE)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
