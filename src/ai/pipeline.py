"""One entry point for the whole feature: question -> resolution -> roadmap -> narrative.

`Pipeline.events(question)` is a generator of JSON-serialisable dicts (used by the SSE API);
`Pipeline.ask(question)` collects them into one result (used by evals and scripts).

Every run is logged stage by stage (see src/ai/runlog.py), and each stage is also sent to
the UI as a `progress` event so it can show where the run is.
"""

import queue
import threading
from typing import Iterator

import networkx as nx

from src.ai.config import GRAPH_PATH
from src.ai.embed_index import try_create_index
from src.ai.llm import LLMClient, LLMError, try_create_llm
from src.ai.narrator import closing_notes, narrate
from src.ai.resolver import Resolution, ResolutionError, Resolver, ResolverConfig
from src.ai.runlog import RunLog
from src.builder import load_graph
from src.queries import (
    RegisteredActivityError,
    RoadmapError,
    registered_activities,
    roadmap_path,
    study_scope,
)

ETHICS_ENTRY = "ethics_and_professional_standards"
SOURCE_TEXT = {"ai": "the AI", "template": "the plain summary", "fallback": "the plain summary (AI failed)"}


class Pipeline:
    def __init__(self, G: nx.DiGraph, resolver: Resolver, llm: LLMClient | None):
        self.G, self.resolver, self.llm = G, resolver, llm

    @classmethod
    def build(
        cls,
        graph_path=GRAPH_PATH,
        use_embeddings: bool = True,
        use_llm: bool = True,
        config: ResolverConfig | None = None,
    ) -> "Pipeline":
        G = load_graph(graph_path)
        index = try_create_index(G) if use_embeddings else None
        llm = try_create_llm() if use_llm else None
        return cls(G, Resolver(G, index=index, llm=llm, config=config), llm)

    @property
    def capabilities(self) -> dict:
        return {"embeddings": self.resolver.index is not None, "llm": self.llm is not None}

    def label(self, node: str | None) -> str | None:
        return self.G.nodes[node]["label"] if node else None

    # ------------------------------------------------------------------ stream
    def events(self, question: str) -> Iterator[dict]:
        run = RunLog(question)
        try:
            yield from self._events(question, run)
        except Exception:
            run.outcome = "crashed"
            run.log.exception("[run %s] crashed", run.run_id)
            raise
        finally:
            run.finish()

    def roadmap_events(self, question: str, start: str, goal: str) -> Iterator[dict]:
        """Roadmap + narrative for known endpoints (used when the learner overrides them)."""
        run = RunLog(f"[override] {start} -> {goal}")
        try:
            yield from self._roadmap_events(question, start, goal, run)
        except Exception:
            run.outcome = "crashed"
            run.log.exception("[run %s] crashed", run.run_id)
            raise
        finally:
            run.finish()

    def _resolve_live(self, question: str, run: RunLog, box: dict) -> Iterator[dict]:
        """Resolve in a worker thread and yield its progress as it happens (tier 3 can be slow)."""
        events: queue.Queue = queue.Queue()

        def trace(stage: str, status: str, detail: str = "", debug: str | None = None) -> None:
            events.put(run.step(stage, status, detail, debug))

        def work() -> None:
            try:
                box["resolution"] = self.resolver.resolve(question, trace=trace)
            except Exception as exc:  # handed back to the generator thread
                box["error"] = exc
            finally:
                events.put(None)

        threading.Thread(target=work, name=f"resolve-{run.run_id}", daemon=True).start()
        while (event := events.get()) is not None:
            yield event

    def _events(self, question: str, run: RunLog) -> Iterator[dict]:
        box: dict = {}
        yield from self._resolve_live(question, run, box)

        error = box.get("error")
        if error is not None:
            if isinstance(error, ResolutionError):
                code, message = "no_match", str(error)
            elif isinstance(error, LLMError):
                code = "llm_failed"
                text = str(error)
                if "429" in text or "RESOURCE_EXHAUSTED" in text:
                    why = "has used up its free-tier quota for now"
                elif "504" in text or "DEADLINE" in text or "timeout" in text.lower():
                    why = "did not answer in time"
                else:
                    why = "is unavailable right now"
                message = (
                    f"The AI fallback {why}, and the other checks could not match your question. "
                    "Try naming the topics directly, e.g. 'from free cash flow to the Black-Scholes model'."
                )
            else:
                code, message = "resolver_failed", str(error)
            run.outcome = f"{code}: {error}"[:200]
            yield run.step("roadmap", "skipped", "no topics to connect")
            yield run.step("narrative", "skipped", "no roadmap")
            yield {"event": "error", "code": code, "message": message}
            yield {"event": "done"}
            return

        resolution: Resolution = box["resolution"]
        yield {"event": "resolution", "resolution": self._resolution_payload(resolution)}

        if resolution.out_of_scope:
            run.outcome = f"out_of_scope (by {resolution.method})"
            yield run.step("roadmap", "skipped", "question is out of scope")
            yield run.step("narrative", "skipped", "question is out of scope")
            yield {
                "event": "out_of_scope",
                "message": "That is outside what this graph covers. It maps finance concepts, not "
                "personal advice or stock picks. Try asking how to get from one concept to another.",
                "reason": resolution.reason,
            }
            yield {"event": "done"}
            return

        yield from self._roadmap_events(question, resolution.start, resolution.goal, run,
                                        method=resolution.method)

    def _roadmap_events(
        self, question: str, start: str, goal: str, run: RunLog, method: str = "override"
    ) -> Iterator[dict]:
        yield run.step("roadmap", "running", f"{start} -> {goal}")
        try:
            roadmap = roadmap_path(self.G, start, goal)
        except RegisteredActivityError as exc:
            yield run.step("roadmap", "done", f"{exc.activity} needs registration; showing the rules instead")
            run.outcome = f"regulated ({exc.activity})"
            yield from self._regulated_events(exc.activity, run)
            return
        except RoadmapError as exc:
            yield run.step("roadmap", "failed", str(exc))
            yield run.step("narrative", "skipped", "no roadmap")
            run.outcome = "no_path"
            yield {"event": "error", "code": "no_path", "message": str(exc)}
            yield {"event": "done"}
            return

        data = roadmap.to_dict()
        shape = "forward links only" if roadmap.directed else "uses some backward links"
        yield run.step("roadmap", "done", f"{len(roadmap.steps)} steps, {shape}",
                       debug=" > ".join(roadmap.nodes))
        yield {"event": "roadmap", "roadmap": data}

        pending: list[dict] = []
        source = {"value": "ai"}

        def report(src: str, detail: str) -> None:
            source["value"] = src
            pending.append(run.step("narrative", "running", detail))

        chars = 0
        for chunk in narrate(question, data, self.llm, report):
            yield from pending
            pending.clear()
            chars += len(chunk)
            yield {"event": "narrative", "text": chunk}
        yield from pending
        yield {"event": "narrative", "text": "\n\n" + closing_notes(data, self.G)}
        written_by = SOURCE_TEXT.get(source["value"], source["value"])
        yield run.step("narrative", "done", f"{chars} characters, written by {written_by}")
        run.outcome = f"ok by {method}: {start} -> {goal}, {len(roadmap.steps)} steps, story by {written_by}"
        yield {"event": "done"}

    def _regulated_events(self, activity: str, run: RunLog) -> Iterator[dict]:
        items = sorted(
            v for _, v, d in self.G.out_edges(activity, data=True) if d.get("type") == "requires-registration"
        )
        yield {
            "event": "regulated",
            "activity": activity,
            "regulatory_items": items,
            "study_alternatives": study_scope(self.G),
        }
        yield run.step("narrative", "running", "fixed explanation for regulated work (no AI)")
        text = (
            f"**{self.label(activity)}** is a regulated activity that typically requires registration or "
            "licensing, so this graph treats it as outside study scope."
        )
        alternatives = ", ".join(self.label(n).lower() for n in study_scope(self.G))
        text += f" Within study scope you can explore: {alternatives}."
        if items:
            try:
                roadmap = roadmap_path(self.G, ETHICS_ENTRY, items[0])
                yield {"event": "roadmap", "roadmap": roadmap.to_dict()}
                text += (
                    f" To understand the rules behind it, the roadmap shows the ethics and regulation "
                    f"topics that lead to {self.label(items[0])}."
                )
            except RoadmapError:
                pass
        yield {"event": "narrative", "text": text}
        yield {"event": "narrative", "text": "\n\n" + closing_notes({"regulated_nearby": []}, self.G)}
        yield run.step("narrative", "done", "explanation and study-scope alternatives shown")
        yield {"event": "done"}

    def _resolution_payload(self, r: Resolution) -> dict:
        payload = r.to_dict()
        payload["start_label"] = self.label(r.start)
        payload["goal_label"] = self.label(r.goal)
        payload["regulated"] = [n for n in (r.start, r.goal) if n in set(registered_activities(self.G))]
        return payload

    # ------------------------------------------------------------------ collect
    def ask(self, question: str) -> dict:
        result: dict = {"status": "ok", "narrative": "", "roadmap": None, "resolution": None, "trace": []}
        for event in self.events(question):
            kind = event["event"]
            if kind == "progress":
                result["trace"].append(event)
            elif kind == "resolution":
                result["resolution"] = event["resolution"]
            elif kind == "roadmap":
                result["roadmap"] = event["roadmap"]
            elif kind == "narrative":
                result["narrative"] += event["text"]
            elif kind == "regulated":
                result["status"] = "regulated"
                result["regulated"] = event
            elif kind == "out_of_scope":
                result["status"] = "out_of_scope"
                result["message"] = event["message"]
            elif kind == "error":
                result["status"] = event["code"]
                result["message"] = event["message"]
        return result
