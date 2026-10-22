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