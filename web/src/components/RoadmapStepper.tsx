import type { Roadmap, Step } from "../api";

// Same wording as src/ai/narrator.py RELATION, so the list and the story agree.
const RELATION: Record<string, (a: string, b: string) => string> = {
  precedes: (a, b) => `${a} comes before ${b}`,
  requires: (a, b) => `${a} requires ${b}`,
  "flows-to": (a, b) => `${a} flows into ${b}`,
  prices: (a, b) => `${a} is used to price ${b}`,
  "exercised-by": (a, b) => `${a} is exercised through ${b}`,
  "permitted-as-study": (a, b) => `${a} is a permitted study activity under ${b}`,
  "belongs-to": (a, b) => `${a} belongs to ${b}`,
};

function relationship(prev: Step, step: Step): string | null {
  if (!step.via_edge) return null;
  const say = RELATION[step.via_edge] ?? ((a: string, b: string) => `${a} is linked to ${b}`);
  // The sentence always follows the graph edge's real direction.
  return step.direction === "backward" ? say(step.label, prev.label) : say(prev.label, step.label);
}

export default function RoadmapStepper({ roadmap, onFocus }: { roadmap: Roadmap; onFocus: (node: string) => void }) {
  return (
    <section className="card" aria-labelledby="steps-heading">
      <h2 id="steps-heading">
        Roadmap{" "}
        <span className="muted small">
          · {roadmap.steps.length} {roadmap.steps.length === 1 ? "step" : "steps"}
        </span>
      </h2>
      {!roadmap.directed && (
        <p className="muted small">
          No one-way route exists between these topics, so some steps follow a link against its direction. Those
          steps have a dashed line and are marked ↩.
        </p>
      )}
      <ol className="steps">
        {roadmap.steps.map((s, i) => {
          const rel = i > 0 ? relationship(roadmap.steps[i - 1], s) : null;
          return (
            <li key={s.node} className={s.direction === "backward" ? "backward" : ""}>
              <button type="button" className="step-head" onClick={() => onFocus(s.node)}>
                <span className="num">{i + 1}</span>
                <span className="step-title">{s.label}</span>
                <span className={`badge t-${s.type}`}>{s.type}</span>
              </button>
              {rel && (
                <p className="via small">
                  {s.direction === "backward" ? "↩ " : "↓ "}
                  {rel}
                </p>
              )}
              <p className="desc">{s.description}</p>
              {s.practice_builds.length > 0 && (
                <p className="small">
                  <strong>Practice:</strong> {s.practice_builds.map((b) => b.replace(/_/g, " ")).join(", ")}
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
