"""Integrity tests: orphans, edge vocabulary, reachability."""

import pytest

from src.builder import load_graph
from src.integrity import check_edge_vocabulary, check_no_orphans, check_reachability
from src.schema import EDGE_TYPES


@pytest.fixture(scope="session")
def graph():
    return load_graph("graph.yaml")


def test_no_orphans(graph):
    orphans = check_no_orphans(graph)
    assert orphans == [], f"Orphan nodes (degree 0): {orphans}"


def test_edge_vocabulary(graph):
    violations = check_edge_vocabulary(graph, EDGE_TYPES)
    assert violations == [], f"Edges with invalid types: {violations}"


def test_reachability(graph):
    unreachable = check_reachability(graph)
    assert unreachable == [], f"Unreachable nodes (disconnected): {unreachable}"

def _norm(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").split())


def test_every_node_has_description(graph):
    """The AI layer embeds and narrates from descriptions; an empty one is invisible to it."""
    missing = [n for n, d in graph.nodes(data=True) if not d.get("description", "").strip()]
    assert missing == [], (
        f"Nodes without a description: {missing}. "
        "Wrong answer: the embedder cannot match questions to these nodes."
    )


def test_labels_and_aliases_are_unambiguous(graph):
    """No label/alias string may belong to two different nodes."""
    owners: dict[str, set[str]] = {}
    for node, data in graph.nodes(data=True):
        for text in [data["label"], *data.get("aliases", [])]:
            owners.setdefault(_norm(text), set()).add(node)
    clashes = {text: sorted(ids) for text, ids in owners.items() if len(ids) > 1}
    assert clashes == {}, (
        f"Ambiguous label/alias strings: {clashes}. "
        "Wrong answer: exact-match resolution would pick an arbitrary node."
    )
