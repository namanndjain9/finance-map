"""Settings for the AI layer. Reads a local .env (never committed) into os.environ."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = REPO_ROOT / "graph.yaml"
CACHE_DIR = REPO_ROOT / ".cache"

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"  # override with GEMINI_MODEL
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # override with EMBED_MODEL

DISCLAIMER = (
    "This roadmap is a learning aid built from a study graph. It is not investment, "
    "legal, or registration advice."
)


def load_env(path: str | Path | None = None) -> None:
    """Set KEY=VALUE pairs from .env without overriding real environment variables."""
    env_path = Path(path) if path else REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
