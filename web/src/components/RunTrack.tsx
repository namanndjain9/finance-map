import { useState } from "react";
import type { StageId, StageState, Stages } from "../api";

const STATIONS: { id: StageId; label: string; doing: string }[] = [
  { id: "rule", label: "Rule", doing: "Checking for advice requests" },
  { id: "tier1", label: "Names", doing: "Looking for names" },
  { id: "tier2", label: "Meaning", doing: "Comparing meanings" },
  { id: "tier3", label: "AI", doing: "Asking the AI" },
  { id: "roadmap", label: "Path", doing: "Finding the path" },
  { id: "narrative", label: "Story", doing: "Writing the story" },
];

const MARK: Record<string, string> = { done: "✓", passed: "→", skipped: "–", failed: "✕", running: "", pending: "" };
const STATUS_TEXT: Record<string, string> = {
  done: "done",
  passed: "passed on",
  skipped: "skipped",
  failed: "failed",
  running: "in progress",
  pending: "not run",
};

type Props = { stages: Stages; busy: boolean; summary: string };

/** Where the walker stands: the stage running now, else the furthest stage that has reported. */
function walkerIndex(stages: Stages): number {
  let last = 0;
  STATIONS.forEach((s, i) => {
    const st = stages[s.id];
    if (st && st.status !== "skipped") last = i;
  });
  const running = STATIONS.findIndex((s) => stages[s.id]?.status === "running");
  return running !== -1 ? running : last;
}

function Walker({ moving, cheer }: { moving: boolean; cheer: boolean }) {
  return (
    <svg
      className={`walker-figure${moving ? " walking" : ""}${cheer ? " cheer" : ""}`}
      viewBox="0 0 30 44"
      width="30"
      height="44"
      aria-hidden="true"
    >
      <g className="w-body">
        <circle cx="15" cy="7" r="5" />
        <line x1="15" y1="12" x2="15" y2="26" />
        <g className="w-arm w-arm-a">
          <line x1="15" y1="15" x2="15" y2="24" />
        </g>
        <g className="w-arm w-arm-b">
          <line x1="15" y1="15" x2="15" y2="24" />
        </g>
        <g className="w-leg w-leg-a">
          <line x1="15" y1="26" x2="15" y2="40" />
        </g>
        <g className="w-leg w-leg-b">
          <line x1="15" y1="26" x2="15" y2="40" />
        </g>
      </g>
    </svg>
  );
}

export default function RunTrack({ stages, busy, summary }: Props) {
  const [open, setOpen] = useState(false);
  const index = walkerIndex(stages);
  const current = STATIONS[index];
  const state: StageState | undefined = stages[current.id];
  const failed = STATIONS.some((s) => stages[s.id]?.status === "failed");
  const totalMs = Math.max(0, ...STATIONS.map((s) => stages[s.id]?.ms ?? 0));
  const caption = busy ? current.doing : failed ? "Something went wrong" : summary || "Finished";
  const pct = ((index + 0.5) / STATIONS.length) * 100;

  return (
    <section className="card run-track" aria-label="Run progress">
      <div className="track-area">
        <div className="track-line" />
        <div className="track-fill" style={{ width: `calc(${pct}% - ${50 / STATIONS.length}%)` }} />
        <div className="walker" style={{ left: `${pct}%` }}>
          <div className={`bubble${index === 0 ? " edge-left" : index === STATIONS.length - 1 ? " edge-right" : ""}`}>
            {caption}
            {busy && <span className="dots" aria-hidden="true" />}
          </div>
          <Walker moving={busy} cheer={!busy && !failed} />
        </div>
        <ol className="stations">
          {STATIONS.map((s) => {
            const status = stages[s.id]?.status ?? "pending";
            return (
              <li
                key={s.id}
                className={`station st-${status}`}
                title={`${s.label}: ${STATUS_TEXT[status]}${stages[s.id]?.detail ? ` — ${stages[s.id]?.detail}` : ""}`}
              >
                <span className="dot-mark">{MARK[status]}</span>
                <span className="station-label">{s.label}</span>
              </li>
            );
          })}
        </ol>
      </div>

      <p className="sr-only" aria-live="polite">
        {busy ? `${current.doing}. ${state?.detail ?? ""}` : caption}
      </p>

      {!busy && (
        <button type="button" className="run-summary" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {summary || "Run finished"} · {(totalMs / 1000).toFixed(1)} s · {open ? "hide" : "show"} run details
        </button>
      )}
      {!busy && open && (
        <ul className="run-details small">
          {STATIONS.map((s) => {
            const st = stages[s.id];
            return (
              <li key={s.id} className={`st-${st?.status ?? "pending"}`}>
                <strong>{s.label}</strong> <span className="muted">{STATUS_TEXT[st?.status ?? "pending"]}</span>
                {st?.detail && <span> — {st.detail}</span>}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
