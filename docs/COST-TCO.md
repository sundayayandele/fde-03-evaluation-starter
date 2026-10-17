# Cost and total cost of ownership

## What costs money

| Item | Driver | Measured / estimate |
| --- | --- | --- |
| Offline evaluation (reference judge, extractive SUT) | CPU minutes on the CI runner | Free on GitHub-hosted runners for public repos; 51 s per full run once the FinanceBench index exists (measured locally on 2 vCPU); the index build takes about 6 min and is cached |
| LLM judge | 1 call per case on `mistral-large-latest` | Pending: record `cost_usd` from `make eval-llm`. At the **assumed** prices in `config/providers.yaml` (USD 2.00 / 6.00 per million tokens in / out) and ~600 tokens in, 60 out per verdict: **estimate** USD 0.0016 per case, ~USD 0.11 per 71-case run |
| Prompt-only baseline and LLM SUT answers | `mistral-small-latest` | Pending; recorded per run from the SUT's `cost_usd` |
| Evaluation service | One small container | Inside the template's cloud lab budget (USD 50 per month per cloud) |
| Human labelling | 40 answers, about 1 hour of an analyst | The most expensive item, and the one that validates the judge |

## Price table (verify before quoting)

| Item | Unit | Price | Source page | Checked on |
| --- | --- | --- | --- | --- |
| Mistral Large (judge) | per million tokens in / out | 2.00 / 6.00 (assumed, in `providers.yaml`) | mistral.ai/pricing | not checked: the build sandbox cannot reach it |
| Mistral Small (SUT, prompt-only) | per million tokens in / out | 0.10 / 0.30 (assumed) | mistral.ai/pricing | not checked |
| AWS Fargate / Azure Container Apps / GCP Cloud Run | vCPU and GB per hour or second | see each stack README | provider pricing pages | fill in when you run a lab |

## How to compute

```text
cost_per_run = cases × (judge_tokens_in × price_in + judge_tokens_out × price_out)
             + cases × sut_cost_per_answer            # from the SUT's cost_usd
monthly      = runs_per_month × cost_per_run + service_hours × container_price
```

Use the `usage` and `cost_usd` recorded in `cases.jsonl`, not estimates, once an LLM run exists.

## Lab budget

USD 50 per month per cloud. Every stack creates a budget alert; every lab ends with `destroy`.
