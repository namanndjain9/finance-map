"""The eval set itself: well-formed, and the alias-tier cases pass with no model at all."""

import pytest

from evals.scoring import CATEGORIES, STATUSES, load_cases, score_all
from src.ai.resolver import Resolver
from src.builder import load_graph


@pytest.fixture(scope="session")
def graph():
    return load_graph("graph.yaml")


@pytest.fixture(scope="session")
def cases():
    return load_cases()


def test_case_ids_unique(cases):
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "Duplicate eval case ids make results ambiguous."


def test_cases_are_well_formed(cases, graph):
    for c in cases:
        assert c["category"] in CATEGORIES, c["id"]
        assert c["tier"] in {"alias", "model"}, c["id"]
        assert c.get("expected_status", "ok") in STATUSES, c["id"]
        named = [
            *c.get("expected_start", []), *c.get("expected_goal", []),
            *c.get("path_must_include", []), *c.get("path_must_exclude", []),
        ]
        unknown = [n for n in named if n not in graph]
        assert unknown == [], f"{c['id']} references nodes not in the graph: {unknown}"
        if c.get("expected_status", "ok") != "out_of_scope":
            assert c.get("expected_goal"), f"{c['id']} needs expected_goal"


def test_alias_tier_cases_pass_offline(cases, graph):
    """No embeddings, no LLM: exact matching and rules alone must get these right."""
    alias_cases = [c for c in cases if c["tier"] == "alias"]
    rows = score_all(alias_cases, Resolver(graph), graph)
    failures = [(r["case"]["id"], r["outcome"], r["checks"]) for r in rows if not r["correct"]]
    assert failures == [], (
        f"Alias-tier failures: {failures}. "
        "Wrong answer: a question that names its concepts was mapped to the wrong nodes."
    )
