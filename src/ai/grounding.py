"""Checks that a narrative stays on the roadmap it was written for."""

import networkx as nx

from src.ai.config import DISCLAIMER
from src.ai.lexicon import build_lexicon, find_mentions


def grounding_report(text: str, roadmap: dict, G: nx.DiGraph, lexicon: dict[str, str] | None = None) -> dict:
    """off_path: nodes named in the text that are not steps; missing: steps never named."""
    lexicon = lexicon or build_lexicon(G)
    on_path = {s["node"] for s in roadmap["steps"]}
    mentioned = {m.node for m in find_mentions(text, lexicon)}
    return {
        "off_path": sorted(mentioned - on_path),
        "missing": sorted(on_path - mentioned),
        "has_disclaimer": DISCLAIMER in text,
    }


def recommends_registered_activity(text: str, G: nx.DiGraph, registered: set[str], lexicon=None) -> list[str]:
    """Registered activities named anywhere in the text (a roadmap should only mention them as a caution)."""
    lexicon = lexicon or build_lexicon(G)
    return sorted({m.node for m in find_mentions(text, lexicon)} & registered)
