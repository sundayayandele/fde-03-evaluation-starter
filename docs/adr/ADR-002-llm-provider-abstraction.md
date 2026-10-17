# ADR-002: Provider-agnostic LLM client with a data-residency guard

- **Status:** Accepted
- **Date:** 2026-10-13

## Context

The series uses Mistral by default, and compares OpenAI, DeepSeek, Qwen, Kimi and self-hosted open weights. The flagship pilot handles banking complaints, which are regulated personal data. Some hosted APIs are operated outside the EU.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Each vendor's own SDK | Full feature access | Five SDKs; code changes to switch provider |
| A gateway library (for example LiteLLM) | Many providers, retries, cost tracking | Extra dependency and abstraction for learners to understand |
| **Thin OpenAI-compatible client + `providers.yaml`** | Small, readable, no vendor SDKs; switch by config | Vendor-specific features need extra code |

## Decision

All providers are called through `src/rag_eval/llm.py` using the OpenAI-compatible chat completions API. Providers, base URLs, key variables and model names per role live in `config/providers.yaml`. Each provider declares `regulated_data_allowed`; `chat(..., contains_regulated_data=True)` raises `DataResidencyError` for any provider not allowed to receive such data. Model IDs default to `PIN_AT_BUILD_TIME` and must be pinned, with an ADR, before use.

## Consequences

- Switching provider for evals or cost comparisons is a configuration change.
- Regulated data cannot reach a non-sovereign provider by accident through this client.
- Phase repos that need embeddings, OCR, fine-tuning or moderation add focused functions next to `chat`, keeping the same configuration.
- Base URLs and model names must be verified against each provider's documentation at build time.
