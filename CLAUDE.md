# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small queryable knowledge graph of finance concepts (valuation chain, CFA Level I domains, regulated vs. study-only activities, model-building coverage). `graph.yaml` is the single source of truth; Python code under `src/` loads it into a NetworkX `DiGraph`, validates it, queries it, and exports derived files. It is explicitly a learning aid — not investment, legal, or registration advice — and the docs/cards are careful to say so; preserve that framing when editing text.

## Commands

Windows / PowerShell, run from the repo root (tests and examples load `graph.yaml` by relative path and import via `src.`):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe -m pytest -q                                   # all tests
.\.venv\Scripts\python.exe -m pytest tests/test_queries.py::TestValueChain -q   # one class
.\.venv\Scripts\python.exe -m pytest tests/test_queries.py::TestValueChain::test_levered_path_length -q
```

No lint/format tooling and no CLI. Run queries and exports via `python -c`:

```powershell
# Run a query
.\.venv\Scripts\python.exe -c "from src.builder import load_graph; from src.queries import value_chain; print(value_chain(load_graph('graph.yaml')))"

# Regenerate exports/topology.mmd and exports/cards.md (both are committed generated files)
.\.venv\Scripts\python.exe -c "from src.builder import load_graph; from src.export import export_mermaid, export_cards; graph = load_graph('graph.yaml'); export_mermaid(graph, 'exports/topology.mmd'); export_cards(graph, 'exports/cards.md')"
```

## Architecture

Pipeline: `graph.yaml` → `src/builder.load_graph` (validates against `src/schema.py`) → `nx.DiGraph` → `src/queries.py` / `src/integrity.py` / `src/export.py`.

- **Closed vocabulary.** `schema.NODE_TYPES` and `schema.EDGE_TYPES` are frozensets; `load_graph` raises `SchemaError` on any unknown node/edge type or on an edge referencing an undeclared node. Adding a new type means editing `schema.py` first.
- **Only `type`, `label`, `description`, `aliases` and `landmark` survive loading.** `builder` copies just those node attributes (and `type` for edges); any other YAML keys are silently dropped. `label` defaults to the id with underscores replaced by spaces. Because it's a `DiGraph`, a second edge between the same ordered pair overwrites the first edge's type.
- **Queries are edge-type driven and use hardcoded node IDs:** `value_chain` walks only `flows-to` edges from `free_cash_flow` to `per_share_value`; `study_scope` collects `activity` nodes with `permitted-as-study` → `study_scope`; `registered_activities` collects `activity` nodes with any `requires-registration` edge; `build_coverage` reports landmark-bearing nodes, `domain` nodes, and `instrument` nodes that have no outgoing edge into a `build` node.
- **Mermaid export** groups nodes into `subgraph`s per domain, where membership is a `belongs-to` edge into the domain or any edge from the domain to a non-domain node.
- **Card deck is mostly hardcoded prose** in `export_cards`; only the study-scope answer is computed from the graph. If you change graph content (routes, registered activities, value chain), update the card text in `src/export.py` too.

## Invariants the tests enforce on `graph.yaml`

Any graph edit must keep these true (`tests/`):

- No orphan nodes, and the graph is a single weakly-connected component.
- `value_chain` returns both the 5-edge unlevered route (through `net_debt`) and the 3-edge levered route.
- `investment_advisory`, `broker_dealer_execution`, `fund_raising`, `backtest_marketing` carry `requires-registration` and are never returned by `study_scope`; `study_scope` is non-empty.
- Every landmark node, domain, and instrument links to at least one `build` node (empty `build_coverage`).
- Each of the 10 CFA Level I topic areas maps to its domain node ID (Corporate Issuers → `corporate_finance`).

Tests are written fixtures-first: expected answers are fixed in the test before the query runs, and assertion messages explain what a wrong answer means. Follow that style for new queries.

## Docs that mirror the graph

`docs/03-self-check.md` records the expected output of each query and the last test run; `docs/05-source-map.md` lists every node with its reference anchor (CFA / CORP / INV / HULL / OUTSIDE). When adding or renaming nodes, update the source map, and update the self-check table if query results change.

## AI roadmap layer (question -> roadmap -> narrative)

A learner types a question; the app maps it to a `(start, goal)` pair of nodes, finds a path with plain graph code, and an LLM only *narrates* that path. Everything outside the narration is deterministic and tested.

```text
question -> src/ai/resolver.Resolver -> (start, goal) -> src/queries.roadmap_path -> Roadmap -> src/ai/narrator -> text
```

- **Resolver tiers** (`src/ai/resolver.py`): (0) `ADVICE_PATTERNS` rule -> out of scope, (1) exact label/alias mentions via `src/ai/lexicon.py` (ambiguous strings are dropped, never guessed), (2) cosine similarity on a local sentence-transformers model (`src/ai/embed_index.py`, cached in `.cache/`), (3) LLM constrained by an `enum` of real node ids. `_finalise` re-checks that every returned id is in the graph.
- **`roadmap_path`** (`src/queries.py`): forward edges first, then backward edges at a x3 penalty (steps flagged `direction="backward"`). `requires-registration` edges are never traversed and a registered activity as an endpoint raises `RegisteredActivityError`. `domain -requires-> build` edges cost `COVERAGE_JUMP_COST` (3.5): they exist for the build-coverage invariant, not as learning steps, and at cost 1 they skip the concepts that explain the build.
- **LLM** (`src/ai/llm.py`): Google Gemini free tier only (`GEMINI_API_KEY`, optional `GEMINI_MODEL`); do not add Claude/Anthropic calls to app code. Responses are cached on disk in `.cache/llm/`. With no key the app still works: tiers 0-2 plus a template narrative.
- **The disclaimer and the registration caution are appended by code** (`narrator.closing_notes`), never left to the model. Keep it that way.
- **Node text**: every node needs `label`, `description` (1-2 plain sentences, it is what gets embedded and narrated) and `aliases`. `tests/test_integrity.py` fails on an empty description or on a label/alias that belongs to two nodes. Avoid generic one-word aliases ("research", "cash flow"): a single alias hit becomes a confident goal-only answer.
- **Frontend**: `web/` (Vite + React + TS) talks to `src/api.py` (FastAPI) over `/api/*`; `/api/ask` and `/api/narrate` stream server-sent events.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
copy .env.example .env                                   # then put your free Gemini key in .env
.\.venv\Scripts\python.exe -m uvicorn src.api:app --reload   # API on :8000
cd web; npm install; npm run dev                         # UI on :5173 (proxies /api to :8000)
.\.venv\Scripts\python.exe -m evals.run                  # resolver evals (embeddings if installed, no LLM)
.\.venv\Scripts\python.exe -m evals.run --llm --narrate --judge   # + Gemini fallback, narrative grounding, judge
```

Tests for this layer need no network, model, or key: `tests/test_roadmap.py`, `test_resolver.py` (canned index + fake LLM), `test_pipeline.py`, `test_api.py` (pipeline built without embeddings/LLM), `test_eval_cases.py` (cases tagged `tier: alias` in `evals/cases.yaml` must pass with exact matching alone).

When writing scripts through the shell, avoid putting backslashes in Python source inside a heredoc: they can be collapsed once, turning a regex `\b` into a literal backspace character. Use the Write tool for such files.

### Run logging and progress
- Every run gets a short id and one timestamped log line per stage (`src/ai/runlog.py`, logger `finance_map.pipeline`): `rule`, `tier1`, `tier2`, `tier3`, `roadmap`, `narrative`, with statuses `running` / `done` / `passed` (ran, did not decide) / `skipped` / `failed`, plus a `finished` summary. `LOG_LEVEL=DEBUG` adds the full tier-2 top-k and the Gemini prompt size. Questions are logged truncated to 120 characters; never log keys.
- The same steps go to the browser as SSE `progress` events; `web/src/components/RunTrack.tsx` animates them (walking figure over six stations). `Resolver.resolve(question, trace=...)` reports each tier's decision and why it handed off; the pipeline runs it in a worker thread so progress streams live during a slow tier-3 call.
- Gemini calls have a timeout (`GEMINI_TIMEOUT_S`, default 25) and bounded retries (`GEMINI_MAX_RETRIES`, default 1; the SDK's own retries are off). Without a timeout the SDK waits forever. An AI failure in tier 3 ends the run with `llm_failed` and a readable message; in narration it falls back to the template.

## Demo video (`demo/`)

`python -m demo.make` builds `demo/out/finance-map-demo.mp4`. The steps are:

1. **Narration.** It voices each scene with edge-tts (`demo/voice.py`). Clips are cached in `demo/.work/voice/` by text, voice and rate. The free service often fails with "No audio was received", so it retries.
2. **Recording.** It starts its own uvicorn on :8001 with the Gemini key blanked, unless `--ai` is given. Then it records with Playwright (`demo/record.py`):
   - the animated cards (`demo/cards/card.html?mode=intro|outro`);
   - the real app, with `demo/overlay.js` injected to draw the cursor, the spotlight and the talking mascot.
3. **Music.** It synthesises music (`demo/music.py`).
4. **Mixing.** It mixes with ffmpeg: voice placed at each scene start, music ducked by sidechain, loudnorm to -16 LUFS.

Recording runs in wall-clock time, and on a busy machine scenes outlast their narration. `fit_scenes` cuts the app recording per scene and speeds up overruns, at most `MAX_SPEEDUP`, so the length stays close to the narration. The storyboard and its action vocabulary live in `demo/script.yaml`. Selectors there depend on the app's class names (`#question`, `.run-summary`, `.graph-badge`, `.steps`, `.narrative`, `.notice`), so update them if those change. Never touch the user's server on :8000.
