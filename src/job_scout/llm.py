"""Chat-model factory and the per-run LLM call budget.

The call budget is a simple circuit breaker: every node reads the running
``llm_calls`` counter from state, checks it against ``MAX_LLM_CALLS_PER_RUN``
before calling the model, and returns the incremented total. The graph runs
sequentially, so returning the cumulative total (not a delta) keeps the counter
correct.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from job_scout.config import get_settings


class LLMBudgetExceededError(RuntimeError):
    """Raised when a run would exceed ``MAX_LLM_CALLS_PER_RUN``."""


@lru_cache(maxsize=8)
def get_chat_model(model: str, temperature: float = 0.0) -> BaseChatModel:
    """Return a cached chat model for an OpenRouter model id (e.g. ``openai/gpt-4o-mini``)."""
    settings = get_settings()
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        base_url=settings.llm_base_url,
        api_key=settings.openrouter_api_key,
    )


def ensure_budget(current_calls: int, planned: int, max_calls: int) -> None:
    """Raise ``LLMBudgetExceededError`` if ``planned`` more calls would exceed ``max_calls``."""
    if current_calls + planned > max_calls:
        raise LLMBudgetExceededError(
            f"Run would make {current_calls + planned} LLM calls, exceeding MAX_LLM_CALLS_PER_RUN={max_calls}."
        )
