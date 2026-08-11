#!/usr/bin/env python3
"""graph_insights.py — Analyze a wiki's wikilink graph for surprising connections & knowledge gaps.
Usage: python3 graph_insights.py <wiki-root> [--connections <n>] [--gaps <n>] [--format json|markdown]
Builds a directed graph from [[wikilinks]], detects communities, and surfaces surprising
cross-boundary connections and knowledge gaps. Pure Python, no external dependencies."""

import argparse, json, os, re, sys, warnings
from collections import Counter, defaultdict
from pathlib import Path

from llm_wiki.core.config import TuningConfig
from llm_wiki.core.layout import discover_layout
from llm_wiki.core.frontmatter import parse_frontmatter
from llm_wiki.graph.louvain import detect_communities

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
SKIP_STEMS = frozenset({"index", "log", "overview"})

def load_md(wiki_root: Path) -> list[Path]:
    if not wiki_root.is_dir():
        return []
    files = []
    for p in wiki_root.rglob("*.md"):
        if p.stem.lower() in SKIP_STEMS: continue
        if any(part.startswith(".") for part in p.relative_to(wiki_root).parts): continue
        files.append(p)
    return files

def build_graph(files, wiki_root):
    nodes = {}
    edge_bag = []
    stem_to_id = {}
    for fp in files:
        rel = fp.relative_to(wiki_root)
        pid = str(rel.with_suffix("")).replace(os.sep, "/")
        stem_to_id[fp.stem.lower()] = pid
        stem_to_id[pid.lower()] = pid
    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text) or {}
        title, ntype = fm.get("title", fp.stem), fm.get("type", "concept")
        sources = fm.get("sources", [])
        rel = fp.relative_to(wiki_root)
        pid = str(rel.with_suffix("")).replace(os.sep, "/")
        targets = set()
        for link in WIKILINK_RE.findall(text):
            tgt = link.strip()
            resolved = stem_to_id.get(tgt.lower()) or stem_to_id.get(tgt)
            if resolved and resolved != pid:
                targets.add(resolved)
                edge_bag.append((pid, resolved))
        nodes[pid] = {
            "id": pid, "label": title, "type": ntype, "path": str(rel),
            "linkCount": len(targets),
            "sources": sources if isinstance(sources, list) else [sources],
        }
    known = set(nodes)
    edges = [(s, t) for s, t in edge_bag if s in known and t in known]
    deg = Counter()
    for s, t in edges: deg[s] += 1; deg[t] += 1
    for nid, attrs in nodes.items(): attrs["degree"] = deg.get(nid, 0)
    return nodes, edges

def _select_community_engine(engine: str | None = None, tuning=None):
    """Return the ``detect_communities`` callable for the selected engine.

    Precedence (BKD-003): explicit ``engine`` argument > resolved tuning
    ``community.engine`` (CLI > env > file > default on the LWM_031 surface) >
    legacy ``LLM_WIKI_COMMUNITY_ENGINE`` env > Louvain default. Leiden
    (LWM_027 / ADR-0025) is only selected when the optional ``[leiden]`` extra
    is importable — otherwise it falls back to Louvain without raising. The
    default is never silently flipped (gated on the ADR-0025 parity gate via
    scripts/community_engine_parity.py + the committed margin baseline).
    """
    import os

    name = None
    if engine:
        name = engine
    elif tuning is not None:
        name = getattr(getattr(tuning, "community", None), "engine", None)
    name = name or os.environ.get("LLM_WIKI_COMMUNITY_ENGINE", "louvain")
    name = str(name).lower()
    if name == "leiden":
        from llm_wiki.graph import leiden
        if leiden.is_leiden_available():
            return leiden.detect_communities
    return detect_communities


def detect_communities_for_insights(nodes, edges, engine: str | None = None,
                                    *, resolution: float = 1.0, seed: int = 42,
                                    tuning=None):
    """Community assignments via the canonical Python engine (graph/louvain.py).

    Replaces the former label-propagation pass so `llm-wiki insights` and the
    TypeScript graph-engine share one community-detection algorithm (LWM_024 /
    ADR-0017). Returns {node_id: community_id} renumbered size-descending — the
    same shape the old label-propagation returned, so downstream scoring is
    unchanged. ``engine`` selects Louvain (default) or the opt-in Leiden sidecar
    (LWM_027); when ``engine`` is None and ``tuning`` is given,
    ``community.engine`` from the resolved tuning surface is used (BKD-003 —
    CLI > env > file > default). ``resolution``/``seed`` are threaded from
    ``community.*`` (LWM_031); Leiden consumes seed only (its resolution is
    fixed by LWM_027's own surface), so default values are byte-identical for
    both engines.
    """
    node_list = [
        {"id": pid, "label": a["label"], "linkCount": a.get("linkCount", 0)}
        for pid, a in nodes.items()
    ]
    edge_list = [{"source": s, "target": t, "weight": 1} for s, t in edges]
    _detect = _select_community_engine(engine, tuning)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        if _detect is detect_communities:  # Louvain accepts resolution
            assignments, _ = _detect(node_list, edge_list, seed=seed, resolution=resolution)
        else:  # Leiden sidecar (resolution governed by LWM_027)
            assignments, _ = _detect(node_list, edge_list, seed=seed)
    # Ensure every node (incl. isolated) has an assignment.
    for pid in nodes:
        assignments.setdefault(pid, len(assignments))
    return assignments

def comm_stats(edges, community):
    c_nodes = defaultdict(set); c_edges = defaultdict(int)
    for s, t in edges:
        cs, ct = community[s], community[t]
        c_nodes[cs].add(s); c_nodes[cs].add(t)
        if cs == ct: c_edges[cs] += 1
    stats = {}
    for cid, members in c_nodes.items():
        n = len(members)
        possible = n * (n - 1) // 2
        cohesion = c_edges[cid] / possible if possible > 0 else 0.0
        stats[cid] = {"id": cid, "nodeCount": n, "edgeCount": c_edges[cid],
                       "cohesion": round(cohesion, 4), "nodes": sorted(members)}
    return stats

def score_connections(nodes, edges, community, cstats, top_n, *,
                      signal_scores=None, peripheral_hub_gate=None,
                      surprise_threshold=None):
    """Score surprising connections, top ``top_n`` by score.

    LWM_031 threading: ``signal_scores`` (only keys the user overrode — the
    cross-community base via ``crossCommunity``, the cross-type contribution via
    ``crossTypeWeak``, the peripheral→hub factor via ``peripheralToHub``) and
    ``peripheral_hub_gate`` (from ``insights.peripheralHubRatio``) replace this
    model's own literals (1.0 / 0.5 / 0.8 / 0.4). ``surprise_threshold`` (from
    ``insights.surpriseThreshold``) filters candidates by minimum score, mirroring
    the TS signal registry. When nothing is overridden the literals are used
    unchanged, so direct calls are byte-identical. ``crossTypeStrong`` and
    ``lowWeight`` steer the TS signal registry only — this coarser model has no
    distant-pair or low-weight signals (documented in docs/reference/tuning.md).
    """
    if signal_scores is None:
        xc_base, ct_score, ph_factor = 1.0, 0.5, 0.8
    else:
        xc_base = float(signal_scores.get("crossCommunity", 1.0))
        ct_score = float(signal_scores.get("crossTypeWeak", 0.5))
        ph_factor = float(signal_scores.get("peripheralToHub", 0.8))
    gate = 0.4 if peripheral_hub_gate is None else float(peripheral_hub_gate)
    scored = []
    for s, t in edges:
        ns, nt = nodes.get(s), nodes.get(t)
        if not ns or not nt: continue
        cs, ct = community[s], community[t]
        ds, dt = ns.get("degree", 0), nt.get("degree", 0)
        max_d, min_d = max(ds, dt) or 1, min(ds, dt) or 1
        deg_ratio = min_d / max_d
        score, reasons = 0.0, []
        if cs != ct:
            xc = xc_base
            if cs in cstats and ct in cstats:
                avg = (cstats[cs]["nodeCount"] + cstats[ct]["nodeCount"]) / 2
                xc += min(avg / 20, 1.0)
            score += xc; reasons.append(f"cross-community (C{cs}↔C{ct})")
        ph = (1.0 - deg_ratio) * ph_factor
        if ph > gate and max_d > 5:
            score += ph; reasons.append(f"peripheral→hub (deg {min_d}↔{max_d})")
        ts, tt = ns.get("type", "concept"), nt.get("type", "concept")
        if ts != tt:
            score += ct_score; reasons.append(f"cross-type ({ts}↔{tt})")
        if reasons:
            scored.append({
                "source": s, "target": t, "sourceLabel": ns["label"],
                "targetLabel": nt["label"], "sourceType": ts, "targetType": tt,
                "sourceDegree": ds, "targetDegree": dt, "score": round(score, 3),
                "reasons": reasons, "communities": (cs, ct),
            })
    if surprise_threshold is not None:
        scored = [x for x in scored if x["score"] >= surprise_threshold]
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_n]

def find_gaps(nodes, edges, adj, community, cstats, top_n, *,
              sparse_min_nodes=3, sparse_cohesion_threshold=0.15,
              bridge_min=3, isolated_max_degree=1):
    """Detect knowledge gaps (isolated nodes / sparse communities / bridge nodes).

    ``sparse_min_nodes``/``sparse_cohesion_threshold``/``bridge_min``/
    ``isolated_max_degree`` thread the ``insights.*`` tuning keys (LWM_031);
    defaults equal the model's literals, so direct calls are byte-identical.
    """
    gaps = {"isolatedNodes": [], "sparseCommunities": [], "bridgeNodes": []}
    for nid, attrs in nodes.items():
        deg = attrs.get("degree", 0)
        if deg <= isolated_max_degree:
            gaps["isolatedNodes"].append({
                "id": nid, "label": attrs["label"], "type": attrs.get("type", "concept"),
                "degree": deg, "community": community.get(nid, -1),
            })
    for cid, st in cstats.items():
        if st["nodeCount"] >= sparse_min_nodes and st["cohesion"] < sparse_cohesion_threshold:
            gaps["sparseCommunities"].append(st)
    for nid in nodes:
        seen = set()
        for nb in adj.get(nid, set()): seen.add(community.get(nb, -1))
        if len(seen) >= bridge_min:
            gaps["bridgeNodes"].append({
                "id": nid, "label": nodes[nid]["label"], "type": nodes[nid].get("type", "concept"),
                "degree": nodes[nid].get("degree", 0),
                "connectedCommunities": sorted(seen), "communityCount": len(seen),
            })
    for k in ("isolatedNodes", "bridgeNodes"):
        gaps[k].sort(key=lambda x: -x.get("degree", 0))
        gaps[k] = gaps[k][:top_n]
    return gaps

def fmt_md(connections, gaps, nc, ec, cc):
    lines = [
        "# Wiki Graph Insights\n",
        f"- **Nodes:** {nc}  \n- **Edges:** {ec}  \n- **Communities:** {cc}\n",
        "## Surprising Connections\n",
    ]
    if not connections:
        lines.append("*No surprising connections found.*\n")
    else:
        lines.append(f"Top {len(connections)}:\n")
        for i, c in enumerate(connections, 1):
            lines.extend([
                f"### {i}. {c['sourceLabel']} → {c['targetLabel']}",
                f"- **Score:** {c['score']}  \n- **Reason:** {'; '.join(c['reasons'])}",
                f"- **Types:** {c['sourceType']} → {c['targetType']}  **Degrees:** {c['sourceDegree']} → {c['targetDegree']}",
                f"- **Pages:** `{c['source']}` → `{c['target']}`\n",
            ])
    lines.append("## Knowledge Gaps\n")
    iso = gaps.get("isolatedNodes", [])
    lines.append(f"### Isolated Nodes ({len(iso)})\n")
    if iso:
        for n in iso: lines.append(f"- **{n['label']}** (`{n['id']}`) — deg {n['degree']}, {n['type']}")
    else: lines.append("*None.*\n")
    sc = gaps.get("sparseCommunities", [])
    lines.append(f"\n### Sparse Communities ({len(sc)})\n")
    if sc:
        for c in sc: lines.append(f"- Community **C{c['id']}**: {c['nodeCount']} nodes, {c['edgeCount']} edges, cohesion {c['cohesion']}")
    else: lines.append("*None.*\n")
    bn = gaps.get("bridgeNodes", [])
    lines.append(f"\n### Bridge Nodes ({len(bn)})\n")
    if bn:
        for n in bn:
            cs = " ↔ ".join(f"C{x}" for x in n["connectedCommunities"])
            lines.append(f"- **{n['label']}** (`{n['id']}`) — {n['communityCount']} communities ({cs})")
    else: lines.append("*None.*\n")
    return "\n".join(lines)

def compute_insights(wiki_root: str, connections: int = 10, gaps: int = 10,
                     fmt: str = "markdown", include_derived: bool = False,
                     tuning=None):
    layout = discover_layout(wiki_root)
    root = Path(layout.pages_dir)
    if not root.is_dir():
        empty = {"summary": {"nodeCount": 0, "edgeCount": 0, "communityCount": 0},
                 "surprisingConnections": [], "knowledgeGaps": {}}
        if fmt == "json":
            return empty
        return "# Wiki Graph Insights\n\n*No content pages found to analyze.*"
    files = load_md(root)
    if not files:
        empty = {"summary": {"nodeCount": 0, "edgeCount": 0, "communityCount": 0},
                 "surprisingConnections": [], "knowledgeGaps": {}}
        if fmt == "json":
            return empty
        return "# Wiki Graph Insights\n\n*No content pages found to analyze.*"
    nodes, edges = build_graph(files, root)

    # --include-derived: opt-in layer inclusion, fail-closed on the NMI+modularity
    # gate (ADR-0027 §gate). Default (flag unset) never opens the layer.
    derived_report = None
    if include_derived:
        from llm_wiki.graph import derived_edges as _de
        derived = _de.load_derived_edges(wiki_root)
        # Derived edges are keyed by page stem; map them into this consumer's
        # id space (relative paths without extension) so the gate and the
        # combined graph evaluate the SAME edge set.
        stem_to_id = {}
        for pid in nodes:
            stem_to_id.setdefault(pid.rsplit("/", 1)[-1].lower(), pid)
        mapped = []
        for e in derived:
            s = stem_to_id.get(str(e["source"]).lower())
            t = stem_to_id.get(str(e["target"]).lower())
            if s and t and s != t:
                mapped.append({"source": s, "target": t,
                               "weight": e.get("weight", 1)})
        wiki_edges = [{"source": s, "target": t, "weight": 1} for s, t in edges]
        include, derived_report = _de.should_include_derived(nodes, wiki_edges, mapped)
        if include:
            extra = [(e["source"], e["target"]) for e in mapped]
            edges = edges + [pair for pair in extra if pair not in edges]

    adj = {nid: set() for nid in nodes}
    for s, t in edges: adj[s].add(t); adj[t].add(s)

    # LWM_031: thread the resolved tuning. When no tuning is passed (or nothing
    # was overridden), every value equals the model literals → byte-identical.
    if tuning is None:
        tuning = TuningConfig()
    ins_cfg = tuning.insights
    comm = detect_communities_for_insights(nodes, edges, tuning=tuning,
                                           resolution=tuning.community.resolution,
                                           seed=tuning.community.seed)
    cstats = comm_stats(edges, comm)
    over = tuning.overridden()
    sig_over = {k.rsplit(".", 1)[-1]: v
                for k, v in over.items() if k.startswith("insights.signalScores")}
    top_conns = score_connections(
        nodes, edges, comm, cstats, connections,
        signal_scores=sig_over or None,
        peripheral_hub_gate=over.get("insights.peripheralHubRatio"),
        surprise_threshold=over.get("insights.surpriseThreshold"),
    )
    ks = find_gaps(nodes, edges, adj, comm, cstats, gaps,
                   sparse_min_nodes=ins_cfg.sparseMinNodes,
                   sparse_cohesion_threshold=ins_cfg.sparseCohesionThreshold,
                   bridge_min=ins_cfg.bridgeCommunityMin,
                   isolated_max_degree=ins_cfg.isolatedMaxDegree)
    if fmt == "json":
        out = {
            "summary": {"nodeCount": len(nodes), "edgeCount": len(edges), "communityCount": len(cstats)},
            "surprisingConnections": top_conns, "knowledgeGaps": ks,
        }
        if derived_report is not None:
            out["derivedGate"] = derived_report
        return out
    return fmt_md(top_conns, ks, len(nodes), len(edges), len(cstats))

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze a wiki's wikilink graph for surprising connections and knowledge gaps.")
    parser.add_argument("wiki_root", help="Path to wiki root directory")
    parser.add_argument("--connections", type=int, default=10,
                        help="Number of top surprising connections (default: 10)")
    parser.add_argument("--gaps", type=int, default=10,
                        help="Max items per gap category (default: 10)")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown",
                        help="Output format (default: markdown)")
    parser.add_argument("--include-derived", action="store_true",
                        help="Opt in to the derived-edge layer, fail-closed on the "
                             "NMI+modularity gate (ADR-0027 §gate)")
    parser.add_argument("--set", action="append", default=[], dest="overrides",
                        metavar="section.key=value",
                        help="Tuning override, e.g. insights.sparseCohesionThreshold=0.3 (LWM_031)")
    args = parser.parse_args()

    from llm_wiki.core.config import ConfigError, resolve_tuning
    try:
        tuning = resolve_tuning(args.wiki_root, cli_overrides=args.overrides)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    result = compute_insights(args.wiki_root, args.connections, args.gaps,
                              args.format, include_derived=args.include_derived,
                              tuning=tuning)
    if isinstance(result, dict):
        if args.include_derived:
            g = result.get("derivedGate") or {}
            verdict = ("included" if g.get("included") else "refused (fail-closed)")
            print(f"Derived layer gate: {verdict} — {g.get('reason', 'no layer')}",
                  file=sys.stderr)
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result)
    return 0

if __name__ == "__main__":
    sys.exit(main())
