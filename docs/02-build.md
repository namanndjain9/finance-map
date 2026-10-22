# Build and run

## What the build does

[`graph.yaml`](../graph.yaml) is the source of truth. It declares nodes and directed edges. [`src/schema.py`](../src/schema.py) defines the closed node- and edge-type vocabularies, while [`src/builder.py`](../src/builder.py) validates those types and references and loads the YAML into a NetworkX directed graph.

The query functions in [`src/queries.py`](../src/queries.py) answer questions about value-chain routes, study scope, registration-sensitive activities, and build coverage. Integrity checks in [`src/integrity.py`](../src/integrity.py) check for isolated nodes, invalid edge types, and disconnected components. [`src/export.py`](../src/export.py) can render the graph as Mermaid and generate the Markdown card deck.

## Requirements

Python 3 and the packages `networkx`, `PyYAML`, and `pytest` are needed to run the tests. From the repository root, install them in a virtual environment if they are not already available:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install networkx pyyaml pytest
```

## Run tests

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The tests load `graph.yaml`, validate graph integrity, and check expected query answers, including both value-chain routes and the absence of uncovered domains, instruments, and landmarks.

## Regenerate the exports

The repository has no command-line export wrapper. Run the export functions directly:

```powershell
.\.venv\Scripts\python.exe -c "from src.builder import load_graph; from src.export import export_mermaid, export_cards; graph = load_graph('graph.yaml'); export_mermaid(graph, 'exports/topology.mmd'); export_cards(graph, 'exports/cards.md')"
```

This writes [`exports/topology.mmd`](../exports/topology.mmd) and [`exports/cards.md`](../exports/cards.md). To inspect a query interactively:

```powershell
.\.venv\Scripts\python.exe -c "from src.builder import load_graph; from src.queries import value_chain; print(value_chain(load_graph('graph.yaml')))"
```

## Worked query: `free_cash_flow` to `per_share_value`

`value_chain` keeps only edges typed `flows-to`, then returns all simple directed paths between the requested nodes. For this graph, the two expected routes are:

**Unlevered route — five edges**

```text
free_cash_flow
  -> discount_rate
  -> enterprise_value
  -> net_debt
  -> equity_value
  -> per_share_value
```

The cash flows to all capital providers are discounted to enterprise value. The net-debt step bridges the value of the whole business to the residual equity value; per-share value then expresses that equity value on a per-share basis.

**Levered route — three edges**

```text
free_cash_flow
  -> discount_rate
  -> equity_value
  -> per_share_value
```

This route represents cash flows discounted directly to equity value, so it skips the enterprise-value and net-debt bridge. The graph uses one `discount_rate` node for both routes; in an actual valuation, the cash-flow definition and discount rate must be consistent (for example, unlevered cash flow with a WACC-based rate versus equity cash flow with a cost-of-equity rate).

Expected result from the query, in order:

```python
[
    ["free_cash_flow", "discount_rate", "enterprise_value", "net_debt", "equity_value", "per_share_value"],
    ["free_cash_flow", "discount_rate", "equity_value", "per_share_value"],
]
```
