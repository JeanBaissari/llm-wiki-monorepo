#!/usr/bin/env python3
"""
graph_insights.py — Analyze a wiki's wikilink graph for surprising connections
and knowledge gaps.

Usage:
    python3 graph_insights.py <wiki-root> [--connections <n>] [--gaps <n>]
                              [--format json|markdown]

Builds a directed graph from [[wikilinks]], detects communities, and surfaces:
  • Surprising connections — edges that cross community, type, or degree boundaries
  • Knowledge gaps — isolated pages, sparse topic clusters, over-bridged nodes

Pure Python, no external dependencies.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ── constants ───────────────────────────────────────────────────────────

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
SKIP_STEMS = frozenset({"index", "log", "overview"})

# ── helpers ─────────────────────────────────────────────────────────────


def parse_frontmatter(text: str) -> dict:
    """Minimal flat key:value / list frontmatter parser (no PyYAML dep)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            result[key] = [
                p.strip().strip("\"'").strip()
                for p in inner.split(",")
                if p.strip()
            ]
        elif val.startswith(('"', "'")):
            result[key] = val[1:-1]
        else:
            result[key] = val
    return result


def load_md_files(wiki_root: Path) -> list[Path]:
    """Collect .md files, skipping structural stubs and hidden dirs."""
    files = []
    for p in wiki_root.rglob("*.md"):
        if p.stem.lower() in SKIP_STEMS:
            continue
        if any(part.startswith(".") for part in p.relative_to(wiki_root).parts):
            continue
        files.append(p)
    return files


# ── graph building ──────────────────────────────────────────────────────


def build_graph(files: list[Path], wiki_root: Path) -> tuple[dict, list]:
    """Build node dict and edge list from markdown files."""
    nodes: dict[str, dict] = {}
    edge_bag: list[tuple[str, str]] = []

    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        title = fm.get("title", fp.stem)
        ntype = fm.get("type", "page")
        sources = fm.get("sources", [])

        rel = fp.relative_to(wiki_root)
        pid = str(rel.with_suffix("")).replace(os.sep, "/")

        targets = set()
        for link in WIKILINK_RE.findall(text):
            tgt = link.strip()
            if tgt and tgt != pid:
                targets.add(tgt)
                edge_bag.append((pid, tgt))

        nodes[pid] = {
            "id": pid,
            "label": title,
            "type": ntype,
            "path": str(rel),
            "linkCount": len(targets),
            "sources": sources if isinstance(sources, list) else [sources],
        }

    # Filter edges to known nodes only
    known = set(nodes)
    edges = [(s, t) for s, t in edge_bag if s in known and t in known]

    # Compute total degree (in + out)
    deg = Counter()
    for s, t in edges:
        deg[s] += 1
        deg[t] += 1
    for nid, attrs in nodes.items():
        attrs["degree"] = deg.get(nid, 0)

    return nodes, edges


def adjacency(nodes: dict, edges: list) -> dict[str, set]:
    """Undirected adjacency sets."""
    adj = {nid: set() for nid in nodes}
    for s, t in edges:
        adj[s].add(t)
        adj[t].add(s)
    return adj


# ── community detection (label propagation) ──────────────────────────────


def detect_communities(adj: dict[str, set]) -> dict[str, int]:
    """Greedy label-propagation community detection."""
    comm = {nid: i for i, nid in enumerate(adj)}
    changed = True
    while changed:
        changed = False
        for nid in adj:
            counts = Counter()
            for nb in adj[nid]:
                counts[comm[nb]] += 1
            if not counts:
                continue
            best = min(counts.items(), key=lambda x: (-x[1], x[0]))[0]
            if best != comm[nid]:
                comm[nid] = best
                changed = True
    # Compact IDs
    seen = {}
    compact = {}
    for nid in adj:
        c = comm[nid]
        if c not in seen:
            seen[c] = len(seen)
        compact[nid] = seen[c]
    return compact


def community_stats(edges: list, community: dict[str, int]) -> dict[int, dict]:
    """Per-community: node count, edge count, cohesion."""
    c_nodes: dict[int, set] = defaultdict(set)
    c_edges: dict[int, int] = defaultdict(int)
    for s, t in edges:
        cs, ct = community[s], community[t]
        c_nodes[cs].add(s)
        c_nodes[cs].add(t)
        if cs == ct:
            c_edges[cs] += 1

    stats: dict[int, dict] = {}
    for cid, members in c_nodes.items():
        n = len(members)
        possible = n * (n - 1) // 2
        cohesion = c_edges[cid] / possible if possible > 0 else 0.0
        stats[cid] = {
            "id": cid,
            "nodeCount": n,
            "edgeCount": c_edges[cid],
            "cohesion": round(cohesion, 4),
            "nodes": sorted(members),
        }
    return stats


# ── surprising connections ──────────────────────────────────────────────


def score_connections(
    nodes: dict, edges: list, community: dict[str, int],
    comm_stats: dict, top_n: int
) -> list[dict]:
    """Score each edge for surprise; return top N."""
    scored = []
    for s, t in edges:
        ns, nt = nodes.get(s), nodes.get(t)
        if not ns or not nt:
            continue
        cs, ct = community[s], community[t]
        ds, dt = ns.get("degree", 0), nt.get("degree", 0)
        max_d = max(ds, dt) or 1
        min_d = min(ds, dt) or 1
        deg_ratio = min_d / max_d  # 1 = similar, ~0 = lopsided

        score = 0.0
        reasons = []

        # Cross-community
        if cs != ct:
            xc = 1.0
            if cs in comm_stats and ct in comm_stats:
                avg = (comm_stats[cs]["nodeCount"] + comm_stats[ct]["nodeCount"]) / 2
                xc += min(avg / 20, 1.0)
            score += xc
            reasons.append(f"cross-community (C{cs}↔C{ct})")

        # Peripheral-to-hub: lopsided degree
        ph = (1.0 - deg_ratio) * 0.8
        if ph > 0.4 and max_d > 5:
            score += ph
            reasons.append(f"peripheral→hub (deg {min_d}↔{max_d})")

        # Cross-type
        ts, tt = ns.get("type", "page"), nt.get("type", "page")
        if ts != tt:
            score += 0.5
            reasons.append(f"cross-type ({ts}↔{tt})")

        if reasons:
            scored.append({
                "source": s,
                "target": t,
                "sourceLabel": ns["label"],
                "targetLabel": nt["label"],
                "sourceType": ts,
                "targetType": tt,
                "sourceDegree": ds,
                "targetDegree": dt,
                "score": round(score, 3),
                "reasons": reasons,
                "communities": (cs, ct),
            })

    scored.sort(key=lambda x: -x["score"])
    return scored[:top_n]


# ── knowledge gaps ──────────────────────────────────────────────────────


def find_gaps(
    nodes: dict, edges: list, adj: dict[str, set],
    community: dict[str, int], comm_stats: dict, top_n: int
) -> dict[str, list]:
    """Isolated nodes, sparse communities, and bridge nodes."""
    gaps: dict[str, list] = {"isolatedNodes": [], "sparseCommunities": [], "bridgeNodes": []}

    # Isolated: degree ≤ 1 (and not a structural page)
    for nid, attrs in nodes.items():
        deg = attrs.get("degree", 0)
        if deg <= 1:
            gaps["isolatedNodes"].append({
                "id": nid,
                "label": attrs["label"],
                "type": attrs.get("type", "page"),
                "degree": deg,
                "community": community.get(nid, -1),
            })

    # Sparse communities: cohesion < 0.15 with ≥3 nodes
    for cid, st in comm_stats.items():
        if st["nodeCount"] >= 3 and st["cohesion"] < 0.15:
            gaps["sparseCommunities"].append(st)

    # Bridge nodes: connected to 3+ communities
    for nid in nodes:
        seen = set()
        for nb in adj.get(nid, set()):
            seen.add(community.get(nb, -1))
        if len(seen) >= 3:
            gaps["bridgeNodes"].append({
                "id": nid,
                "label": nodes[nid]["label"],
                "type": nodes[nid].get("type", "page"),
                "degree": nodes[nid].get("degree", 0),
                "connectedCommunities": sorted(seen),
                "communityCount": len(seen),
            })

    # Trim
    for k in ("isolatedNodes", "bridgeNodes"):
        gaps[k].sort(key=lambda x: -x.get("degree", 0))
        gaps[k] = gaps[k][:top_n]

    return gaps


# ── output ──────────────────────────────────────────────────────────────


def format_markdown(connections: list[dict], gaps: dict,
                    node_count: int, edge_count: int, comm_count: int) -> str:
    """Render human-readable Markdown report."""
    lines = [
        "# Wiki Graph Insights\n",
        f"- **Nodes:** {node_count}",
        f"- **Edges:** {edge_count}",
        f"- **Communities:** {comm_count}\n",
        "## Surprising Connections\n",
    ]
    if not connections:
        lines.append("*No surprising connections found.*\n")
    else:
        lines.append(f"Top {len(connections)} connections:\n")
        for i, c in enumerate(connections, 1):
            lines.extend([
                f"### {i}. {c['sourceLabel']} → {c['targetLabel']}",
                f"- **Score:** {c['score']}",
                f"- **Reason:** {'; '.join(c['reasons'])}",
                f"- **Types:** {c['sourceType']} → {c['targetType']}",
                f"- **Degrees:** {c['sourceDegree']} → {c['targetDegree']}",
                f"- **Communities:** C{c['communities'][0]} → C{c['communities'][1]}",
                f"- **Pages:** `{c['source']}` → `{c['target']}`\n",
            ])

    lines.append("## Knowledge Gaps\n")
    iso = gaps.get("isolatedNodes", [])
    lines.append(f"### Isolated Nodes ({len(iso)})\n")
    if iso:
        for n in iso:
            lines.append(f"- **{n['label']}** (`{n['id']}`) — degree {n['degree']}, type {n['type']}")
    else:
        lines.append("*None.*\n")

    sc = gaps.get("sparseCommunities", [])
    lines.append(f"\n### Sparse Communities ({len(sc)})\n")
    if sc:
        for c in sc:
            lines.append(
                f"- Community **C{c['id']}**: {c['nodeCount']} nodes, "
                f"{c['edgeCount']} edges, cohesion {c['cohesion']}"
            )
    else:
        lines.append("*None.*\n")

    bn = gaps.get("bridgeNodes", [])
    lines.append(f"\n### Bridge Nodes ({len(bn)})\n")
    if bn:
        for n in bn:
            c_str = " ↔ ".join(f"C{x}" for x in n["connectedCommunities"])
            lines.append(
                f"- **{n['label']}** (`{n['id']}`) — connects "
                f"{n['communityCount']} communities ({c_str})"
            )
    else:
        lines.append("*None.*\n")

    return "\n".join(lines)


# ── main ────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze a wiki's wikilink graph for surprising connections and knowledge gaps."
    )
    parser.add_argument("wiki_root", help="Path to the wiki root directory")
    parser.add_argument("--connections", type=int, default=10,
                        help="Number of top surprising connections (default: 10)")
    parser.add_argument("--gaps", type=int, default=10,
                        help="Max items per gap category (default: 10)")
    parser.add_argument("--format", choices=["json", "markdown"],
                        default="markdown",
                        help="Output format (default: markdown)")
    args = parser.parse_args()

    wiki_root = Path(args.wiki_root).resolve()
    if not wiki_root.is_dir():
        print(f"Error: {wiki_root} is not a valid directory", file=sys.stderr)
        return 1

    files = load_md_files(wiki_root)
    if not files:
        print("No markdown files found.", file=sys.stderr)
        return 1

    nodes, edges = build_graph(files, wiki_root)
    adj = adjacency(nodes, edges)
    community = detect_communities(adj)
    cstats = community_stats(edges, community)

    top_conns = score_connections(nodes, edges, community, cstats, args.connections)
    gaps = find_gaps(nodes, edges, adj, community, cstats, args.gaps)

    if args.format == "json":
        out = {
            "summary": {
                "nodeCount": len(nodes),
                "edgeCount": len(edges),
                "communityCount": len(cstats),
            },
            "surprisingConnections": top_conns,
            "knowledgeGaps": gaps,
        }
        print(json.dumps(out, indent=2, default=str))
    else:
        print(format_markdown(top_conns, gaps, len(nodes), len(edges), len(cstats)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
