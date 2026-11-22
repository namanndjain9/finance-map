"""Exact label/alias matching between free text and graph nodes.

Used by the resolver (tier 1) and by the narrative grounding check.
"""

import re
from dataclasses import dataclass

import networkx as nx


def normalize(text: str) -> str:
    """Lowercase, '&' -> 'and', every other non-alphanumeric run -> one space."""
    text = text.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


@dataclass(frozen=True)
class Mention:
    node: str
    key: str  # the normalised label/alias that matched
    start: int  # character offsets in the normalised text
    end: int


def build_lexicon(G: nx.DiGraph) -> dict[str, str]:
    """normalised string -> node id, for ids, labels, aliases and simple plurals.

    A string that points at two different nodes is dropped: an ambiguous
    mention must fall through to embeddings or the LLM, never guess.
    """
    owners: dict[str, set[str]] = {}

    def add(text: str, node: str) -> None:
        key = normalize(text)
        if key:
            owners.setdefault(key, set()).add(node)

    for node, data in G.nodes(data=True):
        add(node.replace("_", " "), node)
        add(data.get("label", ""), node)
        for alias in data.get("aliases", []):
            add(alias, node)

    for key in list(owners):  # plurals, but never over an existing key
        plural = key if key.endswith("s") else key + "s"
        if plural not in owners:
            owners[plural] = set(owners[key])

    return {key: next(iter(nodes)) for key, nodes in owners.items() if len(nodes) == 1}


def find_mentions(text: str, lexicon: dict[str, str]) -> list[Mention]:
    """Non-overlapping mentions, longest match first, returned in text order."""
    norm = normalize(text)
    padded = f" {norm} "
    found: list[Mention] = []
    # Text and keys are both normalised to single-space-separated tokens, so a plain substring
    # search on " key " is a whole-word match. (A regex per key meant ~600 patterns, more than
    # re's 512-entry cache, so every question recompiled them all: ~130 ms, seconds under load.)
    for key, node in lexicon.items():
        needle = f" {key} "
        at = padded.find(needle)
        while at != -1:
            found.append(Mention(node, key, at, at + len(key)))
            at = padded.find(needle, at + 1)
    found.sort(key=lambda m: (-(m.end - m.start), m.start))
    taken: list[Mention] = []
    for m in found:
        if all(m.end <= t.start or m.start >= t.end for t in taken):
            taken.append(m)
    return sorted(taken, key=lambda m: m.start)
