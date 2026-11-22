"""Map a free-text question to (start, goal) nodes that are guaranteed to be in the graph.

Tier 1  exact label/alias mentions (free, deterministic)
Tier 2  embedding similarity (local model)
Tier 3  LLM constrained to an enum of real node ids

Every tier ends in `_finalise`, which re-checks membership in the graph.
"""

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Protocol

import networkx as nx

from src.ai.lexicon import Mention, build_lexicon, find_mentions, normalize
from src.queries import _traversal_graph, default_start

NONE = "NONE"  # enum sentinel for "not stated"

START_CUES = frozenset(
    "from know knowing knew familiar comfortable after learned learnt finished completed given starting start".split()
)
GOAL_CUES = frozenset(
    "to towards toward reach learn learning master become build building price pricing value valuing "
    "want need study studying prepare".split()
)


# Personal-advice / stock-pick phrasing. Checked before any matching so that a generic
# alias ("stock") can never turn "which stock should I buy" into a roadmap.
ADVICE_PATTERNS = [
    re.compile(p)
    for p in (
        r"\bshould i (buy|sell|short|invest|put)\b",
        r"\bwhich (stocks?|etfs?|funds?|cryptos?|coins?|shares) (should|to|do you|is|are|will)\b",
        r"\bwhat (stocks?|etfs?|funds?|cryptos?) (should|to buy|to invest)\b",
        r"\b(best|top|good) (stocks?|etfs?|funds?) to (buy|invest)\b",
        r"\bstock (picks?|tips?)\b",
        r"\bhow (much|many) should i (invest|put|allocate)\b",
        r"\bwill\b.*\b(go up|go down|crash|rally|rise|fall|moon)\b",
        r"\b(is|are)\b.*\bgoing to\b.*\b(go up|go down|crash|rally|rise|fall|moon)\b",
    )
]


class ResolutionError(Exception):
    """The question could not be mapped to nodes in the graph."""


class SupportsJSON(Protocol):
    def generate_json(self, system: str, prompt: str, schema: dict) -> dict: ...


# trace(stage, status, detail="", debug=None); see src/ai/runlog.py for stages and statuses.
Trace = Callable[..., object]


def _no_trace(*_args, **_kwargs) -> None:
    return None


def _fmt(candidates: list[tuple[str, float]], n: int = 3) -> str:
    return ", ".join(f"{node} {score:.2f}" for node, score in candidates[:n])


@dataclass
class ResolverConfig:
    tau: float = 0.40  # a node counts as "named" by the question above this cosine
    margin: float = 0.08  # required gap between the last accepted node and the next candidate
    floor: float = 0.25  # best cosine below this means nothing in the graph matches
    top_k: int = 8


@dataclass
class Resolution:
    start: str | None
    goal: str | None
    method: str  # "rule" | "alias" | "embedding" | "llm"
    confidence: str  # "high" | "medium" | "low"
    direction: str  # "cues" | "order" | "graph" | "llm" | "goal_only"
    start_defaulted: bool = False
    out_of_scope: bool = False
    reason: str = ""
    candidates: list[tuple[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _cue_before(norm_text: str, mention: Mention) -> str | None:
    """'start' / 'goal' if the nearest cue word just before the mention says so."""
    for token in reversed(norm_text[: mention.start].split()[-4:]):
        if token in START_CUES:
            return "start"
        if token in GOAL_CUES:
            return "goal"
    return None


def _order_two(question: str, a: Mention, b: Mention) -> tuple[str, str, str]:
    """(start, goal, how) for two mentions with a before b in the text."""
    norm = normalize(question)
    ca, cb = _cue_before(norm, a), _cue_before(norm, b)
    if (ca, cb) in {("start", "goal"), ("start", None), (None, "goal")}:
        return a.node, b.node, "cues"
    if (ca, cb) in {("goal", "start"), ("goal", None), (None, "start")}:
        return b.node, a.node, "cues"
    return a.node, b.node, "order"


class Resolver:
    def __init__(
        self,
        G: nx.DiGraph,
        index=None,
        llm: SupportsJSON | None = None,
        config: ResolverConfig | None = None,
    ):
        self.G = G
        self.index = index
        self.llm = llm
        self.cfg = config or ResolverConfig()
        self.lexicon = build_lexicon(G)
        self._forward = _traversal_graph(G, allow_backward=False)

    # ------------------------------------------------------------------ public
    def resolve(self, question: str, trace: Trace | None = None) -> Resolution:
        """Run the tiers in order. `trace` (optional) is told what each tier did and why."""
        t = trace or _no_trace
        question = question.strip()
        if not question:
            raise ResolutionError("Ask a question about a finance concept in the graph.")

        def skip_rest(after: str, why: str) -> None:
            for stage in ("tier1", "tier2", "tier3")[("rule", "tier1", "tier2").index(after):]:
                t(stage, "skipped", why)

        # Rule: personal advice / stock picks are refused before any matching.
        t("rule", "running", "checking for advice or stock-pick requests")
        if any(p.search(normalize(question)) for p in ADVICE_PATTERNS):
            t("rule", "done", "advice request -> out of scope")
            skip_rest("rule", "not needed")
            return Resolution(None, None, "rule", "high", "rule", out_of_scope=True,
                              reason="asks for personal investment advice or a stock pick")
        t("rule", "passed", "no advice request")

        # Tier 1: exact label/alias mentions.
        t("tier1", "running", "looking for named concepts")
        mentions = self._distinct_mentions(question)
        hit, why = self._from_mentions(question, mentions)
        names = ", ".join(m.node for m in mentions) or "none"
        if hit:
            t("tier1", "done", f"found {names}; {hit.start} -> {hit.goal} ({hit.direction})")
            skip_rest("tier1", "not needed")
            return hit
        t("tier1", "passed", f"found {names}; {why}")

        # Tier 2: embedding similarity.
        candidates: list[tuple[str, float]] = []
        if self.index is None:
            t("tier2", "skipped", "embeddings not available")
        else:
            t("tier2", "running", "comparing the question with node descriptions")
            candidates = self.index.top_k(question, self.cfg.top_k)
            hit, why = self._from_embeddings(candidates)
            debug = "top-k: " + _fmt(candidates, self.cfg.top_k)
            if hit:
                t("tier2", "done", f"top: {_fmt(candidates)}; {hit.start} -> {hit.goal}", debug=debug)
                t("tier3", "skipped", "not needed")
                return hit
            t("tier2", "passed", f"top: {_fmt(candidates)}; {why}", debug=debug)

        # Tier 3: LLM constrained to real node ids.
        if self.llm is None:
            t("tier3", "skipped", "AI fallback not configured")
        else:
            started = time.perf_counter()  # _from_llm reports "running" with the prompt size
            try:
                result = self._from_llm(question, mentions, candidates, t)
            except Exception as exc:
                t("tier3", "failed", f"{type(exc).__name__}: {exc}"[:200])
                raise
            ms = round((time.perf_counter() - started) * 1000)
            outcome = "out of scope" if result.out_of_scope else f"{result.start} -> {result.goal}"
            t("tier3", "done", f"{outcome} in {ms} ms")
            return result

        if candidates and candidates[0][1] < self.cfg.floor:
            raise ResolutionError("Nothing in the graph matches that question closely enough.")
        raise ResolutionError(
            "Could not tell which two topics you mean. Name them directly, "
            "e.g. 'from free cash flow to the Black-Scholes model'."
        )

    # ------------------------------------------------------------------ tiers
    def _distinct_mentions(self, question: str) -> list[Mention]:
        seen, out = set(), []
        for m in find_mentions(question, self.lexicon):
            if m.node not in seen:
                seen.add(m.node)
                out.append(m)
        return out

    def _from_mentions(self, question: str, mentions: list[Mention]) -> tuple[Resolution | None, str]:
        """(resolution, why-not). why-not explains a hand-off to the next tier."""
        if len(mentions) == 2:
            start, goal, how = _order_two(question, mentions[0], mentions[1])
            return self._finalise(start, goal, "alias", "high" if how == "cues" else "medium", how), ""
        if len(mentions) == 1:
            if _cue_before(normalize(question), mentions[0]) == "start":
                return None, "only a starting point was named"  # needs the LLM to find the goal
            return self._finalise(None, mentions[0].node, "alias", "high", "goal_only"), ""
        if not mentions:
            return None, "no concept named exactly"
        return None, f"{len(mentions)} concepts named, too many to pick two"

    def _graph_order(self, a: str, b: str) -> tuple[str, str] | None:
        ab, ba = nx.has_path(self._forward, a, b), nx.has_path(self._forward, b, a)
        if ab and not ba:
            return a, b
        if ba and not ab:
            return b, a
        return None

    def _from_embeddings(self, candidates: list[tuple[str, float]]) -> tuple[Resolution | None, str]:
        """(resolution, why-not) for the embedding tier."""
        cfg = self.cfg
        above = [c for c in candidates if c[1] >= cfg.tau]
        rest = [c for c in candidates if c[1] < cfg.tau]
        next_score = rest[0][1] if rest else 0.0
        if not above:
            best = candidates[0][1] if candidates else 0.0
            return None, f"best score {best:.2f} below threshold {cfg.tau:.2f}"
        gap = above[-1][1] - next_score
        if gap < cfg.margin:
            return None, f"too close to call (gap {gap:.2f} < {cfg.margin:.2f})"
        if len(above) == 1:
            return self._finalise(None, above[0][0], "embedding", "medium", "goal_only", candidates), ""
        if len(above) == 2:
            order = self._graph_order(above[0][0], above[1][0])
            if order:
                return self._finalise(*order, "embedding", "medium", "graph", candidates), ""
            return None, "two matches but the graph gives no clear order"
        return None, f"{len(above)} nodes above threshold, too many to pick two"

    def _from_llm(
        self,
        question: str,
        mentions: list[Mention],
        candidates: list[tuple[str, float]],
        trace: Trace = _no_trace,
    ) -> Resolution:
        ids = list(self.G.nodes())
        schema = {
            "type": "OBJECT",
            "properties": {
                "start": {"type": "STRING", "enum": ids + [NONE]},
                "goal": {"type": "STRING", "enum": ids + [NONE]},
                "out_of_scope": {"type": "BOOLEAN"},
                "reason": {"type": "STRING"},
            },
            "required": ["start", "goal", "out_of_scope", "reason"],
        }
        catalog = "\n".join(
            f"{n} | {d.get('label', n)} | {d.get('type', '')} | {d.get('description', '')}"
            for n, d in self.G.nodes(data=True)
        )
        mentioned = [m.node for m in mentions]
        hints = ", ".join(mentioned + [n for n, _ in candidates[:5] if n not in mentioned])
        system = (
            "You map a learner's question onto a fixed finance knowledge graph and reply as JSON.\n"
            "start = the concept the learner says they already know or are starting from, else NONE.\n"
            "goal = the concept they want to learn or reach, else NONE.\n"
            "Use ONLY ids from the catalog. If the question asks for personal investment advice, stock "
            "picks, or anything unrelated to learning the catalog's concepts, set out_of_scope=true and "
            "goal=NONE. Questions about doing regulated work (advising clients, running a fund, executing "
            "trades for others, marketing backtests) should still map goal to the matching activity id; "
            "they are handled separately.\n\nCATALOG (id | label | type | description)\n" + catalog
        )
        prompt = f"Question: {question}\nPossibly relevant ids: {hints or 'none'}"
        trace("tier3", "running", "asking the AI to pick the topics",
              debug=f"prompt {len(system) + len(prompt)} chars; hints: {hints or 'none'}")
        data = self.llm.generate_json(system, prompt, schema)

        start, goal = data.get("start", NONE), data.get("goal", NONE)
        for value in (start, goal):
            if value != NONE and value not in self.G:
                raise ResolutionError(f"The model returned '{value}', which is not a node in the graph.")
        reason = str(data.get("reason", ""))
        if data.get("out_of_scope") or (goal == NONE and start == NONE):
            return Resolution(None, None, "llm", "medium", "llm", out_of_scope=True, reason=reason,
                              candidates=candidates)
        if goal == NONE:
            raise ResolutionError("I found what you already know but not what you want to reach. Add a goal.")
        return self._finalise(None if start == NONE else start, goal, "llm", "medium", "llm", candidates, reason)

    # ------------------------------------------------------------------ shared
    def _finalise(
        self,
        start: str | None,
        goal: str,
        method: str,
        confidence: str,
        direction: str,
        candidates: list[tuple[str, float]] | None = None,
        reason: str = "",
    ) -> Resolution:
        for node in (start, goal):
            if node is not None and node not in self.G:
                raise ResolutionError(f"'{node}' is not a node in the graph.")
        defaulted = start is None or start == goal
        if defaulted:
            start = default_start(self.G, goal)
        return Resolution(start, goal, method, confidence, direction, defaulted, False, reason,
                          candidates or [])
