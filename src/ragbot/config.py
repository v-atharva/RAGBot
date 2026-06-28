"""Central application settings.

Replaces the project's ad-hoc ``os.environ`` reads with one typed, env-driven Settings
object (pydantic-settings). The LLM seam is provider-agnostic: ``LLM_PROVIDER`` selects a
local Ollama backend (default, for the demo) or a hosted Anthropic backend (for when the
project is deployed online with an API key) — swapping is a config change, not a refactor.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM provider seam ---
    llm_provider: str = "ollama"  # LLM_PROVIDER = ollama | anthropic
    ollama_base_url: str = "http://localhost:11434"  # OLLAMA_BASE_URL
    ollama_model: str = "qwen3.5:9b"  # OLLAMA_MODEL
    ollama_num_ctx: int = 16384  # context window; default 4096 overflows on grounded prompts
    ollama_keep_alive: str = "10m"  # OLLAMA_KEEP_ALIVE: how long Ollama keeps the model resident
    llm_api_key: str = ""  # LLM_API_KEY (hosted backend, later)
    anthropic_model: str = "claude-sonnet-4-5"  # ANTHROPIC_MODEL (later)
    request_timeout: float = 180.0

    # --- corpus / index paths (mirror .env.example) ---
    transcripts_dir: str = "transcripts"  # TRANSCRIPTS_DIR
    materials_dir: str = "misccontext/raw"  # MATERIALS_DIR
    index_dir: str = "data/index"  # INDEX_DIR
    embed_model: str = "BAAI/bge-small-en-v1.5"  # EMBED_MODEL
    summaries_dir: str = "generated_summaries"
    deadlines_path: str = "misccontext/deadlines.json"

    # --- retrieval knobs ---
    retrieval_k: int = 8
    # Assignment guardrail: when True, solution-key / exam-review chunks (sensitivity=high) are
    # withheld from retrieval so the tutor won't hand over PE/HW answers. Default False — the
    # tutor may use those sources and fully solve assignment questions. (Grounding/citations are
    # unaffected; this only governs which sources the model is allowed to see.)
    block_solution_keys: bool = False

    # --- synthesis knobs ---
    # Course-wide synthesis runs slightly warmer for richer prose (analogies/examples) while
    # staying low enough to keep citations accurate; validate changes against the eval golden set.
    course_wide_temperature: float = 0.3
    # Cap conversation history threaded into prompts (oldest turns dropped beyond this).
    max_history_turns: int = 6

    @property
    def chroma_dir(self) -> str:
        return f"{self.index_dir}/chroma"

    @property
    def active_model(self) -> str:
        return self.ollama_model if self.llm_provider == "ollama" else self.anthropic_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
