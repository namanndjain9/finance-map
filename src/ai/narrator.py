"""Turn a Roadmap into a narrative. The path is fixed by code; the LLM only writes prose about it.

The disclaimer and the registration caution are appended by code (`closing_notes`), never left
to the model. If the LLM is unavailable, blocked, or fails, `template_narrative` still gives the
learner a readable roadmap.
"""

from typing import Callable, Iterator

import networkx as nx

from src.ai.config import DISCLAIMER
from src.ai.llm import LLMClient, LLMError

RELATION = {
    "precedes": "{a} comes before {b}",
    "requires": "{a} requires {b}",
    "flows-to": "{a} flows into {b}",
    "prices": "{a} is used to price {b}",
    "exercised-by": "{a} is exercised through {b}",
    "permitted-as-study": "{a} is a permitted study activity under {b}",
    "belongs-to": "{a} belongs to {b}",
}

SYSTEM = (
    "You write short study roadmaps for a finance learning graph. You are given an ordered list of "
    "steps taken from a knowledge graph, each with a description and its relationship to the previous "
    "step.\n"
    "Write a friendly, plain-English narrative of about 120-220 words that walks the learner through "
    "the steps in the given order.\n"
    "Rules:\n"
    "- Name only the listed steps. Do not introduce other finance topics, tools, products, or people.\n"
    "- Describe each relationship exactly as given in its 'Relationship' line; never reverse it.\n"
    "- Where a step lists practice builds, suggest building them as hands-on practice.\n"
    "- Do not give investment, legal, or registration advice, and do not recommend any trade or product.\n"
    "- Do not write a disclaimer; one is added automatically.\n"
    "- Use markdown: one short intro sentence, then a numbered list with one or two sentences per step."
)


def _relationship(prev_label: str, step: dict) -> str | None:
    if not step.get("via_edge"):
        return None
    template = RELATION.get(step["via_edge"], "{a} is linked to {b}")
    a, b = (prev_label, step["label"]) if step["direction"] == "forward" else (step["label"], prev_label)
    return template.format(a=a, b=b)


def _labels(steps: list[dict]) -> dict[str, str]:
    return {s["node"]: s["label"] for s in steps}


def build_prompt(question: str, roadmap: dict) -> str:
    steps = roadmap["steps"]
    lines = [f"Learner question: {question}", f"Start: {steps[0]['label']}", f"Goal: {steps[-1]['label']}", "Steps:"]
    for i, step in enumerate(steps, 1):
        line = f"{i}. {step['label']} [{step['type']}]: {step['description']}"
        rel = _relationship(steps[i - 2]["label"], step) if i > 1 else None
        if rel:
            line += f"\n   Relationship: {rel}."
        if step["practice_builds"]:
            builds = ", ".join(step["practice_builds"]).replace("_", " ")
            line += f"\n   Practice builds: {builds}."
        lines.append(line)
    return "\n".join(lines)


def template_narrative(roadmap: dict) -> str:
    steps = roadmap["steps"]
    if len(steps) == 1:
        s = steps[0]
        return f"**{s['label']}** is both where you start and where you want to be: {s['description']}"
    out = [f"Here is a path from **{steps[0]['label']}** to **{steps[-1]['label']}** ({len(steps)} steps):", ""]
    for i, step in enumerate(steps, 1):
        line = f"{i}. **{step['label']}**: {step['description']}"
        rel = _relationship(steps[i - 2]["label"], step) if i > 1 else None
        if rel:
            line += f" ({rel}.)"
        if step["practice_builds"]:
            line += " Practice by building: " + ", ".join(step["practice_builds"]).replace("_", " ") + "."
        out.append(line)
    return "\n".join(out)


def closing_notes(roadmap: dict, G: nx.DiGraph) -> str:
    parts = []
    if roadmap.get("regulated_nearby"):
        names = ", ".join(G.nodes[n]["label"].lower() for n in roadmap["regulated_nearby"])
        parts.append(
            f"**Note:** activities such as {names} typically require registration or licensing. "
            "They are outside this self-study roadmap; check the rules that apply to you before "
            "doing any of them."
        )
    parts.append(f"_{DISCLAIMER}_")
    return "\n\n".join(parts)


def narrate(
    question: str,
    roadmap: dict,
    llm: LLMClient | None,
    report: Callable[[str, str], object] | None = None,
) -> Iterator[str]:
    """Yield narrative text. Falls back to the template if the LLM is missing or fails.

    `report(source, detail)` (optional) is told which source wrote the text:
    "ai", "template", or "fallback" (AI failed or returned nothing, template used instead).
    """
    say = report or (lambda _source, _detail: None)
    if llm is None:
        say("template", "AI narration is off; using the plain summary")
        yield template_narrative(roadmap)
        return
    say("ai", "the AI is writing the story")
    produced = False
    reason = "the AI returned no text"
    try:
        for chunk in llm.stream_text(SYSTEM, build_prompt(question, roadmap)):
            produced = True
            yield chunk
        if produced:
            return
    except LLMError as exc:
        reason = f"AI failed: {exc}"[:200]
    say("fallback", f"{reason}; using the plain summary")
    prefix = "\n\n_The AI narration was interrupted; here is the plain summary._\n\n" if produced else ""
    yield prefix + template_narrative(roadmap)
