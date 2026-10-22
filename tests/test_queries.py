"""Query tests with fixtures-first: expected answers written before queries run."""

import pytest

from src.builder import load_graph
from src.queries import build_coverage, registered_activities, study_scope, value_chain


@pytest.fixture(scope="session")
def graph():
    return load_graph("graph.yaml")

class TestValueChain:
    def test_paths_exist(self, graph):
        paths = value_chain(graph)
        assert len(paths) >= 2, (
            "Expected at least 2 paths (unlevered and levered). "
            "Wrong answer: no path means a flows-to edge was never connected."
        )

    def test_unlevered_path_length(self, graph):
        paths = value_chain(graph)
        lengths = [len(p) - 1 for p in paths]
        assert 5 in lengths, (
            "Unlevered path should have 5 edges. "
            "Wrong answer: missing step in FCF -> DR -> EV -> ND -> EqV -> PSV."
        )

    def test_unlevered_path_contains_net_debt(self, graph):
        paths = value_chain(graph)
        long_paths = [p for p in paths if len(p) - 1 == 5]
        for p in long_paths:
            assert "net_debt" in p, (
                "Unlevered path must pass through net_debt. "
                "Wrong answer: reported enterprise value as equity value."
            )

    def test_levered_path_length(self, graph):
        paths = value_chain(graph)
        lengths = [len(p) - 1 for p in paths]
        assert 3 in lengths, (
            "Levered path should have 3 edges. "
            "Wrong answer: levered route not connected."
        )


EXCLUDED_ACTIVITIES = [
    "investment_advisory",
    "broker_dealer_execution",
    "fund_raising",
    "backtest_marketing",
]



class TestStudyScope:
    def test_excluded_activities_exist(self, graph):
        """Step 1: assert all 4 excluded activities exist with requires-registration."""
        registered = registered_activities(graph)
        for activity in EXCLUDED_ACTIVITIES:
            assert activity in registered, (
                f"'{activity}' must exist and carry a requires-registration edge."
            )

    def test_excluded_not_in_study(self, graph):
        """Step 2: assert study query returns none of the 4."""
        permitted = study_scope(graph)
        for activity in EXCLUDED_ACTIVITIES:
            assert activity not in permitted, (
                f"'{activity}' returned by study_scope. "
                "Wrong answer: study scope was typed for work the law sends to registration."
            )

    def test_study_scope_not_empty(self, graph):
        """Guard against passing on an empty graph."""
        permitted = study_scope(graph)
        assert len(permitted) > 0, (
            "Study scope returned nothing. "
            "Wrong answer: no permitted-as-study edge was typed."
        )


class TestBuildCoverage:
    def test_landmarks_covered(self, graph):
        result = build_coverage(graph)
        assert result["landmarks"] == [], (
            f"Uncovered landmarks: {result['landmarks']}. "
            "A landmark returned was collected, never practiced."
        )

    def test_domains_covered(self, graph):
        result = build_coverage(graph)
        assert result["domains"] == [], (
            f"Uncovered domains: {result['domains']}. "
            "A domain returned is an area the path skips."
        )

    def test_instruments_covered(self, graph):
        result = build_coverage(graph)
        assert result["instruments"] == [], (
            f"Uncovered instruments: {result['instruments']}. "
            "An instrument returned was named but never exercised."
        )

CFA_LEVEL_I_TOPICS = [
    "Ethical and Professional Standards",
    "Quantitative Methods",
    "Economics",
    "Financial Statement Analysis",
    "Corporate Issuers",
    "Equity Investments",
    "Fixed Income",
    "Derivatives",
    "Alternative Investments",
    "Portfolio Management",
]

class TestCFACoverage:
    def test_all_topics_mapped(self, graph):
        """Every CFA Level I topic area maps to at least one node."""
        node_ids = set(graph.nodes())
        unmapped = []
        topic_map = {
            "Ethical and Professional Standards": "ethics_and_professional_standards",
            "Quantitative Methods": "quantitative_methods",
            "Economics": "economics",
            "Financial Statement Analysis": "financial_statement_analysis",
            "Corporate Issuers": "corporate_finance",
            "Equity Investments": "equity_investments",
            "Fixed Income": "fixed_income",
            "Derivatives": "derivatives",
            "Alternative Investments": "alternative_investments",
            "Portfolio Management": "portfolio_management",
        }
        for topic, node_id in topic_map.items():
            if node_id not in node_ids:
                unmapped.append(topic)
        assert unmapped == [], (
            f"CFA topics with no mapped node: {unmapped}. "
            "Every topic area must map to a node in the graph."
        )