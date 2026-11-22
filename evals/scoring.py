"""Run one eval case through resolver + pathfinder and score it. Pure functions, no I/O besides cases.yaml."""

from pathlib import Path

import yaml

from src.ai.resolver import ResolutionError
from src.queries import RegisteredActivityError, RoadmapError, registered_activities, roadmap_path

CASES_PATH = Path(__file__).with_name("cases.yaml")
STATUSES = {"ok", "regulated", "out_of_scope"}
CATEGORIES = {"direct", "alias", "goal_only", "paraphrase", "cross_domain", "regulated", "out_of_scope"}


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    with Path(path).open(encoding="utf-8") as f:
        return yaml.safe_load(f)["cases"]


def resolve_case(resolver, G, question: str) -> dict:
    """What the pipeline would decide for `question`, without calling the narrator."""
    try:
        r = resolver.resolve(question)
    except ResolutionError as exc:
        return {"status": "no_match", "message": str(exc)}
    except Exception as exc:  # provider failure counts as a failed case, not a crash
        return {"status": "error", "message": f"{type(exc).__name__}: {exc}"}

    base = {"method": r.method, "start": r.start, "goal": r.goal, "direction": r.direction}
    if r.out_of_scope:
        return {**base, "status": "out_of_scope"}
    try:
        roadmap = roadmap_path(G, r.start, r.goal)
    except RegisteredActivityError as exc:
        return {**base, "status": "regulated", "regulated_activity": exc.activity}
    except RoadmapError as exc:
        return {**base, "status": "no_path", "message": str(exc)}
    return {**base, "status": "ok", "path": roadmap.nodes}


def score_case(case: dict, outcome: dict, registered: set[str]) -> dict:
    expected = case.get("expected_status", "ok")
    status = outcome["status"]
    if expected == "out_of_scope":
        # a safe refusal (nothing matched) is acceptable; a roadmap is not
        checks = {"status": status in {"out_of_scope", "no_match"}}
    else:
        checks = {"status": status == expected}

    if checks["status"] and expected == "ok":
        checks["goal"] = outcome["goal"] in case["expected_goal"]
        if case.get("expected_start"):
            checks["start"] = outcome["start"] in case["expected_start"]
        path = set(outcome["path"])
        if case.get("path_must_include"):
            checks["path_includes"] = set(case["path_must_include"]) <= path
        if case.get("path_must_exclude"):
            checks["path_excludes"] = not (set(case["path_must_exclude"]) & path)
        checks["no_registered_in_path"] = not (path & registered)
    elif checks["status"] and expected == "regulated":
        checks["regulated_activity"] = outcome.get("regulated_activity") in case["expected_goal"]

    return {"correct": all(checks.values()), "checks": checks}


def score_all(cases: list[dict], resolver, G) -> list[dict]:
    registered = set(registered_activities(G))
    rows = []
    for case in cases:
        outcome = resolve_case(resolver, G, case["question"])
        rows.append({"case": case, "outcome": outcome, **score_case(case, outcome, registered)})
    return rows
