"""Query pack: value chain, study scope, registered activities, build coverage."""

import networkx as nx


def value_chain(G: nx.DiGraph) -> list[list[str]]:
    """Find all simple paths from free_cash_flow to per_share_value via flows-to edges."""
    flows_to_graph = nx.DiGraph()
    for u, v, data in G.edges(data=True):
        if data.get("type") == "flows-to":
            flows_to_graph.add_edge(u, v)

    if "free_cash_flow" not in flows_to_graph or "per_share_value" not in flows_to_graph:
        return []

    paths = list(nx.all_simple_paths(flows_to_graph, "free_cash_flow", "per_share_value"))
    return sorted(paths, key=len, reverse=True)

def study_scope(G: nx.DiGraph) -> list[str]:
    """Return activity nodes connected to study_scope by permitted-as-study edges."""
    activities = []
    for u, v, data in G.edges(data=True):
        if data.get("type") == "permitted-as-study" and v == "study_scope":
            if G.nodes[u].get("type") == "activity":
                activities.append(u)
    return sorted(activities)


def registered_activities(G: nx.DiGraph) -> list[str]:
    """Return activity nodes that carry a requires-registration edge."""
    registered = []
    for u, v, data in G.edges(data=True):
        if data.get("type") == "requires-registration":
            if G.nodes[u].get("type") == "activity":
                registered.append(u)
    return sorted(set(registered))



def build_coverage(G: nx.DiGraph) -> dict[str, list[str]]:
    """Return landmark nodes, domain nodes, and instrument nodes with no link to a build."""
    has_build_link = set()
    for u, v, data in G.edges(data=True):
        if G.nodes.get(v, {}).get("type") == "build":
            has_build_link.add(u)

    uncovered_landmarks = []
    uncovered_domains = []
    uncovered_instruments = []

    for node, attrs in G.nodes(data=True):
        if attrs.get("landmark") and node not in has_build_link:
            uncovered_landmarks.append(node)
        if attrs.get("type") == "domain" and node not in has_build_link:
            uncovered_domains.append(node)
        if attrs.get("type") == "instrument" and node not in has_build_link:
            uncovered_instruments.append(node)

    return {
        "landmarks": sorted(uncovered_landmarks),
        "domains": sorted(uncovered_domains),
        "instruments": sorted(uncovered_instruments),
    }