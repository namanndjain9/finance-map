"""Run the evals.

    python -m evals.run                       # resolver only; embeddings if installed, no LLM
    python -m evals.run --no-embeddings       # alias tier only
    python -m evals.run --llm                 # + Gemini fallback for tier 3 (uses free-tier quota)
    python -m evals.run --llm --narrate       # + narrative grounding checks on a sample
    python -m evals.run --llm --narrate --judge   # + LLM-judge rubric (Gemini judging Gemini: treat as a rough signal)

Results are written to evals/results/<timestamp>.json (git-ignored).
"""

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from evals.scoring import load_cases, score_all
from src.ai.config import GRAPH_PATH
from src.ai.embed_index import try_create_index
from src.ai.grounding import grounding_report, recommends_registered_activity
from src.ai.lexicon import build_lexicon
from src.ai.llm import try_create_llm
from src.ai.pipeline import Pipeline
from src.ai.resolver import Resolver
from src.builder import load_graph
from src.queries import registered_activities

RESULTS_DIR = Path(__file__).with_name("results")
CALL_GAP_SECONDS = 4.5  # stay under typical free-tier requests-per-minute limits

JUDGE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "faithfulness": {"type": "INTEGER"},
        "ordering": {"type": "INTEGER"},
        "usefulness": {"type": "INTEGER"},
        "comment": {"type": "STRING"},
    },
    "required": ["faithfulness", "ordering", "usefulness", "comment"],
}
JUDGE_SYSTEM = (
    "You grade a study-roadmap narrative against the ordered steps it was written from. Score 1-5 each: "
    "faithfulness (says nothing that contradicts or goes beyond the steps and relationships), "
    "ordering (follows the given step order), usefulness (clear and helpful to a learner). "
    "Be strict. Reply as JSON."
)


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:5.1f}% ({n}/{d})" if d else "   n/a"


def summarise(rows: list[dict]) -> dict:
    by_cat, by_method = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for r in rows:
        by_cat[r["case"]["category"]][0] += r["correct"]
        by_cat[r["case"]["category"]][1] += 1
        method = r["outcome"].get("method", "none")
        by_method[method][0] += r["correct"]
        by_method[method][1] += 1
    resolved = [r for r in rows if "method" in r["outcome"]]
    return {
        "accuracy": [sum(r["correct"] for r in rows), len(rows)],
        "by_category": dict(by_cat),
        "by_method": dict(by_method),
        "llm_fallback_rate": [sum(r["outcome"]["method"] == "llm" for r in resolved), len(resolved)],
    }


def narrative_eval(pipe: Pipeline, rows: list[dict], limit: int, judge: bool, llm) -> list[dict]:
    G, lexicon, registered = pipe.G, build_lexicon(pipe.G), set(registered_activities(pipe.G))
    sample = [r for r in rows if r["correct"] and r["outcome"]["status"] == "ok"][:limit]
    out = []
    for r in sample:
        result = pipe.ask(r["case"]["question"])
        text, roadmap = result["narrative"], result["roadmap"]
        report = grounding_report(text, roadmap, G, lexicon)
        entry = {
            "id": r["case"]["id"],
            "off_path": report["off_path"],
            "missing_steps": report["missing"],
            "has_disclaimer": report["has_disclaimer"],
            "mentions_registered": recommends_registered_activity(text, G, registered, lexicon),
        }
        if judge and llm is not None:
            steps = "\n".join(f"{i}. {s['label']}: {s['description']}" for i, s in enumerate(roadmap["steps"], 1))
            entry["judge"] = llm.generate_json(JUDGE_SYSTEM, f"STEPS:\n{steps}\n\nNARRATIVE:\n{text}", JUDGE_SCHEMA)
            time.sleep(CALL_GAP_SECONDS)
        out.append(entry)
        time.sleep(CALL_GAP_SECONDS)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-embeddings", action="store_true")
    ap.add_argument("--llm", action="store_true", help="enable the Gemini fallback (needs GEMINI_API_KEY)")
    ap.add_argument("--narrate", action="store_true", help="also grade narratives for a sample of cases")
    ap.add_argument("--judge", action="store_true", help="add an LLM-judge rubric to the narrative sample")
    ap.add_argument("--narrate-limit", type=int, default=8)
    ap.add_argument("--tier", choices=["alias", "model", "all"], default="all")
    args = ap.parse_args()

    G = load_graph(GRAPH_PATH)
    index = None if args.no_embeddings else try_create_index(G)
    llm = try_create_llm() if (args.llm or args.narrate) else None
    if args.llm and llm is None:
        raise SystemExit("--llm needs GEMINI_API_KEY (free key: aistudio.google.com) and `pip install -r requirements-ai.txt`.")

    cases = [c for c in load_cases() if args.tier in ("all", c["tier"])]
    print(f"cases={len(cases)}  embeddings={'on' if index else 'off'}  llm={'on' if llm else 'off'}\n")
    resolver = Resolver(G, index=index, llm=llm if args.llm else None)
    rows = score_all(cases, resolver, G)
    if args.llm:
        time.sleep(0)  # resolver already hit the provider per case; outcomes are cached on disk

    for r in rows:
        o = r["outcome"]
        mark = "PASS" if r["correct"] else "FAIL"
        got = f"{o.get('start')} -> {o.get('goal')}" if "goal" in o else o.get("message", "")[:60]
        print(f"{mark} {r['case']['id']:<10} {o['status']:<12} {o.get('method', '-'):<9} {got}")
        if not r["correct"]:
            failed = [k for k, v in r["checks"].items() if not v]
            print(f"       failed checks: {failed}; question: {r['case']['question']}")

    summary = summarise(rows)
    print("\nOverall:", pct(*summary["accuracy"]))
    for name, (ok, n) in sorted(summary["by_category"].items()):
        print(f"  {name:<14}{pct(ok, n)}")
    print("By method:", {k: f"{v[0]}/{v[1]}" for k, v in summary["by_method"].items()})
    print("LLM fallback rate:", pct(*summary["llm_fallback_rate"]))

    narrative = None
    if args.narrate:
        pipe = Pipeline(G, resolver, llm)
        narrative = narrative_eval(pipe, rows, args.narrate_limit, args.judge, llm)
        print("\nNarrative sample:")
        for n in narrative:
            print(f"  {n['id']:<10} off_path={n['off_path']} missing={n['missing_steps']} "
                  f"disclaimer={n['has_disclaimer']} registered={n['mentions_registered']}"
                  + (f" judge={ {k: n['judge'][k] for k in ('faithfulness','ordering','usefulness')} }" if "judge" in n else ""))

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows, "narrative": narrative}, indent=2, default=list),
                   encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
