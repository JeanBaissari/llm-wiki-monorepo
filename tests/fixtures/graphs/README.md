# Graph Topology Fixtures — Community Detection Verification

This directory contains 7 synthetic graph topologies for cross-implementation
verification of community detection (Louvain) between TypeScript and Python paths.

## Topologies

| File | Name | Nodes | Edges | Expected Communities | Purpose |
|------|------|-------|-------|---------------------|---------|
| `two_clique.json` | Two-clique | 20 | 90+90=180 | 2 | Clear split test |
| `star.json` | Star | 21 | 20 | 1 | Louvain merges center+leaves |
| `barbell.json` | Barbell | 16 | 56+56+1=113 | 2 | Weak bridge between clusters |
| `ring_of_cliques.json` | Ring-of-cliques | 20 | 6×5+5=35 | 5† | Ring structure test |
| `sbm.json` | SBM (3 blocks) | 30 | ~350 | 3†† | Noisy planted partition |
| `random.json` | Erdos-Renyi | 30 | ~90 | 1 | No structure — agreement only |
| `empty.json` | Empty | 10 | 0 | 10 | Edge case: isolated nodes |

† May vary with resolution parameter (resolution=1 may merge adjacent cliques)
†† Noisy — planted structure may not be fully recovered by Louvain

## Format

Each file follows this JSON schema:

```json
{
  "name": "graph_name",
  "description": "Human-readable description",
  "expected_communities": null | int,
  "nodes": ["node_id_0", "node_id_1", ...],
  "edges": [
    {"source": "a", "target": "b", "weight": 1},
    ...
  ]
}
```

- `nodes`: Ordered list of node IDs
- `edges`: Weighted undirected edges
- `expected_communities`: Expected number of communities (null = noisy/unpredictable)

## Seeds Used

Verification runs use 5 seeds: `[42, 123, 456, 789, 0]`

## Thresholds

| Metric | Threshold | Notes |
|--------|-----------|-------|
| NMI | > 0.95 | Cross-implementation agreement |
| ARI | > 0.95 | Cross-implementation agreement |
| ΔQ / max(Q) | < 0.01 | Modularity tolerance (1%) |
| Within-impl NMI | = 1.0 | Determinism (same seed) |
| Within-impl NMI | > 0.90 | Stability (different seeds) |

## Usage

```bash
# Run verification suite
python3 tests/verification/run_verification.py

# Run as pytest
pytest tests/test_verification.py -v
```
