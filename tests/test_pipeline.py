"""Pipeline, narrator and grounding tests. A fake LLM stands in for Gemini; nothing touches the network."""

import pytest

from src.ai.config import DISCLAIMER
from src.ai.grounding import grounding_report, recommends_registered_activity
from src.ai.llm import LLMError
from src.ai.narrator import build_prompt, closing_notes, narrate, template_narrative
from src.ai.pipeline import Pipeline
from src.ai.resolver import NONE, Resolver
from src.builder import load_graph
from src.queries import registered_activities, roadmap_path


@pytest.fixture(scope="session")
def graph():
    return load_graph("graph.yaml")


class FakeLLM:
    """JSON replies are canned; text streams the given chunks, optionally failing part-way."""

    def __init__(self, json_reply=None, chunks=("Start with ", "free cash flow."), fail_after=None):
        self.json_reply, self.chunks, self.fail_after = json_reply or {}, chunks, fail_after
        self.prompts = []

    def generate_json(self, system, prompt, schema):
        return self.json_reply

    def stream_text(self, system, prompt):
        self.prompts.append((system, prompt))
        for i, chunk in enumerate(self.chunks):
            if self.fail_after is not None and i >= self.fail_after:
                raise LLMError("boom")
            yield chunk


def make_pipeline(graph, llm=None):
    return Pipeline(graph, Resolver(graph, llm=llm), llm)


# ---------------------------------------------------------------- narrator
class TestNarrator:
    def test_prompt_states_relationships_in_graph_direction(self, graph):
        """A backward step must be phrased with the edge's real orientation."""
        data = roadmap_path(graph, "free_cash_flow", "call_option").to_dict()
        prompt = build_prompt("q", data)
        assert "Call option is exercised through Equity" in prompt, (
            "Wrong answer: the edge call_option -exercised-by-> equity was described backwards."
        )

    def test_template_covers_every_step(self, graph):
        data = roadmap_path(graph, "fixed_income", "derivatives").to_dict()
        text = template_narrative(data)
        assert "Fixed income" in text and "Derivatives" in text

    def test_llm_chunks_are_streamed(self, graph):
        data = roadmap_path(graph, "fixed_income", "derivatives").to_dict()
        assert "".join(narrate("q", data, FakeLLM())) == "Start with free cash flow."

    def test_no_llm_uses_template(self, graph):
        data = roadmap_path(graph, "fixed_income", "derivatives").to_dict()
        assert "".join(narrate("q", data, None)) == template_narrative(data)

    def test_llm_failure_before_output_uses_template(self, graph):
        data = roadmap_path(graph, "fixed_income", "derivatives").to_dict()
        text = "".join(narrate("q", data, FakeLLM(fail_after=0)))
        assert text == template_narrative(data), "Wrong answer: the learner got an error instead of a roadmap."

    def test_llm_failure_mid_stream_appends_template(self, graph):
        data = roadmap_path(graph, "fixed_income", "derivatives").to_dict()
        text = "".join(narrate("q", data, FakeLLM(fail_after=1)))
        assert text.startswith("Start with ") and template_narrative(data) in text

    def test_disclaimer_always_in_closing_notes(self, graph):
        data = roadmap_path(graph, "fixed_income", "derivatives").to_dict()
        assert DISCLAIMER in closing_notes(data, graph)

    def test_registration_caution_added_by_code(self, graph):
        data = roadmap_path(graph, "ethics_and_professional_standards", "advisers_act").to_dict()
        notes = closing_notes(data, graph)
        assert "require registration" in notes and "investment advisory" in notes


# ---------------------------------------------------------------- pipeline
class TestPipeline:
    def test_happy_path_events_and_disclaimer(self, graph):
        events = list(make_pipeline(graph).events("How do I get from free cash flow to per share value?"))
        kinds = [e["event"] for e in events if e["event"] != "progress"]
        assert kinds[0] == "resolution" and kinds[1] == "roadmap" and kinds[-1] == "done"
        text = "".join(e["text"] for e in events if e["event"] == "narrative")
        assert DISCLAIMER in text, "Wrong answer: a roadmap shipped without the learning-aid disclaimer."

    def test_resolution_payload_has_labels(self, graph):
        result = make_pipeline(graph).ask("How do I learn Black-Scholes?")
        assert result["resolution"]["goal_label"] == "Black-Scholes model"
        assert result["roadmap"]["steps"][-1]["node"] == "black_scholes_model"

    def test_advice_request_gets_no_roadmap(self, graph):
        result = make_pipeline(graph).ask("Which stock should I buy tomorrow?")
        assert result["status"] == "out_of_scope" and result["roadmap"] is None

    @pytest.mark.parametrize(
        "question,activity",
        [
            ("How do I start a hedge fund and raise money from investors?", "fund_raising"),
            ("Can I run a broker-dealer from my laptop?", "broker_dealer_execution"),
        ],
    )
    def test_regulated_work_is_explained_not_planned(self, graph, question, activity):
        result = make_pipeline(graph).ask(question)
        assert result["status"] == "regulated" and result["regulated"]["activity"] == activity
        nodes = {s["node"] for s in result["roadmap"]["steps"]}
        assert not nodes & set(registered_activities(graph)), (
            "Wrong answer: the learning roadmap for a regulated question included the regulated activity."
        )
        assert "require registration" in result["narrative"] or "requires registration" in result["narrative"]
        assert DISCLAIMER in result["narrative"]

    def test_unmatched_question_is_a_clean_error(self, graph):
        result = make_pipeline(graph).ask("xyzzy plugh")
        assert result["status"] == "no_match" and "message" in result

    def test_llm_resolution_then_narration(self, graph):
        llm = FakeLLM(json_reply={"start": NONE, "goal": "black_scholes_model", "out_of_scope": False, "reason": ""})
        result = make_pipeline(graph, llm).ask("What formula prices European options?")
        assert result["resolution"]["method"] == "llm"
        assert result["narrative"].startswith("Start with free cash flow.")

    def test_override_endpoints_skip_resolution(self, graph):
        events = list(make_pipeline(graph).roadmap_events("q", "fixed_income", "derivatives"))
        assert [e["event"] for e in events if e["event"] not in ("narrative", "progress")] == ["roadmap", "done"]

    def test_override_with_unknown_node_is_an_error_event(self, graph):
        events = list(make_pipeline(graph).roadmap_events("q", "fixed_income", "not_a_node"))
        assert [e for e in events if e["event"] != "progress"][0]["event"] == "error"


# ---------------------------------------------------------------- grounding
class TestGrounding:
    def test_flags_off_path_concepts(self, graph):
        data = roadmap_path(graph, "fixed_income", "derivatives").to_dict()
        report = grounding_report("Fixed income leads to derivatives, and also to the Black-Scholes model.", data, graph)
        assert report["off_path"] == ["black_scholes_model"] and report["missing"] == []

    def test_reports_unmentioned_steps_and_disclaimer(self, graph):
        data = roadmap_path(graph, "fixed_income", "derivatives").to_dict()
        report = grounding_report("Just derivatives. " + DISCLAIMER, data, graph)
        assert report["missing"] == ["fixed_income"] and report["has_disclaimer"]

    def test_detects_registered_activity_mentions(self, graph):
        registered = set(registered_activities(graph))
        text = "You could try investment advisory next."
        assert recommends_registered_activity(text, graph, registered) == ["investment_advisory"]
