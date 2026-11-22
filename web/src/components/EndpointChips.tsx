import type { NodeInfo, Resolution } from "../api";

type Props = {
  nodes: NodeInfo[];
  start: string;
  goal: string;
  resolution: Resolution | null;
  busy: boolean;
  onChange: (start: string, goal: string) => void;
};

const METHOD_TEXT: Record<string, string> = {
  rule: "rule",
  alias: "name match",
  embedding: "semantic match",
  llm: "AI fallback",
};

function NodeSelect({
  id,
  label,
  value,
  nodes,
  disabled,
  onPick,
}: {
  id: string;
  label: string;
  value: string;
  nodes: NodeInfo[];
  disabled: boolean;
  onPick: (id: string) => void;
}) {
  const types = Array.from(new Set(nodes.map((n) => n.type)));
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} disabled={disabled} onChange={(e) => onPick(e.target.value)}>
        {types.map((t) => (
          <optgroup key={t} label={t}>
            {nodes
              .filter((n) => n.type === t)
              .map((n) => (
                <option key={n.id} value={n.id}>
                  {n.label}
                </option>
              ))}
          </optgroup>
        ))}
      </select>
    </div>
  );
}

export default function EndpointChips({ nodes, start, goal, resolution, busy, onChange }: Props) {
  return (
    <section className="card" aria-labelledby="endpoints-heading">
      <h2 id="endpoints-heading">Where the roadmap runs</h2>
      <div className="endpoints">
        <NodeSelect id="start" label="Start" value={start} nodes={nodes} disabled={busy} onPick={(s) => onChange(s, goal)} />
        <span className="arrow" aria-hidden="true">
          →
        </span>
        <NodeSelect id="goal" label="Goal" value={goal} nodes={nodes} disabled={busy} onPick={(g) => onChange(start, g)} />
      </div>
      {resolution && (
        <p className="muted small">
          Matched by <strong>{METHOD_TEXT[resolution.method] ?? resolution.method}</strong>
          {resolution.start_defaulted && " · no starting point given, so the usual entry point was used"}
          . Wrong match? Pick different topics above.
        </p>
      )}
    </section>
  );
}
