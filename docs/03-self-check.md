# Self-check and evidence

## Expected query answers

These are the expected answers for the current `graph.yaml`. A query result describes the graph as encoded; it is not an empirical finding about markets or a legal determination.

| Query | Expected value | What a wrong answer means |
|---|---|---|
| `value_chain(graph)` | Two paths: `free_cash_flow -> discount_rate -> enterprise_value -> net_debt -> equity_value -> per_share_value` (5 edges), and `free_cash_flow -> discount_rate -> equity_value -> per_share_value` (3 edges). The longer route is returned first. | No paths points to a missing or mistyped `flows-to` edge. A missing five-edge route suggests a break in the enterprise-value/net-debt bridge. A missing three-edge route means the direct levered route is disconnected. |
| `study_scope(graph)` | `["academic_research", "educational_content_creation", "portfolio_rebalancing", "simulated_paper_trading"]` | A missing permitted activity suggests a missing `permitted-as-study` edge. A registration-sensitive activity appearing here means the study and activity classifications have been mixed. |
| `registered_activities(graph)` | `["backtest_marketing", "broker_dealer_execution", "fund_raising", "investment_advisory"]` | A missing activity indicates it has no `requires-registration` edge or is not typed as an activity. An unexpected activity indicates the registration-sensitive edge set changed and should be reviewed. |
| `build_coverage(graph)` | `{"landmarks": [], "domains": [], "instruments": []}` | A returned landmark was collected but not practiced in a build; a returned domain is uncovered by the build inventory; a returned instrument is named but not exercised in a build. This is a coverage check on the graph, not a market finding. |
| `roadmap_path(graph, "free_cash_flow", "per_share_value")` | `free_cash_flow -> discount_rate -> equity_value -> per_share_value`, all forward steps. The shortest route is the levered one; the unlevered route through `net_debt` is the longer alternative. | A path through a `requires-registration` activity, or one with a step flagged `backward` here, means edge traversal rules changed. |
| `roadmap_path(graph, "free_cash_flow", "call_option")` | `free_cash_flow -> discount_rate -> dcf_model -> equity -> call_option`; the last step is flagged `backward` because the graph edge runs `call_option -exercised-by-> equity`. | A path that presents `call_option` as a forward step would let the narrator describe the relationship the wrong way round. |
| `roadmap_path(graph, "economics", "capm_calculator")` | `economics -> market_efficiency -> capital_asset_pricing_model -> capm_calculator`. | A direct `economics -> capm_calculator` hop means a domain-to-build coverage link was walked as a learning step (it should cost `COVERAGE_JUMP_COST`). |
| `roadmap_path(graph, <any>, "investment_advisory")` | Raises `RegisteredActivityError`; the same for the other three registered activities. | A returned path means a study roadmap could lead to regulated work. |

## Test evidence

Actual command run from the repository root:

```text
.\.venv\Scripts\python.exe -m pytest -q
```

Actual output:

```text
112 passed in 35.91s
```

## Roadmap resolver evals

Command (embeddings on, no LLM, so tier 3 is not exercised):

```text
.\.venv\Scripts\python.exe -m evals.run
```

Result on `evals/cases.yaml` (43 cases): **35/43 correct (81.4%)**.

| Category | Correct | Note |
|---|---|---|
| direct, alias, goal_only, cross_domain | 24/24 | Exact label/alias matching. |
| out_of_scope | 5/5 | Three by the advice rule, two by nothing matching (safe refusal). |
| regulated | 3/4 | `reg-01` ("registered investment adviser") abstained; it needs the LLM tier. |
| paraphrase | 3/10 | Six abstained with "could not tell which two topics" (safe, would go to the LLM tier). One answered wrongly: `para-02` matched "discounting" to `discount_rate`. |

What this does and does not show: the exact-match and embedding tiers rarely give a wrong answer here (1 of 43), and they decline when unsure. The Gemini fallback, narrative grounding and judge rubric (`--llm --narrate --judge`) have not been run: they need a `GEMINI_API_KEY`. The embedding thresholds (`tau=0.40`, `margin=0.08`) are defaults chosen conservatively; a sweep over 15 model-tier cases showed the wrong-answer count did not depend on them, so they were not tuned further.

## Card-deck practice bar

Practice bar: `█████████████████░░░ 17/20`

This is a practice score/bar for the card deck, not an outcome, prediction, credential, registration, or evidence of investment performance.
