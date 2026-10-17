# Deployment

The evaluation service needs one setting beyond the template: `TARGET_URL`, the base URL of the system under test (fde-02). Everything else is optional: an `MISTRAL_API_KEY` for the LLM judge, and `OTEL_EXPORTER_OTLP_ENDPOINT` for traces.

| Path | Command | `TARGET_URL` | Details |
| --- | --- | --- | --- |
| Local Python | `make run` / `make e2e`; `make sut-up` starts fde-02 on :8001 | `http://127.0.0.1:8001` (default) | [Quick start](../README.md#quick-start) |
| Docker Desktop | `make up-docker`; add `--profile sut --profile observability` | `http://sut:8000` (Compose default) | [Desktop labs](learning/DESKTOP-LABS.md#2-evaluate-fde-02-in-containers-with-traces-any-desktop) |
| Podman Desktop | `make up-podman` | `http://host.containers.internal:8001` | fde-02 on the host |
| Rancher Desktop | `make up-rancher` | same as Docker | |
| Local Kubernetes | `make k8s-docker`, `make k8s-rancher`, `make k8s-kind`; jobs: `kubectl apply -k deploy/kubernetes/jobs` | fde-02's Service in namespace `fde` (ConfigMap) | Deploy fde-02 to the same cluster first |
| Helm | `helm upgrade --install fde-03-evaluation deploy/helm/fde-03-evaluation --set config.TARGET_URL=http://fde-02-llm-applications` | `values.yaml: config.TARGET_URL` | `--set route.enabled=true` on OpenShift |
| OpenShift | `oc apply -k deploy/openshift` | ConfigMap | Route with edge TLS |
| AWS / Azure / GCP | `make tf-<cloud>-plan -var target_url=<fde-02 url>` | `target_url` variable | [Cloud labs](learning/CLOUD-LABS.md) |

## Release

1. Run `make eval-offline`, publish the runs you cite (`rag-eval publish`), and update the README results and `docs/RELEASE-READINESS.md`.
2. Update `CHANGELOG.md` and bump the version in `pyproject.toml`, `src/rag_eval/__init__.py`, `Chart.yaml` and the Terraform `image_tag` defaults.
3. Tag `vX.Y.Z` and push it. The `publish-starter` workflow regenerates the starter repo.
4. When fde-02 releases, refresh its baseline: `rag-eval baseline runs/<label>-advanced-financebench --out evals/baselines/financebench-test-advanced-<label>.jsonl`, and point `gate.yml` at it.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Every case has `error: ConnectError` | `TARGET_URL` is wrong or fde-02 is down: `curl $TARGET_URL/health/ready` |
| `sut.py`: "SUT runs 'bm25', config wants 'hybrid'" | fde-02's index has no dense vectors: `filing-assistant embed lsa` |
| p95 latency far above the published runs | A cold system under test. `sut.py` warms it up; when you start fde-02 yourself, send two questions first |
| Gate fails on `regression:*` | Compare the two runs with `rag-eval report`; failures are in `cases.jsonl` (`/api/v1/runs/<id>/cases?only_failures=true`) |
| Gate fails on `redteam:*` | `runs/<label>-redteam/redteam-cases.jsonl` lists each failed check with what triggered it |
| `golden verify` fails | Someone edited the items: rebuild (`golden build --force`) or create a new version |
