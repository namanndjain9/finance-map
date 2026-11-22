# Finance Map

Finance Map is a small, queryable knowledge graph for exploring finance concepts, valuation relationships, learning activities, and model-building coverage. Its source of truth is [`graph.yaml`](graph.yaml); Python code validates and queries the graph, and exports a Mermaid topology and a question-and-answer card deck.

The graph is a learning aid, not a complete syllabus, investment recommendation, legal guide, or evidence of professional authorization or investment performance. In particular, registration requirements depend on the activity and jurisdiction.

## Quick start

Requires Python 3. From the repository root, create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Try a query

The value-chain query finds both paths from free cash flow to per-share value:

```powershell
.\.venv\Scripts\python.exe -c "from src.builder import load_graph; from src.queries import value_chain; print(value_chain(load_graph('graph.yaml')))"
```

Expected routes:

```text
free_cash_flow -> discount_rate -> enterprise_value -> net_debt -> equity_value -> per_share_value
free_cash_flow -> discount_rate -> equity_value -> per_share_value
```

The first route values unlevered cash flow at enterprise value and then bridges to equity value by accounting for net debt. The second route represents discounting cash flow to equity directly. In a real valuation, cash-flow and discount-rate definitions must be consistent.

## Project contents

- [`graph.yaml`](graph.yaml) — graph nodes and typed edges.
- [`src/schema.py`](src/schema.py) — closed node- and edge-type vocabularies.
- [`src/builder.py`](src/builder.py) — graph loading and schema validation.
- [`src/queries.py`](src/queries.py) — value-chain, study-scope, registration, and build-coverage queries.
- [`src/integrity.py`](src/integrity.py) — orphan, edge-vocabulary, and reachability checks.
- [`src/export.py`](src/export.py) — Mermaid and Markdown card-deck exporters.
- [`tests/`](tests/) — pytest checks for integrity, expected query answers, and the AI roadmap layer.
- [`src/ai/`](src/ai/), [`src/api.py`](src/api.py), [`web/`](web/), [`evals/`](evals/) — question-to-roadmap resolver, narrator, FastAPI backend, React frontend, and eval set.
- [`exports/`](exports/) — generated topology and card-deck files.
- [`docs/`](docs/) — learning notes, build instructions, self-check evidence, teach-back, and source map.

## Regenerate exports

There is no command-line export wrapper. Run the export functions directly:

```powershell
.\.venv\Scripts\python.exe -c "from src.builder import load_graph; from src.export import export_mermaid, export_cards; graph = load_graph('graph.yaml'); export_mermaid(graph, 'exports/topology.mmd'); export_cards(graph, 'exports/cards.md')"
```

See [`docs/02-build.md`](docs/02-build.md) for the detailed build instructions and worked valuation example, and [`docs/05-source-map.md`](docs/05-source-map.md) for the reference anchors and their limits.

## Ask for a roadmap (AI + web UI)

Type a question such as *"I know free cash flow, how do I get to pricing a call option?"* and get a step-by-step path through the graph plus a short written walkthrough. The path itself is computed by ordinary graph code; the AI only helps (a) pick the two end points when the question does not name them and (b) write the narrative.

How a question is mapped to two nodes, cheapest first:

1. **Rule** – requests for personal advice or stock picks are declined outright.
2. **Name match** – labels and aliases in `graph.yaml` (e.g. "WACC", "T-bill", "Black-Scholes").
3. **Semantic match** – a local sentence-transformers model compares the question with each node's description.
4. **AI fallback** – Google Gemini (free tier), constrained to answer with ids that exist in the graph.

The roadmap never routes through activities that require registration. Questions about doing that kind of work get an explanation and the study-safe alternatives instead of a plan. Every answer ends with the learning-aid disclaimer, added by code.

### Run it

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
copy .env.example .env      # add a free Gemini key from https://aistudio.google.com (optional)
.\.venv\Scripts\python.exe -m uvicorn src.api:app --reload
```

In a second terminal:

```powershell
cd web
npm install
npm run dev                 # open http://localhost:5173
```

Without a Gemini key the app still works: name and semantic matching run as usual, and narratives are a plain template summary instead of AI-written prose. Free-tier note: Google may use prompts sent to the free Gemini tier to improve its products. The app sends only the question and graph content.

### Evaluate it

```powershell
.\.venv\Scripts\python.exe -m evals.run                      # resolver accuracy on evals/cases.yaml
.\.venv\Scripts\python.exe -m evals.run --llm --narrate --judge   # also the Gemini fallback, narrative grounding and a judge rubric
```

`evals/cases.yaml` holds the questions with their acceptable start/goal nodes. Cases tagged `tier: alias` run in `pytest` with no model at all. See [`docs/03-self-check.md`](docs/03-self-check.md) for the latest numbers.

## Make the demo video

`demo/` builds a ~90-second walkthrough video with no manual editing. It records the real app with an animated narrator mascot, adds a natural voice-over and original background music, and mixes everything with ffmpeg.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-demo.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m demo.make          # needs ffmpeg on PATH; takes several minutes
```

It writes three files to `demo/out/`:

- `finance-map-demo.mp4`
- `finance-map-demo-captioned.mp4`, the same video with burned-in subtitles
- `finance-map-demo.srt`

To change the video, edit `demo/script.yaml`, which holds the narration, the on-screen captions, each scene's actions, the voice and the music level, then run the command again.

- **Server.** The build starts its own server on port 8001, with the AI off so the result is the same every time. Add `--ai` to use Gemini.
- **Voice.** The voice comes from the free `edge-tts` service, which receives only the narration text.
- **Music.** The music is synthesised by `demo/music.py`, so there are no licences involved.
