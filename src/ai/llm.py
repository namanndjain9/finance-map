"""Thin provider-agnostic LLM wrapper. The only implementation is Google Gemini's free tier.

Anything with these two methods can stand in for it (tests use a fake):

    generate_json(system, prompt, schema) -> dict
    stream_text(system, prompt) -> Iterator[str]

Set GEMINI_API_KEY (free key from Google AI Studio) in the environment or a local .env.
Note: on the free tier Google may use prompts to improve its products. This app only
sends the user's question and graph content.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Iterator, Protocol

from src.ai.config import CACHE_DIR, DEFAULT_GEMINI_MODEL


class LLMError(Exception):
    """The provider failed or returned nothing usable."""


class LLMUnavailable(LLMError):
    """No API key or SDK is available."""


class LLMClient(Protocol):
    def generate_json(self, system: str, prompt: str, schema: dict) -> dict: ...
    def stream_text(self, system: str, prompt: str) -> Iterator[str]: ...


RETRYABLE_CODES = {429, 500, 503}  # 504 (deadline exceeded) is not retried: it already used the full timeout


class GeminiClient:
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        cache_dir: str | Path | None = CACHE_DIR / "llm",
        max_retries: int | None = None,
        timeout_s: float | None = None,
    ):
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise LLMUnavailable("GEMINI_API_KEY is not set (get a free key at aistudio.google.com).")
        try:
            from google import genai
            from google.genai import errors, types
        except ImportError as exc:
            raise LLMUnavailable("google-genai is not installed (pip install -r requirements-ai.txt).") from exc

        self._types, self._errors = types, errors
        # The SDK has no request timeout by default, so a stalled call would hang the run forever.
        self.timeout_s = timeout_s if timeout_s is not None else float(os.environ.get("GEMINI_TIMEOUT_S", "25"))
        # attempts=1 turns off the SDK's own retries; _with_retry decides, so the worst-case wait is
        # (max_retries + 1) x timeout instead of being silently doubled (seen: 504 at 25 s, then again).
        self._client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=int(self.timeout_s * 1000), retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )
        self.model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._max_retries = max_retries if max_retries is not None else int(os.environ.get("GEMINI_MAX_RETRIES", "1"))

    # ------------------------------------------------------------------ cache
    def _cache_file(self, kind: str, *parts: str) -> Path | None:
        if not self._cache_dir:
            return None
        digest = hashlib.sha256("\x00".join([kind, self.model, *parts]).encode()).hexdigest()
        return self._cache_dir / f"{digest}.json"

    @staticmethod
    def _read(path: Path | None):
        if path and path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    @staticmethod
    def _write(path: Path | None, value) -> None:
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value), encoding="utf-8")

    # ------------------------------------------------------------------ retry
    def _with_retry(self, call):
        for attempt in range(self._max_retries + 1):
            try:
                return call()
            except self._errors.APIError as exc:
                if getattr(exc, "code", None) not in RETRYABLE_CODES or attempt == self._max_retries:
                    raise LLMError(f"Gemini request failed: {exc}") from exc
                time.sleep(min(2 ** (attempt + 1), 30))  # free-tier rate limits are per minute
            except Exception as exc:  # timeouts and transport errors: not retried, so the wait stays bounded
                raise LLMError(f"Gemini request failed ({type(exc).__name__}, timeout {self.timeout_s:g}s)") from exc

    # ------------------------------------------------------------------ api
    def generate_json(self, system: str, prompt: str, schema: dict) -> dict:
        cache = self._cache_file("json", system, prompt, json.dumps(schema, sort_keys=True))
        cached = self._read(cache)
        if cached is not None:
            return cached
        config = self._types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,
        )
        response = self._with_retry(
            lambda: self._client.models.generate_content(model=self.model, contents=prompt, config=config)
        )
        try:
            data = json.loads(response.text)
        except (TypeError, ValueError) as exc:
            raise LLMError("Gemini returned no valid JSON.") from exc
        self._write(cache, data)
        return data

    def stream_text(self, system: str, prompt: str) -> Iterator[str]:
        cache = self._cache_file("text", system, prompt)
        cached = self._read(cache)
        if cached is not None:
            yield cached
            return
        config = self._types.GenerateContentConfig(system_instruction=system, temperature=0.3)
        pieces: list[str] = []
        try:
            for chunk in self._client.models.generate_content_stream(
                model=self.model, contents=prompt, config=config
            ):
                if chunk.text:
                    pieces.append(chunk.text)
                    yield chunk.text
        except self._errors.APIError as exc:
            raise LLMError(f"Gemini stream failed: {exc}") from exc
        except Exception as exc:  # timeouts and transport errors
            raise LLMError(f"Gemini stream failed ({type(exc).__name__}, timeout {self.timeout_s:g}s)") from exc
        if not pieces:
            raise LLMError("Gemini returned an empty response (possibly blocked by safety filters).")
        self._write(cache, "".join(pieces))


def try_create_llm(**kwargs) -> GeminiClient | None:
    """A Gemini client, or None when no key / SDK is available."""
    try:
        return GeminiClient(**kwargs)
    except LLMUnavailable:
        return None
