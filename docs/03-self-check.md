# Self-check and evidence

## Expected query answers

These are the expected answers for the current `graph.yaml`. A query result describes the graph as encoded; it is not an empirical finding about markets or a legal determination.

| Query | Expected value | What a wrong answer means |
|---|---|---|
| `value_chain(graph)` | Two paths: `free_cash_flow -> discount_rate -> enterprise_value -> net_debt -> equity_value -> per_share_value` (5 edges), and `free_cash_flow -> discount_rate -> equity_value -> per_share_value` (3 edges). The longer route is returned first. | No paths points to a missing or mistyped `flows-to` edge. A missing five-edge route suggests a break in the enterprise-value/net-debt bridge. A missing three-edge route means the direct levered route is disconnected. |
| `study_scope(graph)` | `["academic_research", "educational_content_creation", "portfolio_rebalancing", "simulated_paper_trading"]` | A missing permitted activity suggests a missing `permitted-as-study` edge. A registration-sensitive activity appearing here means the study and activity classifications have been mixed. |
| `registered_activities(graph)` | `["backtest_marketing", "broker_dealer_execution", "fund_raising", "investment_advisory"]` | A missing activity indicates it has no `requires-registration` edge or is not typed as an activity. An unexpected activity indicates the registration-sensitive edge set changed and should be reviewed. |
| `build_coverage(graph)` | `{"landmarks": [], "domains": [], "instruments": []}` | A returned landmark was collected but not practiced in a build; a returned domain is uncovered by the build inventory; a returned instrument is named but not exercised in a build. This is a coverage check on the graph, not a market finding. |

## Test evidence

Actual command run from the repository root:

```text
.\.venv\Scripts\python.exe -m pytest -q
```

Actual output:

```text
..............                                                           [100%]
14 passed in 1.74s
```

## Card-deck practice bar

Practice bar: `█████████████████░░░ 17/20`

This is a practice score/bar for the card deck, not an outcome, prediction, credential, registration, or evidence of investment performance.
