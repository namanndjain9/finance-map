"""FastAPI backend.

    uvicorn src.api:app --reload          # then `npm run dev` in web/ (proxies /api to :8000)

Endpoints
    GET  /api/status    which optional parts (embeddings, LLM) are available
    GET  /api/graph     nodes + edges for the graph view
    POST /api/resolve   {question}          -> start/goal resolution
    POST /api/roadmap   {start, goal}       -> deterministic roadmap (no AI)
    POST /api/ask       {question}          -> SSE: resolution, roadmap, narrative...
    POST /api/narrate   {question,start,goal} -> SSE: roadmap, narrative (after the learner overrides endpoints)
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.ai.config import DEFAULT_GEMINI_MODEL, REPO_ROOT
from src.ai.pipeline import Pipeline
from src.ai.resolver import ResolutionError
from src.ai.runlog import configure_logging
from src.queries import RegisteredActivityError, RoadmapError, roadmap_path


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class Endpoints(BaseModel):
    start: str
    goal: str


class NarrateBody(Question, Endpoints):
    pass


state: dict[str, Pipeline] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log = configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    pipe = state["pipe"] = Pipeline.build()  # loads the graph and, if installed, the embedding model
    caps = pipe.capabilities
    log.info(
        "finance_map ready: embeddings=%s llm=%s model=%s key=%s",
        "on" if caps["embeddings"] else "off",
        "on" if caps["llm"] else "off",
        os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL,
        "present" if (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")) else "missing",
    )
    yield
    state.clear()


app = FastAPI(title="Finance Map roadmap API", lifespan=lifespan)


def pipe() -> Pipeline:
    return state["pipe"]


def sse(events: Iterator[dict]) -> StreamingResponse:
    def encode():
        for event in events:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        encode(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.get("/api/status")
def status() -> dict:
    return {**pipe().capabilities, "model": os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL}


@app.get("/api/graph")
def graph() -> dict:
    G = pipe().G
    nodes = [
        {
            "id": n,
            "label": d["label"],
            "type": d["type"],
            "description": d["description"],
            "aliases": d["aliases"],
            "landmark": d.get("landmark"),
        }
        for n, d in G.nodes(data=True)
    ]
    edges = [{"source": u, "target": v, "type": d["type"]} for u, v, d in G.edges(data=True)]
    return {"nodes": nodes, "edges": edges}


@app.post("/api/resolve")
def resolve(body: Question) -> dict:
    try:
        return pipe()._resolution_payload(pipe().resolver.resolve(body.question))
    except ResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/roadmap")
def roadmap(body: Endpoints) -> dict:
    try:
        return roadmap_path(pipe().G, body.start, body.goal).to_dict()
    except RegisteredActivityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RoadmapError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/ask")
def ask(body: Question) -> StreamingResponse:
    return sse(pipe().events(body.question))


@app.post("/api/narrate")
def narrate(body: NarrateBody) -> StreamingResponse:
    return sse(pipe().roadmap_events(body.question, body.start, body.goal))


# Serve the built frontend (web/dist) when present, so one process serves everything.
_dist = Path(REPO_ROOT) / "web" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
