"""Resolver tests, fixtures-first. No network, no model: tiers 2/3 use canned stand-ins."""

import pytest

from src.ai.lexicon import build_lexicon, find_mentions
from src.ai.resolver import NONE, ResolutionError, Resolver, ResolverConfig
from src.builder import load_graph


@pytest.fixture(scope="session")
def graph():
    return load_graph("graph.yaml")


class CannedIndex:
    """Stands in for NodeIndex: returns fixed (node, cosine) candidates."""

    def __init__(self, candidates):
        self.candidates = candidates

    def top_k(self, question, k=8):
        return self.candidates[:k]


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def generate_json(self, system, prompt, schema):
        self.calls.append((system, prompt, schema))
        return self.reply

    def stream_text(self, system, prompt):
        yield "unused"


# ---------------------------------------------------------------- lexicon
class TestLexicon:
    def test_acronym_and_plural_resolve(self, graph):
        lex = build_lexicon(graph)
        assert lex["wacc"] == "discount_rate"
        assert lex["t bill"] == "treasury_bill"
        assert lex["bonds"] == "fixed_income", "'bonds' is the fixed_income alias, not corporate_bond"
        assert lex["bond"] == "corporate_bond"

    def test_longest_match_wins(self, graph):
        mentions = find_mentions("price a call option with the black-scholes model", build_lexicon(graph))
        assert [m.node for m in mentions] == ["call_option", "black_scholes_model"], (
            "Wrong answer: 'black-scholes model' was split or 'option' matched on its own."
        )


# ---------------------------------------------------------------- tier 1
TIER1 = [
    ("How do I get from free cash flow to per share value?", "free_cash_flow", "per_share_value", "cues"),
    ("I know DCF and want to learn Black-Scholes", "dcf", "black_scholes_model", "cues"),
    ("How do I price a call option starting from free cash flow?", "free_cash_flow", "call_option", "cues"),
    ("T-bill to CAPM calculator", "treasury_bill", "capm_calculator", "cues"),
    ("free cash flow, enterprise value", "free_cash_flow", "enterprise_value", "order"),
]


class TestTier1Aliases:
    @pytest.mark.parametrize("question,start,goal,how", TIER1)
    def test_two_mentions(self, graph, question, start, goal, how):
        r = Resolver(graph).resolve(question)
        assert (r.start, r.goal, r.method, r.direction) == (start, goal, "alias", how), (
            f"{question!r} -> {r.start} -> {r.goal} via {r.direction}. "
            "Wrong answer: direction read backwards or a mention was missed."
        )

    def test_goal_only_defaults_start(self, graph):
        r = Resolver(graph).resolve("How do I learn Black-Scholes?")
        assert (r.start, r.goal) == ("corporate_finance", "black_scholes_model")
        assert r.start_defaulted and r.direction == "goal_only"

    @pytest.mark.parametrize("question", [
        "Which stock should I buy tomorrow?",
        "Should I sell my bonds now?",
        "What stocks to invest in this year",
        "any good stock tips?",
        "Is Tesla stock going to go up next week?",
        "Will bitcoin crash tomorrow?",
    ])
    def test_advice_requests_are_out_of_scope_without_llm(self, graph, question):
        r = Resolver(graph).resolve(question)
        assert r.out_of_scope and r.method == "rule", (
            f"{question!r} resolved to {r.goal}. "
            "Wrong answer: a request for a stock pick was answered with a study roadmap."
        )

    def test_learning_question_about_stocks_is_not_advice(self, graph):
        r = Resolver(graph).resolve("How do I value common stock?")
        assert not r.out_of_scope and r.goal == "equity"

    def test_explaining_price_moves_is_not_advice(self, graph):
        r = Resolver(graph).resolve("Does market efficiency explain why prices go up and down?")
        assert not r.out_of_scope, "Wrong answer: a learning question about price behaviour was refused as advice."

    def test_no_llm_no_match_raises(self, graph):
        with pytest.raises(ResolutionError):
            Resolver(graph).resolve("what is the meaning of life")

    def test_empty_question_raises(self, graph):
        with pytest.raises(ResolutionError):
            Resolver(graph).resolve("   ")

    def test_only_start_cue_falls_through(self, graph):
        """'I know DCF, what next?' names no goal: tier 1 must not invent one."""
        with pytest.raises(ResolutionError):
            Resolver(graph).resolve("I already know DCF, what next?")


# ---------------------------------------------------------------- tier 2
class TestTier2Embeddings:
    def test_two_candidates_ordered_by_graph(self, graph):
        index = CannedIndex([("derivatives", 0.71), ("fixed_income", 0.66), ("equity", 0.20)])
        r = Resolver(graph, index=index).resolve("which of these two topics comes first in the curriculum")
        assert (r.start, r.goal, r.method, r.direction) == ("fixed_income", "derivatives", "embedding", "graph"), (
            "Wrong answer: embedding order used instead of the graph's learning order."
        )

    def test_single_candidate_is_goal_only(self, graph):
        index = CannedIndex([("market_efficiency", 0.70), ("economics", 0.30)])
        r = Resolver(graph, index=index).resolve("can anyone beat the market consistently")
        assert r.goal == "market_efficiency" and r.direction == "goal_only"

    def test_cyclic_pair_is_ambiguous_without_llm(self, graph):
        index = CannedIndex([("call_option", 0.70), ("black_scholes_model", 0.65), ("equity", 0.2)])
        with pytest.raises(ResolutionError):
            Resolver(graph, index=index).resolve("option pricing")

    def test_small_margin_is_not_accepted(self, graph):
        index = CannedIndex([("equity", 0.50), ("fixed_income", 0.45)])
        with pytest.raises(ResolutionError):
            Resolver(graph, index=index, config=ResolverConfig(tau=0.5)).resolve("securities")

    def test_below_floor_reports_no_match(self, graph):
        index = CannedIndex([("equity", 0.10)])
        with pytest.raises(ResolutionError, match="Nothing in the graph"):
            Resolver(graph, index=index).resolve("best pizza in town")

    def test_confident_embedding_never_calls_llm(self, graph):
        llm = FakeLLM({})
        index = CannedIndex([("market_efficiency", 0.70), ("economics", 0.30)])
        Resolver(graph, index=index, llm=llm).resolve("can anyone beat the market consistently")
        assert llm.calls == [], "Wrong answer: paid for an LLM call the embedding already answered."


# ---------------------------------------------------------------- tier 3
class TestTier3LLM:
    def test_llm_result_is_used_and_schema_is_enum_of_node_ids(self, graph):
        llm = FakeLLM({"start": NONE, "goal": "black_scholes_model", "out_of_scope": False, "reason": "x"})
        r = Resolver(graph, llm=llm).resolve("What formula prices European options?")
        assert (r.method, r.goal, r.start) == ("llm", "black_scholes_model", "corporate_finance")
        schema = llm.calls[0][2]
        assert set(schema["properties"]["goal"]["enum"]) == set(graph.nodes()) | {NONE}, (
            "Wrong answer: the model was allowed to answer with an id that is not in the graph."
        )

    def test_hallucinated_id_rejected(self, graph):
        llm = FakeLLM({"start": NONE, "goal": "black_scholes_formula", "out_of_scope": False, "reason": ""})
        with pytest.raises(ResolutionError, match="not a node"):
            Resolver(graph, llm=llm).resolve("What formula prices European options?")

    def test_out_of_scope_flag(self, graph):
        llm = FakeLLM({"start": NONE, "goal": NONE, "out_of_scope": True, "reason": "stock pick"})
        r = Resolver(graph, llm=llm).resolve("Which stock should I buy tomorrow?")
        assert r.out_of_scope and r.goal is None

    def test_start_only_without_goal_asks_for_goal(self, graph):
        llm = FakeLLM({"start": "dcf", "goal": NONE, "out_of_scope": False, "reason": ""})
        with pytest.raises(ResolutionError, match="goal"):
            Resolver(graph, llm=llm).resolve("I already know DCF, what next?")

    def test_llm_used_when_embeddings_unsure(self, graph):
        llm = FakeLLM({"start": "dcf", "goal": "lbo_model", "out_of_scope": False, "reason": ""})
        index = CannedIndex([("dcf", 0.5), ("lbo_model", 0.46), ("equity", 0.45)])
        r = Resolver(graph, index=index, llm=llm).resolve("valuation then buyouts")
        assert (r.start, r.goal, r.method) == ("dcf", "lbo_model", "llm")
