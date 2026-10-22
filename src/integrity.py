"""Integrity checks: no orphans, vocabulary-only edges, full reachability."""

import networkx as nx


def check_no_orphans(G: nx.DiGraph) -> list[str]:
    """Return node IDs with degree 0 (no edges at all)."""
    return [n for n in G.nodes() if G.degree(n) == 0]


def check_edge_vocabulary(G: nx.DiGraph, allowed: frozenset[str]) -> list[tuple]:
    """Return edges whose type is not in the allowed set."""
    violations = []
    for u, v, data in G.edges(data=True):
        if data.get("type") not in allowed:
            violations.append((u, v, data.get("type")))
    return violations


def check_reachability(G: nx.DiGraph) -> list[str]:
    """Return nodes not reachable from the rest (disconnected components)."""
    undirected = G.to_undirected()
    if nx.is_connected(undirected):
        return []
    components = list(nx.connected_components(undirected))
    largest = max(components, key=len)
    unreachable = []
    for comp in components:
        if comp != largest:
            unreachable.extend(comp)
    return sorted(unreachable)