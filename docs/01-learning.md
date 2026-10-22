# Learning the finance map

## What I was learning, and why

This project turns a finance learning path into a typed, queryable graph. I was learning how valuation ideas connect, how those connections differ from a study plan, and where a learning exercise ends and regulated financial activity may begin.

The valuation chain makes abstract concepts testable: forecast cash flows are discounted to present value, bridged from enterprise value to equity value where appropriate, and then expressed per share. The surrounding nodes connect that core to financial statements, investments, derivatives, portfolio management, ethics, and practical model-building.

The graph is deliberately not a complete curriculum or legal guide. It is an inventory of claims that can be checked. A query returning a list or path is evidence about the graph as currently encoded—not evidence that the graph is exhaustive, that a market behaves a certain way, or that a person is authorized to perform an activity.

## Three habits

1. **Type every edge from the closed vocabulary.** Choose a defined relationship such as `flows-to`, `precedes`, `requires`, `prices`, `permitted-as-study`, or `requires-registration`. An intuitive but untyped relationship is not machine-checkable.
2. **Keep study apart from registration.** Learning, research, educational work, and simulated practice are not interchangeable with providing services, executing transactions, or raising capital for others. The graph separates study-scope edges from registration-sensitive activities; real requirements depend on the activity and jurisdiction.
3. **Write expected answers first.** State the exact path, list, or coverage result before running a query. That makes the test capable of disproving the model instead of inviting a post-hoc explanation.

## How I use the map

Start with a question, write down the answer that would be correct, then run the query or test. If the answer differs, inspect the edge types and graph wiring before changing the expected value. The useful deliverable is the answer recalled and checked cold; the picture is only an aid.
