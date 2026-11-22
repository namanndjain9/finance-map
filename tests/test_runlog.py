"""Run logging and progress events, fixtures-first. Fake LLM, canned index: no network, no model."""

import logging

import pytest

from src.ai.llm import LLMError
from src.ai.pipeline import Pipeline
from src.ai.resolver import NONE, ResolutionError, Resolver, ResolverConfig
from src.builder import load_graph


@pytest.fixture(scope="session")
def graph():
    return load_graph("graph.yaml")


class CannedIndex:
    def __init__(self, candidates):
        self.candidates = candidates

    def top_k(self, question, k=8):
        return self.candidates[:k]


class FakeLLM:
    def __init__(self, json_reply=None, fail_stream=False):
        self.json_reply, self.fail_stream = json_reply or {}, fail_stream

    def generate_json(self, system, prompt, schema):
        return self.json_reply

    def stream_text(self, system, prompt):
        if self.fail_stream:
            raise LLMError("quota exceeded")
        yield "A short story."


def progress(events):
    return [(e["stage"], e["status"]) for e in events if e["event"] == "progress"]


def final_status(events):
    """Last reported status per stage, in first-seen order."""
    last: dict[str, str] = {}
    for stage, status in progress(events):
        last[stage] = status
    return list(last.items())


class TestProgressEvents:
    def test_alias_question_stage_by_stage(self, graph):
        """Tier 1 decides, so tiers 2 and 3 are skipped; then the roadmap and narrative run."""
        pipe = Pipeline(graph, Resolver(graph), None)
        events = list(pipe.events("How do I get from free cash flow to per share value?"))
        assert final_status(events) == [
            ("rule", "passed"),
            ("tier1", "done"),
            ("tier2", "skipped"),
            ("tier3", "skipped"),
            ("roadmap", "done"),
            ("narrative", "done"),
        ], (
            f"Got {final_status(events)}. "
            "Wrong answer: the UI would show the walker at the wrong station."
        )

    def test_every_stage_starts_running_before_it_finishes(self, graph):
        pipe = Pipeline(graph, Resolver(graph), None)
        steps = progress(pipe.events("How do I get from free cash flow to per share value?"))
        for stage in ("rule", "tier1", "roadmap", "narrative"):
            assert steps.index((stage, "running")) < max(i for i, s in enumerate(steps) if s[0] == stage)

    def test_progress_arrives_before_the_resolution(self, graph):
        pipe = Pipeline(graph, Resolver(graph), None)
        kinds = [e["event"] for e in pipe.events("How do I learn Black-Scholes?")]
        assert kinds.index("progress") < kinds.index("resolution")

    def test_llm_tier_reports_running_then_done(self, graph):
        llm = FakeLLM({"start": NONE, "goal": "black_scholes_model", "out_of_scope": False, "reason": ""})
        pipe = Pipeline(graph, Resolver(graph, llm=llm), llm)
        steps = progress(pipe.events("What formula prices European options?"))
        tier3 = [status for stage, status in steps if stage == "tier3"]
        assert tier3 == ["running", "done"], f"tier3 went {tier3}"
        assert ("tier1", "passed") in steps and ("tier2", "skipped") in steps

    def test_advice_rule_skips_every_tier(self, graph):
        pipe = Pipeline(graph, Resolver(graph), None)
        assert final_status(list(pipe.events("Which stock should I buy tomorrow?"))) == [
            ("rule", "done"),
            ("tier1", "skipped"),
            ("tier2", "skipped"),
            ("tier3", "skipped"),
            ("roadmap", "skipped"),
            ("narrative", "skipped"),
        ]

    def test_no_match_skips_roadmap_and_narrative(self, graph):
        pipe = Pipeline(graph, Resolver(graph), None)
        status = dict(final_status(list(pipe.events("xyzzy plugh"))))
        assert status["roadmap"] == "skipped" and status["narrative"] == "skipped"

    def test_narrative_fallback_is_reported(self, graph):
        llm = FakeLLM(fail_stream=True)
        pipe = Pipeline(graph, Resolver(graph), llm)
        events = list(pipe.events("How do I get from free cash flow to per share value?"))
        details = [e["detail"] for e in events if e["event"] == "progress" and e["stage"] == "narrative"]
        assert any("quota exceeded" in d for d in details), details
        assert "plain summary (AI failed)" in details[-1]

    def test_llm_tier_failure_is_reported_not_raised(self, graph):
        """A timed-out or failing AI tier must end the run cleanly with a readable message."""

        class FailingLLM(FakeLLM):
            def generate_json(self, system, prompt, schema):
                raise LLMError("Gemini request failed (ReadTimeout, timeout 25s)")

        llm = FailingLLM()
        pipe = Pipeline(graph, Resolver(graph, llm=llm), llm)
        events = list(pipe.events("What is your favourite colour?"))
        assert ("tier3", "failed") in progress(events)
        error = next(e for e in events if e["event"] == "error")
        assert error["code"] == "llm_failed" and "naming the topics directly" in error["message"], error
        assert "did not answer in time" in error["message"], "a timeout must be described as a timeout"
        assert events[-1]["event"] == "done"

    def test_llm_quota_error_is_described_as_quota(self, graph):
        class QuotaLLM(FakeLLM):
            def generate_json(self, system, prompt, schema):
                raise LLMError("Gemini request failed: 429 RESOURCE_EXHAUSTED")

        llm = QuotaLLM()
        events = list(Pipeline(graph, Resolver(graph, llm=llm), llm).events("What is your favourite colour?"))
        error = next(e for e in events if e["event"] == "error")
        assert "quota" in error["message"], error["message"]

    def test_ask_collects_the_trace(self, graph):
        result = Pipeline(graph, Resolver(graph), None).ask("How do I learn Black-Scholes?")
        assert {e["stage"] for e in result["trace"]} == {"rule", "tier1", "tier2", "tier3", "roadmap", "narrative"}


class TestResolverTrace:
    def test_tier2_abstain_reason(self, graph):
        calls = []
        index = CannedIndex([("equity", 0.50), ("fixed_income", 0.45)])
        resolver = Resolver(graph, index=index, config=ResolverConfig(tau=0.5))  # only 0.50 qualifies
        with pytest.raises(ResolutionError):
            resolver.resolve("securities", trace=lambda *a, **k: calls.append(a))
        tier2 = [a for a in calls if a[0] == "tier2"]
        assert tier2[-1][1] == "passed" and "too close to call" in tier2[-1][2], tier2

    def test_trace_is_optional(self, graph):
        assert Resolver(graph).resolve("How do I learn Black-Scholes?").goal == "black_scholes_model"


class TestLogLines:
    def test_run_is_logged_with_id_and_stages(self, graph, caplog):
        caplog.set_level(logging.INFO, logger="finance_map.pipeline")
        Pipeline(graph, Resolver(graph), None).ask("How do I learn Black-Scholes?")
        text = caplog.text
        assert "[run " in text and "question" in text and "finished" in text
        for stage in ("rule", "tier1", "tier2", "tier3", "roadmap", "narrative"):
            assert f"] {stage}" in text, f"no log line for {stage}"

    def test_long_questions_are_truncated_in_the_log(self, graph, caplog):
        caplog.set_level(logging.INFO, logger="finance_map.pipeline")
        Pipeline(graph, Resolver(graph), None).ask("How do I learn Black-Scholes? " + "x" * 500)
        assert "x" * 200 not in caplog.text
