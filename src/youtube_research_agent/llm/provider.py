"""LLM provider abstraction.

Three concrete providers:
  - AnthropicProvider (Claude) — preferred for narrative quality
  - OpenAIProvider                — fallback
  - HeuristicProvider             — deterministic fallback for tests / no-key runs

`get_provider()` picks the strongest available based on env vars.
"""

from __future__ import annotations

import os
from typing import Protocol


class LLMProvider(Protocol):
    """A provider takes a prompt + returns text."""

    name: str

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str: ...


# ---------------------------------------------------------------------------
# Anthropic (Claude)
# ---------------------------------------------------------------------------


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None,
                 model: str = "claude-sonnet-4-6") -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        try:
            import anthropic   # type: ignore
        except ImportError as e:
            raise RuntimeError("anthropic not installed: pip install anthropic") from e
        self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        client = self._get_client()
        msg = client.messages.create(
            model=self.model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # Concatenate text blocks
        out = []
        for block in msg.content:
            if getattr(block, "type", None) == "text":
                out.append(block.text)
        return "".join(out)


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None,
                 model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        try:
            from openai import OpenAI   # type: ignore
        except ImportError as e:
            raise RuntimeError("openai not installed: pip install openai") from e
        self._client = OpenAI(api_key=self.api_key)
        return self._client

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Heuristic fallback — no LLM, deterministic output
# ---------------------------------------------------------------------------


class HeuristicProvider:
    """Deterministic fallback when no LLM keys are set.

    Doesn't generate creative copy — but renders a structurally valid
    brief from the idea's own data so the pipeline still produces a
    usable document offline. Used in tests; used in CI; used when a
    user wants to run the rest of the pipeline without paying for LLM
    calls.
    """

    name = "heuristic"

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        # The brief generator's prompt always ends with a JSON skeleton —
        # the heuristic just echoes a known-shape JSON. The brief
        # generator itself handles the structural rendering; this provider
        # exists so the brief generator's "ask an LLM for creative copy"
        # branch can no-op cleanly.
        return ""


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def get_provider() -> LLMProvider:
    """Return the strongest provider for which credentials are present.

    Order: Anthropic > OpenAI > Heuristic fallback.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicProvider()
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIProvider()
    return HeuristicProvider()
