# Desktop labs: Docker Desktop, Podman Desktop, Rancher Desktop

Every FDE repo runs on all three desktops, first as containers, then on local Kubernetes. Do the lab on the desktop you have; doing it on a second one is the best way to understand what is engine-specific and what is not.

> Run only **one** desktop engine at a time. Two engines fight over port 8000, the Docker socket and kubectl contexts.

## Sizing

| Profile | CPU | RAM | Free disk |
| --- | --- | --- | --- |
| API container only | 1 vCPU | 1 GiB | 5 GiB |
| API + Prometheus + Grafana | 2 vCPU | 2 GiB | 8 GiB |
| Desktop engine VM (Windows/macOS) | 2-4 CPUs | 4 GiB minimum, 6-8 GiB comfortable | 20 GiB |
| Local Kubernetes on top | +1 CPU | +2 GiB | +5 GiB |

The evaluation service itself needs little (56 MB resident, measured); the system under test, fde-02, needs up to 1.5 GiB. GPU work in fde-04 to fde-06 never runs on the desktop; the desktop stack calls a remote GPU endpoint or the Mistral API.

## 0. Prepare (all desktops)

```bash
git clone https://github.com/<you>/<repo>.git && cd <repo>
python3.12 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
make install && make test && make e2e                       # proves the code before containers
cp .env.example .env                                        # add MISTRAL_API_KEY if the repo needs it
```

Windows users: run the labs from WSL2 (Ubuntu) for `make` and the shell syntax used here.

## 1A. Docker Desktop

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), start it, and in **Settings → Resources** give it at least 2 CPUs, 4 GiB RAM and 20 GiB disk.
2. Containers:

   ```bash
   make up-docker            # docker compose build + up, then the smoke test
   docker compose -f deploy/compose/compose.yaml ps
   docker compose -f deploy/compose/compose.yaml logs --tail=50 api
   make down-docker
   ```

3. Kubernetes: **Settings → Kubernetes → Enable Kubernetes**, wait for the green light, then:

   ```bash
   make k8s-docker           # builds, applies the docker-desktop overlay, port-forwards, smoke test
   kubectl --context docker-desktop -n fde get pods,svc,hpa,pdb
   make k8s-delete
   ```

## 1B. Podman Desktop

1. Install [Podman Desktop](https://podman-desktop.io/). On Windows and macOS, create and start a Podman machine (2+ CPUs, 4+ GiB):

   ```bash
   podman machine init --cpus 2 --memory 4096 --disk-size 30
   podman machine start
   podman info | head
   ```

2. Pod (the Kubernetes-style path):

   ```bash
   make up-podman            # podman build + podman kube play deploy/podman/pod.yaml + smoke test
   podman pod ps && podman logs fde-03-evaluation-api
   make down-podman
   ```

   API keys: `podman secret create fde-03-evaluation-mistral-key - <<< "$MISTRAL_API_KEY"` (repos that need keys document how the pod mounts it).

3. Compose alternative: `make up-podman-compose` (needs `podman compose`, which uses docker-compose or podman-compose).
4. Kubernetes with kind: install [kind](https://kind.sigs.k8s.io/), or install it through Podman Desktop's Kind integration, then:

   ```bash
   export KIND_EXPERIMENTAL_PROVIDER=podman
   make k8s-kind             # creates cluster 'fde', loads the image, applies the kind overlay, smoke test
   kind delete cluster --name fde
   ```

Notes: Podman is rootless by default, which matches the non-root image. On SELinux hosts (Fedora, RHEL) add `:Z` to bind mounts you create yourself.

## 1C. Rancher Desktop

1. Install [Rancher Desktop](https://rancherdesktop.io/). In **Preferences → Container Engine** choose **dockerd (moby)**; in **Preferences → Kubernetes** enable Kubernetes. Give the VM 2+ CPUs and 4+ GiB.
2. Rancher Desktop sets a `rancher-desktop` Docker context. Containers:

   ```bash
   docker context ls
   make up-rancher           # docker --context rancher-desktop compose up, then the smoke test
   make down-rancher
   ```

3. Kubernetes (k3s). With the moby engine, k3s sees images you build, so no registry is needed:

   ```bash
   make k8s-rancher          # build, apply the rancher-desktop overlay, port-forward, smoke test
   kubectl --context rancher-desktop -n fde get pods
   make k8s-delete
   ```

   Using the **containerd** engine instead? Build with `nerdctl --namespace k8s.io build -t fde-03-evaluation:local .` and run `make k8s-rancher RANCHER="nerdctl --namespace k8s.io"`.

## 2. Evaluate fde-02 in containers, with traces (any desktop)

Clone fde-02 next to this repo (or set `FDE02_DIR`). The `sut` profile builds it with its demo corpus; the `observability` profile adds Prometheus, Grafana and Jaeger.

```bash
docker compose -f deploy/compose/compose.yaml --profile sut --profile observability up -d --build
docker compose -f deploy/compose/compose.yaml run --rm \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318 api \
  rag-eval run --golden refusal --split all --label compose-v1.1
# Evaluation UI http://127.0.0.1:8000 · Grafana http://127.0.0.1:3000 → "FDE 03 · RAG evaluation"
# Jaeger http://127.0.0.1:16686 → service rag-eval → one trace per case, X-Trace-Id on fde-02's response
```

The SUT image bakes the demo corpus only (`SUT_CORPUS=sample` bakes 6 FinanceBench filings). The FinanceBench numbers in the README come from the local Python path (`make eval-offline`). Runs made in a container live in its `/tmp/runs` and disappear with it: publish what you keep.

## 3. Evidence for your portfolio

Capture:

- the smoke-test output;
- `kubectl get pods` showing Ready, and the red-team CronJob (`kubectl apply -k deploy/kubernetes/jobs`, then `kubectl -n fde create job --from=cronjob/fde-03-redteam now`) with its log;
- a Grafana screenshot of the evaluation dashboard;
- a Jaeger trace of one case;
- the commit SHA.

Note which desktop and versions you used.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `port is already allocated` | Another engine or old stack on 8000 | Stop the other desktop; `make down-*`; or `HOST_PORT=8080 make up-docker` |
| Pod `ImagePullBackOff` on desktop Kubernetes | Cluster cannot see the local image | Docker/Rancher: build with the same engine as the cluster. kind: re-run `make k8s-kind` (it loads the image) |
| `CreateContainerConfigError` | Missing Secret referenced as required | The base marks the Secret optional; check you did not change that |
| Podman `kube play` port not reachable | Podman machine not running | `podman machine start` |
| Rancher `docker: context not found` | Engine set to containerd | Switch to dockerd (moby) or use `nerdctl` as above |
| Smoke test times out | Container crashed on start | `docker compose ... logs api`, `podman logs`, or `kubectl logs` |
