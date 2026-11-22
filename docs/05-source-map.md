# Source map

This map records the conceptual anchor for each node in `graph.yaml`. It identifies subject-level references, not page-level citations: no page numbers or quotations are asserted. The CFA reference is used at topic-area-outline level only, not as a claim to have used or reproduced paid curriculum readings.

## Reference anchors

| Key | Reference | Scope used here |
|---|---|---|
| **CFA** | CFA Institute, *CFA Program Level I 2026 topic-area outline* (cfainstitute.org). | Topic-area names and broad domain organization only. |
| **CORP** | Richard A. Brealey, Stewart C. Myers, Franklin Allen, and Alex Edmans, *Principles of Corporate Finance*, 2025 release (McGraw-Hill). | Corporate finance, cash-flow valuation, discounting, enterprise/equity value, and corporate-finance modeling concepts. |
| **INV** | Zvi Bodie, Alex Kane, and Alan J. Marcus, *Investments*, 13th edition (McGraw-Hill, 2024). | Investments, portfolio/market concepts, asset classes, and risk/return methods. |
| **HULL** | John C. Hull, *Options, Futures, and Other Derivatives*, 11th edition (Pearson, 2022). | Derivative instruments and option valuation models. |
| **OUTSIDE** | Not anchored by the four references above. | Project-specific learning taxonomy or a topic requiring a primary legal, regulatory, credentialing, or standards source before relying on it. |

## Node-to-anchor index

Every declared node is listed below. Where a node has more than one conceptual anchor, all relevant keys are shown.

| Graph node(s) | Anchor(s) |
|---|---|
| `corporate_finance` | CFA, CORP |
| `ethics_and_professional_standards` | CFA |
| `quantitative_methods` | CFA, INV |
| `economics` | CFA, INV |
| `financial_statement_analysis` | CFA, CORP |
| `equity_investments` | CFA, INV |
| `fixed_income` | CFA, INV |
| `derivatives` | CFA, HULL |
| `alternative_investments` | CFA, INV |
| `portfolio_management` | CFA, INV |
| `wealth_planning` | INV |
| `discount_rate`, `net_debt_bridge`, `free_cash_flow`, `enterprise_value`, `net_debt`, `equity_value`, `per_share_value` | CORP |
| `study_scope` | OUTSIDE |
| `time_value_of_money`, `market_efficiency`, `capital_asset_pricing_model` | INV |
| `equity`, `corporate_bond`, `treasury_bill` | INV |
| `call_option` | INV, HULL |
| `interest_rate_swap` | HULL |
| `dcf`, `comparable_company_analysis`, `scenario_analysis` | CORP |
| `monte_carlo_simulation` | INV |
| `portfolio_rebalancing`, `academic_research`, `simulated_paper_trading`, `educational_content_creation` | OUTSIDE |
| `investment_advisory`, `broker_dealer_execution`, `fund_raising`, `backtest_marketing` | OUTSIDE |
| `advisers_act`, `sec_rule_206` | OUTSIDE |
| `cfa_code_of_ethics`, `gips_standards` | OUTSIDE |
| `charter_route`, `academic_doctorate`, `quant_route`, `search_fund` | OUTSIDE |
| `cfa_charter`, `cpa_license`, `frm_certification`, `caia_charter` | OUTSIDE |
| `dcf_model`, `3_statement_model`, `M_and_A_model`, `lbo_model` | CORP |
| `black_scholes_model`, `binomial_tree_model` | HULL |
| `yield_curve_model` | INV, HULL |
| `factor_risk_model`, `capm_calculator`, `monte_carlo_engine` | INV |
| `gips_report_builder` | OUTSIDE |

## Limits of this map

The OUTSIDE entries are intentionally not presented as supported by the four finance-text anchors. In particular, the graph's regulatory edges are a study aid, not legal authority. Verify legal and regulatory claims against applicable primary sources and qualified counsel; verify credential and standards claims with the issuing organization. The node-to-anchor index is a starting point for further reading, not a claim that each node is fully covered by its listed reference.

## About node descriptions

Each node in `graph.yaml` also carries a short `label`, `description`, and `aliases`. These are plain-language study-aid summaries written for matching questions to nodes and for narrating roadmaps. They are not quotations from, and have not been checked line by line against, the anchors above. Check a description against the listed anchor, or the issuing body for regulatory and credential nodes, before relying on it.
