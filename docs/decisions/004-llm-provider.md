# ADR-004: OpenRouter as the LLM provider

Status: accepted, 2026-10-03

## Context
Upstream was wired to OpenAI via `init_chat_model("openai:...")`, with optional Groq and Ollama.
We want one key and one bill across many models, so Phase 1 can pick the default by measurement.

## Decision
Use OpenRouter through LangChain's `ChatOpenAI` with `base_url=https://openrouter.ai/api/v1`.
`SCOUT_MODEL` holds an OpenRouter model id (`openai/gpt-4o-mini`). The default is a placeholder
until Phase 1 chooses by cost and structured-output reliability.
The Groq extra and `provider:model` strings are removed.

## Consequences
- Changing model is one env var; any OpenAI-compatible endpoint works via `LLM_BASE_URL`.
- Opik's built-in pricing may not recognise OpenRouter ids. Cost comes from OpenRouter's response
  `usage` and goes into trace metadata (Phase 1). A `$0.00` Opik cost is not real.
- We depend on OpenRouter's structured-output support per model; Phase 1 measures it.
