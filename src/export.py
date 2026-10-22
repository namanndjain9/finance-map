"""Export the graph as Mermaid diagram and Markdown card deck."""
from pathlib import Path
import networkx as nx

def export_mermaid(G: nx.DiGraph, path: str | Path) -> None:
    """Write a valid Mermaid flowchart grouping nodes by domain."""
    path = Path(path)
    lines = ["graph LR"]
    
    domains = [n for n, d in G.nodes(data=True) if d.get("type") == "domain"]
    assigned = set()
    
    for domain in sorted(domains):
        lines.append(f"    subgraph {domain}")
        belonging = set()
        
        for u, v, d in G.edges(data=True):
            # Capture explicitly assigned nodes (belongs-to) or incoming/outgoing domain edges
            if (d.get("type") == "belongs-to" and v == domain) or (u == domain and G.nodes[v].get("type") != "domain"):
                target_node = u if d.get("type") == "belongs-to" else v
                belonging.add(target_node)
                
        for member in sorted(belonging):
            landmark = G.nodes[member].get("landmark", "")
            # Safely quote labels to prevent nested bracket syntax errors
            label = f'"{member} [{landmark}]"' if landmark else f'"{member}"'
            lines.append(f"        {member}[{label}]")
            assigned.add(member)
            
        lines.append("    end")
        
    # Remaining top-level nodes (non-domain, non-member)
    for node in sorted(G.nodes()):
        if node not in assigned and node not in domains:
            landmark = G.nodes[node].get("landmark", "")
            label = f'"{node} [{landmark}]"' if landmark else f'"{node}"'
            lines.append(f"    {node}[{label}]")
            
    # Draw all edges with type labels
    for u, v, data in G.edges(data=True):
        edge_type = data.get("type", "")
        lines.append(f"    {u} -->|{edge_type}| {v}")
        
    path.write_text("\n".join(lines), encoding="utf-8")

def export_cards(G: nx.DiGraph, path: str | Path) -> None:
    """Write a Markdown card deck with 20 query-based prompts and answers."""
    path = Path(path)
    cards = []

    cards.append("# Finance Map Card Deck\n")
    cards.append("## Value Chain Cards\n")
    cards.append("**Q:** How does a forecast cash flow become a per-share value on the unlevered route?\n")
    cards.append("**A:** free_cash_flow -> discount_rate -> enterprise_value -> net_debt -> equity_value -> per_share_value (5 flows-to edges). The discount rate turns future cash into present value. The net-debt bridge subtracts debt claims to isolate equity.\n")
    cards.append("---\n")
    cards.append("**Q:** What is the levered route?\n")
    cards.append("**A:** free_cash_flow -> discount_rate -> equity_value -> per_share_value (3 flows-to edges). Discounts cash flow to equity directly, skipping enterprise value and net debt.\n")
    cards.append("---\n")
    cards.append("**Q:** What does a discount rate consist of?\n")
    cards.append("**A:** A risk-free rate plus a premium for risk. It turns a future cash flow into money today.\n")
    cards.append("---\n")
    cards.append("**Q:** What is enterprise value?\n")
    cards.append("**A:** The whole business priced for everyone who funded it (debt + equity holders).\n")
    cards.append("---\n")
    cards.append("**Q:** What is the net-debt bridge?\n")
    cards.append("**A:** The step from enterprise value to equity value. Equity value = enterprise value minus net debt.\n")
    cards.append("---\n")
    cards.append("## Study Scope Cards\n")
    cards.append("**Q:** Which activities can you practice as self-directed study without registration?\n")

    from src.queries import study_scope as _study_scope
    permitted = _study_scope(G)
    cards.append(f"**A:** {', '.join(permitted) if permitted else 'None found (check graph)'}.\n")
    cards.append("---\n")
    cards.append("**Q:** Name the 4 activities that require registration.\n")
    cards.append("**A:** investment_advisory, broker_dealer_execution, fund_raising, backtest_marketing. Each carries a requires-registration edge to its regulatory item.\n")
    cards.append("---\n")
    cards.append("**Q:** Why is a CFA charter not permission to manage money?\n")
    cards.append("**A:** A charter is a credential (private certification). Authority to manage or advise on other people's money comes from a registration (Advisers Act or broker-dealer/FINRA).\n")
    cards.append("---\n")
    cards.append("**Q:** Why is a backtest not a track record?\n")
    cards.append("**A:** A backtest is a strategy replayed over past data. It suffers from look-ahead bias, survivorship bias, overfitting, and ignores transaction costs. It is not a prediction. The graph types it as an activity requiring registration to show to prospective investors.\n")
    cards.append("---\n")
    cards.append("**Q:** What does Regulation D govern?\n")
    cards.append("**A:** Private fund raising (a securities offering). It requires a Form D filing and implicates the Investment Company Act. It needs securities counsel.\n")
    cards.append("---\n")
    cards.append("## Route Cards\n")
    cards.append("**Q:** Name the four routes into finance practice.\n")
    cards.append("**A:** Academic doctorate (asset-pricing research), charter route (CFA + MBA + registration), quant route (MFE + algo/ML), search fund (buy and run a company).\n")
    cards.append("---\n")
    cards.append("**Q:** Which route is built for a coder?\n")
    cards.append("**A:** The quant route: master's in financial engineering plus algorithmic and machine-learning work.\n")
    cards.append("---\n")
    cards.append("**Q:** What does the academic doctorate route train you for?\n")
    cards.append("**A:** To study markets (asset-pricing and econometrics research), not to work in them.\n")
    cards.append("---\n")
    cards.append("## Coverage Cards\n")
    cards.append("**Q:** What does a non-zero build-coverage count mean?\n")
    cards.append("**A:** A landmark returned was collected but never practiced. A domain returned is an area the path skips. An instrument returned was named but never exercised in a build. The count is a regression check on your inventory, not a finding about markets.\n")
    cards.append("---\n")
    cards.append("**Q:** What free data sources feed the later builds?\n")
    cards.append("**A:** FRED (St. Louis Fed), SEC EDGAR, Kenneth French Data Library (Dartmouth), Damodaran Online (NYU Stern).\n")
    cards.append("---\n")    
    cards.append("## Method Cards\n")
    cards.append("**Q:** Why must every edge come from the closed vocabulary?\n")
    cards.append("**A:** An untyped edge is a feeling, not a claim anyone can query. The closed vocabulary makes the graph machine-checkable.\n")
    cards.append("---\n")
    cards.append("**Q:** Why write the expected answer before running the query?\n")
    cards.append("**A:** A query you interpret afterwards can never fail. Fixtures-first testing means the test fails on wrong structure, not wrong assertion.\n")
    cards.append("---\n")
    cards.append("**Q:** When a query returns a count, what must you say about it?\n")
    cards.append("**A:** What it is evidence of. A count over nodes you added is a regression check on your inventory, not a finding about markets.\n")
    cards.append("---\n")
    cards.append("**Q:** What is a concept map NOT?\n")
    cards.append("**A:** A syllabus to read. It is a structure to interrogate. The deliverable is the query answered cold, never the picture alone.\n")
    cards.append("---\n")
    cards.append("**Q:** What does the honest route build, and what does it not build?\n")
    cards.append("**A:** It builds knowledge, quantitative craft, and a portfolio of models. It does not build a degree, a charter, a registration, capital, or a track record of real returns.\n")

    path.write_text("\n".join(cards), encoding="utf-8")