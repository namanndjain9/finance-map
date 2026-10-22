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
- [`tests/`](tests/) — pytest checks for integrity and expected query answers.
- [`exports/`](exports/) — generated topology and card-deck files.
- [`docs/`](docs/) — learning notes, build instructions, self-check evidence, teach-back, and source map.

## Regenerate exports

There is no command-line export wrapper. Run the export functions directly:

```powershell
.\.venv\Scripts\python.exe -c "from src.builder import load_graph; from src.export import export_mermaid, export_cards; graph = load_graph('graph.yaml'); export_mermaid(graph, 'exports/topology.mmd'); export_cards(graph, 'exports/cards.md')"
```

See [`docs/02-build.md`](docs/02-build.md) for the detailed build instructions and worked valuation example, and [`docs/05-source-map.md`](docs/05-source-map.md) for the reference anchors and their limits.
