import { FormEvent, useState } from "react";

const EXAMPLES = [
  "How do I get from free cash flow to per share value?",
  "I know DCF and want to learn Black-Scholes",
  "How do I learn the CAPM?",
  "How do I start a hedge fund and raise money?",
  "Which stock should I buy tomorrow?",
];

type Props = { busy: boolean; onAsk: (question: string) => void };

export default function QuestionBox({ busy, onAsk }: Props) {
  const [text, setText] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = text.trim();
    if (q) onAsk(q);
  }

  return (
    <section className="card" aria-labelledby="ask-heading">
      <h2 id="ask-heading">What do you want to learn?</h2>
      <form onSubmit={submit} className="ask-row">
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        <input
          id="question"
          type="text"
          value={text}
          maxLength={500}
          placeholder="e.g. I know free cash flow, how do I get to pricing a call option?"
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit" disabled={busy || !text.trim()}>
          {busy ? "Working…" : "Get roadmap"}
        </button>
      </form>
      <div className="chips" aria-label="Example questions">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            className="chip"
            disabled={busy}
            onClick={() => {
              setText(ex);
              onAsk(ex);
            }}
          >
            {ex}
          </button>
        ))}
      </div>
    </section>
  );
}
