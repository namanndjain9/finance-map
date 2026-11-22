import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getJson, streamPost } from "./api";
import type { EdgeInfo, NodeInfo, Resolution, Roadmap, Stages, Status, StreamEvent } from "./api";
import QuestionBox from "./components/QuestionBox";
import RunTrack from "./components/RunTrack";
import EndpointChips from "./components/EndpointChips";
import RoadmapStepper from "./components/RoadmapStepper";
import NarrativePanel from "./components/NarrativePanel";
import GraphView from "./components/GraphView";

type Notice = { kind: "info" | "error" | "regulated"; message: string };
type Endpoints = { start: string; goal: string };

const METHOD_TEXT: Record<string, string> = {
  rule: "the advice rule",
  alias: "name match",
  embedding: "semantic match",
  llm: "the AI",
};

/** One-line outcome shown in the run track once the run has finished. */
function runSummary(stages: Stages, resolution: Resolution | null, notice: Notice | null): string {
  if (notice?.kind === "error") return "No roadmap";
  if (notice?.kind === "regulated") return "Regulated work: showing the rules instead";
  if (!stages.tier1 && stages.roadmap) return "Roadmap for your chosen topics";
  if (!resolution) return "";
  if (resolution.out_of_scope) return `Out of scope (${METHOD_TEXT[resolution.method] ?? resolution.method})`;
  return `Matched by ${METHOD_TEXT[resolution.method] ?? resolution.method}`;
}

export default function App() {
  const [nodes, setNodes] = useState<NodeInfo[]>([]);
  const [edges, setEdges] = useState<EdgeInfo[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [question, setQuestion] = useState("");
  const [resolution, setResolution] = useState<Resolution | null>(null);
  const [endpoints, setEndpoints] = useState<Endpoints | null>(null);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [narrative, setNarrative] = useState("");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState<string | null>(null);
  const [stages, setStages] = useState<Stages>({});
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    Promise.all([getJson<{ nodes: NodeInfo[]; edges: EdgeInfo[] }>("/api/graph"), getJson<Status>("/api/status")])
      .then(([g, s]) => {
        setNodes(g.nodes);
        setEdges(g.edges);
        setStatus(s);
      })
      .catch(() =>
        setNotice({ kind: "error", message: "Cannot reach the API. Start it with: uvicorn src.api:app --reload" }),
      );
  }, []);

  const handle = useCallback((e: StreamEvent) => {
    switch (e.event) {
      case "progress":
        setStages((prev) => ({ ...prev, [e.stage]: { status: e.status, detail: e.detail, ms: e.ms } }));
        break;
      case "resolution":
        setResolution(e.resolution);
        if (e.resolution.start && e.resolution.goal) setEndpoints({ start: e.resolution.start, goal: e.resolution.goal });
        break;
      case "roadmap":
        setRoadmap(e.roadmap);
        setEndpoints({ start: e.roadmap.start, goal: e.roadmap.goal });
        break;
      case "narrative":
        setNarrative((prev) => prev + e.text);
        break;
      case "regulated":
        setNotice({
          kind: "regulated",
          message: "This is regulated work, so it is outside the study roadmap. Here is what you can explore instead.",
        });
        break;
      case "out_of_scope":
        setNotice({ kind: "info", message: e.message });
        break;
      case "error":
        setNotice({ kind: "error", message: e.message });
        break;
      case "done":
        break;
    }
  }, []);

  const run = useCallback(
    async (path: string, body: unknown) => {
      abort.current?.abort();
      const ac = new AbortController();
      abort.current = ac;
      setBusy(true);
      try {
        await streamPost(path, body, handle, ac.signal);
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          setNotice({ kind: "error", message: err instanceof Error ? err.message : String(err) });
        }
      } finally {
        if (abort.current === ac) setBusy(false);
      }
    },
    [handle],
  );

  function clearAnswer() {
    setRoadmap(null);
    setNarrative("");
    setNotice(null);
    setFocus(null);
    setStages({});
  }

  function ask(q: string) {
    clearAnswer();
    setResolution(null);
    setEndpoints(null);
    setQuestion(q);
    void run("/api/ask", { question: q });
  }

  function override(start: string, goal: string) {
    clearAnswer();
    setEndpoints({ start, goal });
    void run("/api/narrate", { question: question || "Roadmap between the chosen topics", start, goal });
  }

  const path = useMemo(() => (roadmap ? roadmap.steps.map((s) => s.node) : []), [roadmap]);

  return (
    <div className="page">
      <header>
        <h1>Finance Map</h1>
        <p className="muted">Ask a question and get a roadmap through the finance knowledge graph. A learning aid, not advice.</p>
        {status && (
          <p className="small muted" aria-label="Backend capabilities">
            Matching: name match{status.embeddings ? " + semantic" : ""}
            {status.llm ? ` + AI fallback (${status.model})` : " · AI off, plain summaries"}
          </p>
        )}
      </header>

      <QuestionBox busy={busy} onAsk={ask} />

      {notice && (
        <div className={`notice ${notice.kind}`} role={notice.kind === "error" ? "alert" : "status"}>
          {notice.message}
        </div>
      )}

      <div className="layout">
        <div className="col">
          {(busy || Object.keys(stages).length > 0) && (
            <RunTrack stages={stages} busy={busy} summary={runSummary(stages, resolution, notice)} />
          )}
          {endpoints && nodes.length > 0 && (
            <EndpointChips
              nodes={nodes}
              start={endpoints.start}
              goal={endpoints.goal}
              resolution={resolution}
              busy={busy}
              onChange={override}
            />
          )}
          {roadmap && <RoadmapStepper roadmap={roadmap} onFocus={setFocus} />}
          <NarrativePanel text={narrative} busy={busy} llm={status?.llm ?? false} />
        </div>
        <div className="col sticky">
          <GraphView nodes={nodes} edges={edges} path={path} focus={focus} />
        </div>
      </div>

      <footer className="small muted">
        This roadmap is a learning aid built from a study graph. It is not investment, legal, or registration advice.
      </footer>
    </div>
  );
}
