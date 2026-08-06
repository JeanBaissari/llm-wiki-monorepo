#!/usr/bin/env python3
"""graph_insights.py — Analyze a wiki's wikilink graph for surprising connections & knowledge gaps.
Usage: python3 graph_insights.py <wiki-root> [--connections <n>] [--gaps <n>] [--format json|markdown]
Builds a directed graph from [[wikilinks]], detects communities, and surfaces surprising
cross-boundary connections and knowledge gaps. Pure Python, no external dependencies."""

import argparse, json, os, re, sys, warnings
from collections import Counter, defaultdict
from pathlib import Path

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

def detect_communities_for_insights(nodes, edges):
    """Community assignments via the canonical Louvain engine (graph/louvain.py).

    Replaces the former label-propagation pass so `llm-wiki insights` and the
    TypeScript graph-engine share one community-detection algorithm (LWM_024 /
    ADR-0017). Returns {node_id: community_id} renumbered size-descending — the
    same shape the old label-propagation returned, so downstream scoring is
    unchanged. The Louvain transition warning is suppressed here because this IS
    the intended, completed migration for insights.
    """
    node_list = [
        {"id": pid, "label": a["label"], "linkCount": a.get("linkCount", 0)}
        for pid, a in nodes.items()
    ]
    edge_list = [{"source": s, "target": t, "weight": 1} for s, t in edges]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        assignments, _ = detect_communities(node_list, edge_list, seed=42)
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

def score_connections(nodes, edges, community, cstats, top_n):
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
            xc = 1.0
            if cs in cstats and ct in cstats:
                avg = (cstats[cs]["nodeCount"] + cstats[ct]["nodeCount"]) / 2
                xc += min(avg / 20, 1.0)
            score += xc; reasons.append(f"cross-community (C{cs}↔C{ct})")
        ph = (1.0 - deg_ratio) * 0.8
        if ph > 0.4 and max_d > 5:
            score += ph; reasons.append(f"peripheral→hub (deg {min_d}↔{max_d})")
        ts, tt = ns.get("type", "concept"), nt.get("type", "concept")
        if ts != tt:
            score += 0.5; reasons.append(f"cross-type ({ts}↔{tt})")
        if reasons:
            scored.append({
                "source": s, "target": t, "sourceLabel": ns["label"],
                "targetLabel": nt["label"], "sourceType": ts, "targetType": tt,
                "sourceDegree": ds, "targetDegree": dt, "score": round(score, 3),
                "reasons": reasons, "communities": (cs, ct),
            })
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_n]

def find_gaps(nodes, edges, adj, community, cstats, top_n):
    gaps = {"isolatedNodes": [], "sparseCommunities": [], "bridgeNodes": []}
    for nid, attrs in nodes.items():
        deg = attrs.get("degree", 0)
        if deg <= 1:
            gaps["isolatedNodes"].append({
                "id": nid, "label": attrs["label"], "type": attrs.get("type", "concept"),
                "degree": deg, "community": community.get(nid, -1),
            })
    for cid, st in cstats.items():
        if st["nodeCount"] >= 3 and st["cohesion"] < 0.15:
            gaps["sparseCommunities"].append(st)
    for nid in nodes:
        seen = set()
        for nb in adj.get(nid, set()): seen.add(community.get(nb, -1))
        if len(seen) >= 3:
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

def compute_insights(wiki_root: str, connections: int = 10, gaps: int = 10, fmt: str = "markdown"):
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
    adj = {nid: set() for nid in nodes}
    for s, t in edges: adj[s].add(t); adj[t].add(s)
    comm = detect_communities_for_insights(nodes, edges)
    cstats = comm_stats(edges, comm)
    top_conns = score_connections(nodes, edges, comm, cstats, connections)
    ks = find_gaps(nodes, edges, adj, comm, cstats, gaps)
    if fmt == "json":
        return {
            "summary": {"nodeCount": len(nodes), "edgeCount": len(edges), "communityCount": len(cstats)},
            "surprisingConnections": top_conns, "knowledgeGaps": ks,
        }
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
    args = parser.parse_args()
    result = compute_insights(args.wiki_root, args.connections, args.gaps, args.format)
    if isinstance(result, dict):
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result)
    return 0

if __name__ == "__main__":
    sys.exit(main())
