"""HTTP API tests. The pipeline is built without embeddings or an LLM, so no model or network is used."""

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from src.ai.config import DISCLAIMER  # noqa: E402
from src.ai.pipeline import Pipeline  # noqa: E402


@pytest.fixture(scope="module")
def client():
    import src.api as api

    original = Pipeline.build.__func__
    api.Pipeline.build = classmethod(lambda cls, *a, **k: original(cls, use_embeddings=False, use_llm=False))
    try:
        with TestClient(api.app) as c:
            yield c
    finally:
        api.Pipeline.build = classmethod(original)


def sse(response) -> list[dict]:
    frames = [f for f in response.text.split("\n\n") if f.strip()]
    return [json.loads(f.removeprefix("data: ")) for f in frames]


def test_status_reports_no_optional_parts(client):
    body = client.get("/api/status").json()
    assert body["embeddings"] is False and body["llm"] is False


def test_graph_endpoint_exposes_descriptions(client):
    body = client.get("/api/graph").json()
    assert len(body["nodes"]) == 62 and len(body["edges"]) == 78
    assert all(n["description"] and n["label"] for n in body["nodes"])


def test_roadmap_endpoint(client):
    r = client.post("/api/roadmap", json={"start": "fixed_income", "goal": "derivatives"})
    assert r.status_code == 200
    assert [s["node"] for s in r.json()["steps"]] == ["fixed_income", "derivatives"]


def test_roadmap_refuses_registered_activity(client):
    r = client.post("/api/roadmap", json={"start": "corporate_finance", "goal": "investment_advisory"})
    assert r.status_code == 422 and "registration" in r.json()["detail"]


def test_roadmap_unknown_node_is_404(client):
    assert client.post("/api/roadmap", json={"start": "nope", "goal": "derivatives"}).status_code == 404


def test_resolve_endpoint(client):
    body = client.post("/api/resolve", json={"question": "How do I learn Black-Scholes?"}).json()
    assert body["goal"] == "black_scholes_model" and body["goal_label"] == "Black-Scholes model"


def test_resolve_unmatched_is_422(client):
    assert client.post("/api/resolve", json={"question": "xyzzy plugh"}).status_code == 422


def test_question_length_is_validated(client):
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/ask", json={"question": "x" * 501}).status_code == 422


def test_ask_streams_resolution_roadmap_narrative_done(client):
    r = client.post("/api/ask", json={"question": "How do I get from free cash flow to per share value?"})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = sse(r)
    kinds = [e["event"] for e in events if e["event"] != "progress"]
    assert kinds[:2] == ["resolution", "roadmap"] and kinds[-1] == "done"
    assert any(e["event"] == "progress" for e in events), "Wrong answer: the UI gets no progress to animate."
    assert DISCLAIMER in "".join(e["text"] for e in events if e["event"] == "narrative")


def test_ask_advice_request_is_out_of_scope(client):
    kinds = [e["event"] for e in sse(client.post("/api/ask", json={"question": "Which stock should I buy tomorrow?"}))]
    assert "out_of_scope" in kinds and "roadmap" not in kinds


def test_narrate_override(client):
    events = sse(client.post("/api/narrate", json={"question": "q", "start": "fixed_income", "goal": "derivatives"}))
    kinds = [e["event"] for e in events if e["event"] != "progress"]
    assert kinds[0] == "roadmap" and kinds[-1] == "done"
