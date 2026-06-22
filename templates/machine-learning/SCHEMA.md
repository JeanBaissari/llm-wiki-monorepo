# Machine Learning Domain Schema

Extends the base schema with machine learning-specific page types,
directories, and frontmatter conventions.

## Extra Directories

| Directory | Purpose |
|-----------|---------|
| `wiki/models/` | Model architecture and configuration records |
| `wiki/datasets/` | Dataset documentation |
| `wiki/experiments/` | Experiment run records |
| `wiki/benchmarks/` | Benchmark comparison tables |

## Domain Page Types

| Type | Directory | Purpose | Frontmatter Fields |
|------|-----------|---------|--------------------|
| `model` | `wiki/models/` | An ML model architecture or trained instance | `architecture: string`, `parameters: int`, `training_dataset: []`, `task: string`, `metrics: { metric_name: value }` |
| `dataset` | `wiki/datasets/` | A dataset used for training or evaluation | `size: int`, `splits: { train: int, val: int, test: int }`, `features: []`, `task: string`, `license`, `source_url` |
| `experiment` | `wiki/experiments/` | A specific training run or hyperparameter sweep | `model: []`, `dataset: []`, `hyperparameters: {}`, `seed: int`, `metrics: { metric_name: value }`, `duration: string` |
| `benchmark` | `wiki/benchmarks/` | A standardised evaluation benchmark | `task: string`, `metrics: []`, `models: {}`, `source_url` |

## Naming Conventions

- **Models:** `architecture-name.md` (e.g., `resnet-50.md`, `llama-3.md`)
- **Datasets:** `dataset-name.md` (e.g., `imagenet.md`, `squad-v2.md`)
- **Experiments:** `model-dataset-YYYY-MM-DD.md` (e.g., `resnet50-imagenet-2024-06-01.md`)
- **Benchmarks:** `benchmark-name.md` (e.g., `glue.md`, `mmlu.md`)

## Frontmatter Template

```yaml
---
type: model | dataset | experiment | benchmark
title: Human-readable title
tags: []
related: []
sources: []
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

### Model-specific
```yaml
type: model
architecture: "Transformer"
parameters: 70000000000
training_dataset:
  - dataset-slug
task: "text-generation"
metrics:
  accuracy: 0.92
  f1: 0.89
```

### Dataset-specific
```yaml
type: dataset
size: 1000000
splits:
  train: 800000
  val: 100000
  test: 100000
features:
  - "text"
  - "label"
task: "text-classification"
license: "MIT"
source_url: "https://..."
```

### Experiment-specific
```yaml
type: experiment
model:
  - model-slug
dataset:
  - dataset-slug
hyperparameters:
  learning_rate: 3e-5
  batch_size: 32
  epochs: 10
seed: 42
metrics:
  accuracy: 0.94
  f1: 0.91
duration: "12h 34m"
```

### Benchmark-specific
```yaml
type: benchmark
task: "question-answering"
metrics:
  - "f1"
  - "exact_match"
models:
  model-a: { f1: 0.88, exact_match: 0.82 }
  model-b: { f1: 0.91, exact_match: 0.85 }
source_url: "https://..."
```

## Conventions

1. Every model page should document the architecture in sufficient
   detail to reproduce it, including layer counts, hidden sizes,
   activation functions, and normalisation.
2. Dataset pages should document preprocessing steps, train/val/test
   splits, label distributions, and known biases.
3. Experiment pages should document GPU hours, framework versions, and
   any deviation from the standard training recipe.
4. Benchmark pages should standardise metric names across models being
   compared and note the date of evaluation.
5. When a model's weights are updated (finetuning, quantisation, etc.),
   create a new experiment page rather than overwriting.
