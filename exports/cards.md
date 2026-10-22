# Finance Map Card Deck

## Value Chain Cards

**Q:** How does a forecast cash flow become a per-share value on the unlevered route?

**A:** free_cash_flow -> discount_rate -> enterprise_value -> net_debt -> equity_value -> per_share_value (5 flows-to edges). The discount rate turns future cash into present value. The net-debt bridge subtracts debt claims to isolate equity.

---

**Q:** What is the levered route?

**A:** free_cash_flow -> discount_rate -> equity_value -> per_share_value (3 flows-to edges). Discounts cash flow to equity directly, skipping enterprise value and net debt.

---

**Q:** What does a discount rate consist of?

**A:** A risk-free rate plus a premium for risk. It turns a future cash flow into money today.

---

**Q:** What is enterprise value?

**A:** The whole business priced for everyone who funded it (debt + equity holders).

---

**Q:** What is the net-debt bridge?

**A:** The step from enterprise value to equity value. Equity value = enterprise value minus net debt.

---

## Study Scope Cards

**Q:** Which activities can you practice as self-directed study without registration?

**A:** academic_research, educational_content_creation, portfolio_rebalancing, simulated_paper_trading.

---

**Q:** Name the 4 activities that require registration.

**A:** investment_advisory, broker_dealer_execution, fund_raising, backtest_marketing. Each carries a requires-registration edge to its regulatory item.

---

**Q:** Why is a CFA charter not permission to manage money?

**A:** A charter is a credential (private certification). Authority to manage or advise on other people's money comes from a registration (Advisers Act or broker-dealer/FINRA).

---

**Q:** Why is a backtest not a track record?

**A:** A backtest is a strategy replayed over past data. It suffers from look-ahead bias, survivorship bias, overfitting, and ignores transaction costs. It is not a prediction. The graph types it as an activity requiring registration to show to prospective investors.

---

**Q:** What does Regulation D govern?

**A:** Private fund raising (a securities offering). It requires a Form D filing and implicates the Investment Company Act. It needs securities counsel.

---

## Route Cards

**Q:** Name the four routes into finance practice.

**A:** Academic doctorate (asset-pricing research), charter route (CFA + MBA + registration), quant route (MFE + algo/ML), search fund (buy and run a company).

---

**Q:** Which route is built for a coder?

**A:** The quant route: master's in financial engineering plus algorithmic and machine-learning work.

---

**Q:** What does the academic doctorate route train you for?

**A:** To study markets (asset-pricing and econometrics research), not to work in them.

---

## Coverage Cards

**Q:** What does a non-zero build-coverage count mean?

**A:** A landmark returned was collected but never practiced. A domain returned is an area the path skips. An instrument returned was named but never exercised in a build. The count is a regression check on your inventory, not a finding about markets.

---

**Q:** What free data sources feed the later builds?

**A:** FRED (St. Louis Fed), SEC EDGAR, Kenneth French Data Library (Dartmouth), Damodaran Online (NYU Stern).

---

## Method Cards

**Q:** Why must every edge come from the closed vocabulary?

**A:** An untyped edge is a feeling, not a claim anyone can query. The closed vocabulary makes the graph machine-checkable.

---

**Q:** Why write the expected answer before running the query?

**A:** A query you interpret afterwards can never fail. Fixtures-first testing means the test fails on wrong structure, not wrong assertion.

---

**Q:** When a query returns a count, what must you say about it?

**A:** What it is evidence of. A count over nodes you added is a regression check on your inventory, not a finding about markets.

---

**Q:** What is a concept map NOT?

**A:** A syllabus to read. It is a structure to interrogate. The deliverable is the query answered cold, never the picture alone.

---

**Q:** What does the honest route build, and what does it not build?

**A:** It builds knowledge, quantitative craft, and a portfolio of models. It does not build a degree, a charter, a registration, capital, or a track record of real returns.
