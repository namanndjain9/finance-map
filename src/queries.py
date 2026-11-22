"""Query pack: value chain, study scope, registered activities, build coverage, roadmap."""

from dataclasses import asdict, dataclass, field

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

# ---------------------------------------------------------------------------
# Roadmap: deterministic path between two nodes (no AI involved)
# ---------------------------------------------------------------------------

# Registration edges are never traversed: a learning roadmap must not route
# through a regulated activity. permitted-as-study stays traversable so the
# study-only activities (e.g. simulated_paper_trading) are reachable.
TRAVERSAL_EXCLUDED_EDGE_TYPES = frozenset({"requires-registration"})

EDGE_COST = {
    "precedes": 1.0,
    "requires": 1.0,
    "flows-to": 1.0,
    "belongs-to": 1.0,
    "permitted-as-study": 1.0,
    "prices": 1.5,
    "exercised-by": 1.5,
}
BACKWARD_FACTOR = 3.0  # walking an edge against its direction costs this much more
# domain -requires-> build edges exist to satisfy build coverage, not to teach. Taken as a
# 1-cost shortcut they skip the concepts that explain the build (e.g. economics -> capm_calculator
# without market_efficiency or the CAPM), so they are a costly jump instead of an ordinary step.
COVERAGE_JUMP_COST = 3.5


class RoadmapError(ValueError):
    """Raised when a roadmap cannot be built (unknown node, no path)."""


class RegisteredActivityError(RoadmapError):
    """Raised when an endpoint is an activity that requires registration."""

    def __init__(self, activity: str):
        super().__init__(f"'{activity}' requires registration and is outside the study roadmap.")
        self.activity = activity


@dataclass
class Step:
    node: str
    type: str
    label: str
    description: str
    via_edge: str | None  # edge type used to arrive here (None for the first step)
    direction: str | None  # "forward" | "backward" | None for the first step
    practice_builds: list[str] = field(default_factory=list)


@dataclass
class Roadmap:
    start: str
    goal: str
    steps: list[Step]
    directed: bool  # True when a purely forward path existed
    regulated_nearby: list[str] = field(default_factory=list)

    @property
    def nodes(self) -> list[str]:
        return [s.node for s in self.steps]

    def to_dict(self) -> dict:
        return asdict(self)


def _traversal_graph(G: nx.DiGraph, allow_backward: bool) -> nx.DiGraph:
    """Weighted arcs for path search; each arc records the edge type and direction."""
    H = nx.DiGraph()
    H.add_nodes_from(G.nodes())

    def offer(a: str, b: str, weight: float, edge_type: str, direction: str) -> None:
        if not H.has_edge(a, b) or weight < H[a][b]["weight"]:
            H.add_edge(a, b, weight=weight, edge_type=edge_type, direction=direction)

    for u, v, data in G.edges(data=True):
        edge_type = data.get("type")
        if edge_type in TRAVERSAL_EXCLUDED_EDGE_TYPES:
            continue
        cost = EDGE_COST.get(edge_type, 1.0)
        if (
            edge_type == "requires"
            and G.nodes[u].get("type") == "domain"
            and G.nodes[v].get("type") == "build"
        ):
            cost = COVERAGE_JUMP_COST
        offer(u, v, cost, edge_type, "forward")
        if allow_backward:
            offer(v, u, cost * BACKWARD_FACTOR, edge_type, "backward")
    return H


def _practice_builds(G: nx.DiGraph, node: str) -> list[str]:
    return sorted(v for v in G.successors(node) if G.nodes[v].get("type") == "build")


def default_start(G: nx.DiGraph, goal: str) -> str:
    """Nearest root ancestor of `goal` along forward edges; the learner's natural entry point."""
    H = _traversal_graph(G, allow_backward=False)
    ancestors = nx.ancestors(H, goal)
    roots = [a for a in ancestors if H.in_degree(a) == 0]
    if roots:
        return min(roots, key=lambda r: nx.dijkstra_path_length(H, r, goal))
    if H.in_degree(goal) == 0 and G.nodes[goal].get("type") == "domain":
        return goal
    # Study-only activities have no forward ancestors: enter at the first domain.
    domain_roots = sorted(
        n for n in G.nodes() if G.nodes[n].get("type") == "domain" and H.in_degree(n) == 0
    )
    return domain_roots[0] if domain_roots else goal


def roadmap_path(G: nx.DiGraph, start: str, goal: str) -> Roadmap:
    """Shortest learning path from `start` to `goal`.

    Try 1 uses forward edges only. If there is none, try 2 also allows walking
    edges backward at a penalty; those steps are flagged direction="backward"
    (the earlier node is a prerequisite of the later one in the graph).
    """
    for node in (start, goal):
        if node not in G:
            raise RoadmapError(f"'{node}' is not a node in the graph.")
    registered = set(registered_activities(G))
    for node in (start, goal):
        if node in registered:
            raise RegisteredActivityError(node)

    directed = True
    H = _traversal_graph(G, allow_backward=False)
    try:
        path = nx.dijkstra_path(H, start, goal, weight="weight")
    except nx.NetworkXNoPath:
        directed = False
        H = _traversal_graph(G, allow_backward=True)
        try:
            path = nx.dijkstra_path(H, start, goal, weight="weight")
        except nx.NetworkXNoPath:
            raise RoadmapError(f"No path between '{start}' and '{goal}'.") from None

    steps = []
    for i, node in enumerate(path):
        attrs = G.nodes[node]
        arc = H[path[i - 1]][node] if i else None
        steps.append(
            Step(
                node=node,
                type=attrs.get("type", ""),
                label=attrs.get("label", node),
                description=attrs.get("description", ""),
                via_edge=arc["edge_type"] if arc else None,
                direction=arc["direction"] if arc else None,
                practice_builds=_practice_builds(G, node),
            )
        )

    neighbourhood = set(path)
    for node in path:
        neighbourhood.update(G.predecessors(node))
        neighbourhood.update(G.successors(node))
    return Roadmap(
        start=start,
        goal=goal,
        steps=steps,
        directed=directed,
        regulated_nearby=sorted(registered & neighbourhood),
    )
