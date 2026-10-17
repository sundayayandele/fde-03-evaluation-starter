# Monitoring

| File | Purpose |
| --- | --- |
| `prometheus.yml` | Scrapes the evaluation service and, with the `sut` profile, fde-02 |
| `alerts.yml` | Service health; `RedTeamCriticalFailure` (a run with a critical category below 100%); `FalseRefusalsHigh` (above 5%) |
| `grafana/dashboards/evaluation.json` | Accuracy, hit@5, false refusals and p95 latency per run; red-team pass rate by category; service and SUT request rates |
| `grafana/dashboards/service.json` | The template's service overview |

```bash
docker compose -f deploy/compose/compose.yaml --profile observability --profile sut up -d --build
# Evaluation UI http://127.0.0.1:8000 · Grafana http://127.0.0.1:3000 · Jaeger http://127.0.0.1:16686
docker compose -f deploy/compose/compose.yaml run --rm \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318 api \
  rag-eval run --golden refusal --split all --label compose
```

The `eval_*` gauges are read from run files at scrape time (`RunCollector` in `app/main.py`), so a dashboard shows exactly what is on disk: published results in the image plus runs made in the container. Traces carry case ids, labels and timings, never question or answer text.
