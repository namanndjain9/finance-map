import ReactMarkdown from "react-markdown";

type Props = { text: string; busy: boolean; llm: boolean };

/** The story. Waiting is shown by the run track, so this only appears once text arrives. */
export default function NarrativePanel({ text, busy, llm }: Props) {
  if (!text) return null;
  return (
    <section className="card" aria-labelledby="story-heading">
      <h2 id="story-heading">
        The story <span className="muted small">· {llm ? "written by an AI from the path above" : "plain summary (AI narration is off)"}</span>
      </h2>
      <div className="narrative" aria-live="polite" aria-busy={busy}>
        <ReactMarkdown>{text}</ReactMarkdown>
        {busy && <span className="caret" aria-hidden="true" />}
      </div>
    </section>
  );
}
