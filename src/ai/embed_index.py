"""Cosine-similarity index over node text, backed by a local sentence-transformers model."""

import hashlib
from pathlib import Path
from typing import Callable

import networkx as nx
import numpy as np

from src.ai.config import CACHE_DIR, DEFAULT_EMBED_MODEL

Encoder = Callable[[list[str]], np.ndarray]


def node_text(G: nx.DiGraph, node: str) -> str:
    d = G.nodes[node]
    text = f"{d.get('label', node)} ({d.get('type', '')}): {d.get('description', '')}"
    aliases = d.get("aliases", [])
    return f"{text} Also called: {', '.join(aliases)}." if aliases else text


def sentence_transformer_encoder(model_name: str) -> Encoder:
    from sentence_transformers import SentenceTransformer  # heavy import, kept lazy

    model = SentenceTransformer(model_name)
    return lambda texts: model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def _unit(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


class NodeIndex:
    """Embeds every node once; `top_k` ranks nodes by cosine similarity to a question."""

    def __init__(
        self,
        G: nx.DiGraph,
        encoder: Encoder | None = None,
        model_name: str = DEFAULT_EMBED_MODEL,
        cache_path: str | Path | None = CACHE_DIR / "node_embeddings.npz",
    ):
        self.nodes = list(G.nodes())
        self._texts = [node_text(G, n) for n in self.nodes]
        self._encoder = encoder or sentence_transformer_encoder(model_name)
        digest = hashlib.sha256((model_name + "\n" + "\n".join(self._texts)).encode()).hexdigest()
        self._matrix = self._load_or_build(digest, Path(cache_path) if cache_path else None)

    def _load_or_build(self, digest: str, cache_path: Path | None) -> np.ndarray:
        if cache_path and cache_path.is_file():
            cached = np.load(cache_path, allow_pickle=False)
            if str(cached["digest"]) == digest:
                return cached["matrix"]
        matrix = _unit(np.asarray(self._encoder(self._texts), dtype=np.float32))
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(cache_path, matrix=matrix, digest=np.array(digest))
        return matrix

    def top_k(self, question: str, k: int = 8) -> list[tuple[str, float]]:
        query = _unit(np.asarray(self._encoder([question]), dtype=np.float32))[0]
        scores = self._matrix @ query
        order = np.argsort(-scores)[:k]
        return [(self.nodes[i], float(scores[i])) for i in order]


def try_create_index(G: nx.DiGraph, **kwargs) -> NodeIndex | None:
    """Build the index, or return None when sentence-transformers or the model is unavailable."""
    try:
        return NodeIndex(G, **kwargs)
    except Exception:  # missing package, offline first run, corrupt cache
        return None
