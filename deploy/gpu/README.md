# GPU providers

Reserved for repos that need a GPU (fde-04 to fde-06). Each provider gets a folder with the
same three entry points, so labs can switch provider without code changes:

| File | Purpose |
| --- | --- |
| `deploy/gpu/<provider>/README.md` | Account setup, spending limit, region choice, data-handling notes |
| `deploy/gpu/<provider>/train.*` | Launch a fine-tuning job (pod or serverless function) with auto-stop |
| `deploy/gpu/<provider>/serve.*` | Start an OpenAI-compatible vLLM endpoint with scale-to-zero |

Planned providers: `runpod/` (default), `modal/`, `vastai/`. Budget: USD 100 per month across
fde-04 to fde-06; see `docs/COST-TCO.md` in each GPU repo for the dated price table.
