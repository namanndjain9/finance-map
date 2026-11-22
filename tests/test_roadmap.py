"""Roadmap tests, fixtures-first: expected paths are fixed before the query runs."""

import pytest

from src.builder import load_graph
from src.queries import (
    RegisteredActivityError,
    RoadmapError,
    default_start,
    registered_activities,
    roadmap_path,
)


@pytest.fixture(scope="session")
def graph():
    return load_graph("graph.yaml")


# (start, goal, exact node path, directed?)
EXPECTED_PATHS = [
    ("free_cash_flow", "per_share_value",
     ["free_cash_flow", "discount_rate", "equity_value", "per_share_value"], True),
    ("fixed_income", "derivatives", ["fixed_income", "derivatives"], True),
    ("treasury_bill", "capm_calculator", ["treasury_bill", "capm_calculator"], True),
    ("free_cash_flow", "call_option",
     ["free_cash_flow", "discount_rate", "dcf_model", "equity", "call_option"], False),
]


class TestRoadmapPaths:
    @pytest.mark.parametrize("start,goal,expected,directed", EXPECTED_PATHS)
    def test_expected_path(self, graph, start, goal, expected, directed):
        result = roadmap_path(graph, start, goal)
        assert result.nodes == expected, (
            f"{start} -> {goal} returned {result.nodes}. "
            "Wrong answer: the roadmap skips or invents a learning step."
        )
        assert result.directed is directed, (
            f"directed={result.directed}, expected {directed}. "
            "Wrong answer: a backward step was presented as forward progress, or vice versa."
        )

    def test_backward_steps_are_flagged(self, graph):
        result = roadmap_path(graph, "free_cash_flow", "call_option")
        backward = [s.node for s in result.steps if s.direction == "backward"]
        assert backward == ["call_option"], (
            f"Backward steps were {backward}. "
            "Wrong answer: the narrator would call a prerequisite a follow-on."
        )

    def test_first_step_has_no_incoming_edge(self, graph):
        first = roadmap_path(graph, "fixed_income", "derivatives").steps[0]
        assert first.via_edge is None and first.direction is None

    def test_same_node_is_single_step(self, graph):
        assert roadmap_path(graph, "dcf", "dcf").nodes == ["dcf"]

    def test_unknown_node_raises(self, graph):
        with pytest.raises(RoadmapError):
            roadmap_path(graph, "free_cash_flow", "not_a_node")

    def test_practice_builds_listed(self, graph):
        steps = roadmap_path(graph, "treasury_bill", "capm_calculator").steps
        assert steps[0].practice_builds == ["capm_calculator", "yield_curve_model"], (
            f"treasury_bill builds: {steps[0].practice_builds}. "
            "Wrong answer: an instrument shown without the model that exercises it."
        )


class TestRoadmapRegulation:
    def test_never_routes_through_registered_activity(self, graph):
        registered = set(registered_activities(graph))
        nodes = list(graph.nodes())
        for start in nodes:
            if start in registered:
                continue
            for goal in ("per_share_value", "black_scholes_model", "gips_report_builder"):
                result = roadmap_path(graph, start, goal)
                assert not (set(result.nodes) & registered), (
                    f"{start} -> {goal} passes through {set(result.nodes) & registered}. "
                    "Wrong answer: a study roadmap was routed through regulated work."
                )

    @pytest.mark.parametrize(
        "activity", ["investment_advisory", "broker_dealer_execution", "fund_raising", "backtest_marketing"]
    )
    def test_registered_endpoint_refused(self, graph, activity):
        for args in (("corporate_finance", activity), (activity, "corporate_finance")):
            with pytest.raises(RegisteredActivityError):
                roadmap_path(graph, *args)

    def test_regulated_nearby_reported_at_regulatory_item(self, graph):
        result = roadmap_path(graph, "ethics_and_professional_standards", "advisers_act")
        assert {"investment_advisory", "fund_raising"} <= set(result.regulated_nearby), (
            f"regulated_nearby={result.regulated_nearby}. "
            "Wrong answer: the narrator gets no cue to add a registration caution."
        )

    def test_study_only_activities_reachable(self, graph):
        for activity in ("simulated_paper_trading", "educational_content_creation"):
            result = roadmap_path(graph, "wealth_planning", activity)
            assert result.goal == activity and result.nodes[0] == "wealth_planning"


class TestDefaultStart:
    def test_value_chain_entry_is_corporate_finance(self, graph):
        assert default_start(graph, "per_share_value") == "corporate_finance"

    def test_entry_point_has_a_path_to_every_node(self, graph):
        registered = set(registered_activities(graph))
        for goal in graph.nodes():
            if goal in registered:
                continue
            start = default_start(graph, goal)
            assert roadmap_path(graph, start, goal).nodes[-1] == goal, (
                f"default_start({goal}) = {start} has no usable path. "
                "Wrong answer: a goal-only question would return nothing."
            )


class TestCoverageJumps:
    """domain -> build 'requires' links are coverage bookkeeping, not learning steps."""

    @pytest.mark.parametrize(
        "start,goal,must_pass_through",
        [
            ("economics", "capm_calculator", ["market_efficiency", "capital_asset_pricing_model"]),
            ("portfolio_management", "gips_report_builder", ["gips_standards"]),
            ("quantitative_methods", "monte_carlo_engine", ["monte_carlo_simulation"]),
            ("corporate_finance", "dcf_model", ["dcf"]),
        ],
    )
    def test_roadmap_walks_through_the_explaining_concept(self, graph, start, goal, must_pass_through):
        nodes = roadmap_path(graph, start, goal).nodes
        assert set(must_pass_through) <= set(nodes), (
            f"{start} -> {goal} returned {nodes}. "
            "Wrong answer: the roadmap jumped straight to a build and skipped the concept behind it."
        )

    def test_coverage_link_still_usable_when_it_is_the_only_way(self, graph):
        # derivatives' only forward route to black_scholes_model is its coverage link.
        assert roadmap_path(graph, "derivatives", "black_scholes_model").nodes == [
            "derivatives",
            "black_scholes_model",
        ]


class TestIndependentRoutesAndCredentials:
    """Career routes and credentials are parallel options, not a sequence."""

    OPTIONS = {
        "cpa_license", "frm_certification", "caia_charter", "cfa_charter",
        "search_fund", "quant_route", "academic_doctorate", "charter_route",
    }

    @pytest.mark.parametrize("goal", sorted(OPTIONS))
    def test_no_detour_through_other_options(self, graph, goal):
        allowed = {goal} | ({"charter_route"} if goal == "cfa_charter" else set())
        nodes = roadmap_path(graph, default_start(graph, goal), goal).nodes
        detour = (set(nodes) & self.OPTIONS) - allowed
        assert detour == set(), (
            f"Roadmap to {goal} passes through {sorted(detour)}. "
            "Wrong answer: e.g. 'get the FRM' told the learner to do a search fund and the CPA first."
        )

    def test_cpa_is_reached_from_financial_statement_analysis(self, graph):
        assert roadmap_path(graph, "financial_statement_analysis", "cpa_license").nodes == [
            "financial_statement_analysis",
            "cpa_license",
        ]
