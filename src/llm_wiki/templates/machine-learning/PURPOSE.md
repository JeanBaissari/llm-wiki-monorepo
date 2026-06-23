# Machine Learning Wiki — Purpose

This template scaffolds a wiki for tracking ML models, datasets,
experiments, and benchmarks.

**What it is for:**

- Maintaining a model registry with architecture details, training data,
  and performance metrics for every model you build or evaluate.
- Documenting datasets — provenance, schema, preprocessing, and biases.
- Recording experiments systematically so that every hyperparameter
  sweep, ablation, and run is traceable.
- Tracking benchmark results to compare model performance across
  standardised tasks.

**What it is NOT for:**

- Experiment tracking and metric logging in real time — use dedicated
  MLOps tools (MLflow, Weights & Biases, TensorBoard) during active
  development. This wiki is for curated, durable records.
- Model deployment manifests or serving configuration — use your
  deployment platform (Kubernetes, Sagemaker, BentoML) for that.
- Data versioning or blob storage — use DVC, Git LFS, or S3.

**Key extensibility pattern:** Each experiment links to the model,
dataset, and benchmark it relates to. Model pages aggregate best
experiment results and link to benchmark comparisons.
