"""Provider-agnostic LLM client.

A thin seam over chat-completion backends so the rest of the tutor never imports a vendor
SDK directly. Today it talks to a local Ollama server (the demo default); a hosted Anthropic
backend is wired behind the same ``chat()`` interface for when the project goes online.

The configured Ollama model (``qwen3.5:9b``) is a *thinking* model: it emits a
``<think>...</think>`` reasoning trace before the answer. :func:`strip_think` removes it
centrally so callers always get clean prose, regardless of backend.
"""

from __future__ import annotations

import re
from typing import Protocol

import httpx

from ragbot.config import Settings

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class LLMError(RuntimeError):
    """Raised when a backend is unreachable or returns an error."""


def strip_think(text: str) -> str:
    """Remove a thinking-model ``<think>...</think>`` trace; tolerate an unclosed tag."""
    cleaned = _THINK_RE.sub("", text)
    if "<think>" in cleaned and "</think>" not in cleaned:
        cleaned = cleaned.split("<think>", 1)[0]
    return cleaned.strip()


class LLMClient(Protocol):
    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str: ...


class OllamaClient:
    """Local Ollama backend (POST {base_url}/api/chat)."""

    def __init__(
        self, base_url: str, model: str, timeout: float = 180.0, num_ctx: int = 16384
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.num_ctx = num_ctx

    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            # qwen3.5 is a thinking model; we want the answer, not the reasoning trace.
            # Disabling it avoids the trace consuming the token budget (which left the
            # answer empty), and is much faster for an interactive UI.
            "think": False,
            "options": {"temperature": temperature, "num_ctx": self.num_ctx},
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/api/chat", json=payload, timeout=self.timeout
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(
                f"Ollama request to {self.base_url} failed: {exc}. "
                "Is `ollama serve` running and the model pulled?"
            ) from exc
        content = (resp.json().get("message") or {}).get("content", "")
        return strip_think(content)


class AnthropicClient:
    """Hosted Anthropic backend (used when LLM_PROVIDER=anthropic)."""

    def __init__(self, api_key: str, model: str, timeout: float = 180.0):
        if not api_key:
            raise LLMError("LLM_API_KEY is required when LLM_PROVIDER=anthropic.")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def chat(self, system: str, user: str, *, temperature: float = 0.2) -> str:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise LLMError("The `anthropic` package is not installed.") from exc
        client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)
        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # noqa: BLE001 - surface any SDK error uniformly
            raise LLMError(f"Anthropic request failed: {exc}") from exc
        parts = [
            getattr(b, "text", "")
            for b in message.content
            if getattr(b, "type", None) == "text"
        ]
        return strip_think("".join(parts))


def get_llm(settings: Settings) -> LLMClient:
    """Construct the backend selected by ``settings.llm_provider``."""
    if settings.llm_provider == "anthropic":
        return AnthropicClient(
            settings.llm_api_key, settings.anthropic_model, settings.request_timeout
        )
    return OllamaClient(
        settings.ollama_base_url,
        settings.ollama_model,
        settings.request_timeout,
        settings.ollama_num_ctx,
    )
