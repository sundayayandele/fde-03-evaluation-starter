# Infrastructure

The evaluation service is light (56 MB resident with 20 runs on disk). The system under test, fde-02, sits next to it on every path.

| Environment | Evaluation service | System under test (`TARGET_URL`) | Evaluation jobs | Telemetry |
| --- | --- | --- | --- | --- |
| Local Python | uvicorn :8000 | `scripts/sut.py` starts fde-02 on :8001 | `make eval-offline` | `/metrics/`; Jaeger if `OTEL_EXPORTER_OTLP_ENDPOINT` is set |
| Docker / Rancher Desktop | Compose `api` | Compose `sut` profile builds fde-02 from `FDE02_DIR` | `docker compose run --rm api rag-eval …` | `observability` profile: Prometheus, Grafana, Jaeger |
| Podman Desktop | `podman kube play` | fde-02 on the host, `host.containers.internal:8001` | `podman exec` into the pod | same |
| Kubernetes (Docker Desktop, Rancher, kind) | Deployment + Service | fde-02's Service in namespace `fde` | CronJob `fde-03-redteam` (`deploy/kubernetes/jobs`) | Prometheus annotations; Grafana dashboard `evaluation.json` |
| OpenShift / Helm | Route / chart; `config.TARGET_URL` | fde-02's chart in the same namespace | the same CronJob | cluster monitoring |
| AWS / Azure / GCP | Fargate / Container Apps / Cloud Run | `target_url` variable: fde-02's URL from its own Terraform output | CI (`release-gate` workflow) rather than cloud jobs | CloudWatch / Log Analytics / Cloud Logging |

Runs started through `POST /api/v1/runs` write to `/tmp/runs` inside the container (read-only root filesystem), so they disappear with the pod. The durable record is the CLI or CI run, published to `evals/results/`. The service image carries the golden sets that may be redistributed, plus the published results.
