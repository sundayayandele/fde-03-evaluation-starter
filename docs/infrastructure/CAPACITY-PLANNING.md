# Capacity planning

Measured on 2026-10-16, 2 vCPU (Xeon 2.1 GHz).

| Workload | Measured | Bound by |
| --- | --- | --- |
| A run of 71 FinanceBench questions against fde-02 `advanced` (concurrency 4) | 20.2 s of summed answer time, about 5 s wall-clock | The system under test (p50 276 ms per answer) |
| The same against `basic` | 2.9 s summed, under 1 s wall | The system under test |
| Calibration of the reference judge (390 cases) | 0.27 s, 40 MB | CPU, trivial |
| `make eval-offline` end to end (after fde-02's index exists) | 51 s for 8 fde-02 start-ups and 12 runs (re-run: identical rates, p95 latency within ±15%) | fde-02 index load and warm-up |
| Building fde-02's FinanceBench index | 334–364 s | PDF extraction and OCR; cached in CI |
| Evaluation service, `GET /api/v1/runs` with 20 runs on disk | p50 47 ms, p95 77 ms; `/metrics/` 45 ms; 56 MB resident | File reads at scrape time |

## Sizing

- **Service:** 100m CPU / 128 MiB requested, 500m / 512 MiB limit. A replica serves dashboards and the judge endpoint. Run evaluations as jobs, not through the service.
- **Concurrency against the system under test:** the default of 4 suits a 1-vCPU fde-02 replica. More concurrency measures queueing rather than answering. Raise it only with more replicas, and report it in the run config (it is recorded).
- **LLM runs:** bound by provider rate limits. At concurrency 4 and an estimated 2–4 s per Mistral answer plus a judge call, a 71-question run would take a few minutes. That is an estimate until `make eval-llm` runs.
