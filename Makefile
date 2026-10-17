# One entry point for every path: local Python, three desktops, local Kubernetes,
# OpenShift, Helm and three clouds. Run `make help` for the list.
#
# Desktops:  Docker Desktop (docker), Podman Desktop (podman), Rancher Desktop
#            (dockerd/moby engine via the rancher-desktop docker context, or nerdctl).
# Run only ONE desktop engine at a time to avoid port and socket clashes.

SHELL      := /bin/bash
APP        ?= fde-03-evaluation
LOADENV    := set -a; [ -f .env ] && . ./.env; set +a;
IMAGE      ?= $(APP):local
HOST_PORT  ?= 8000
BASE_URL   ?= http://127.0.0.1:$(HOST_PORT)
PY         ?= python
COMPOSE    := deploy/compose/compose.yaml
NAMESPACE  ?= fde
RANCHER    ?= docker --context rancher-desktop   # or: nerdctl --namespace k8s.io
KIND_NAME  ?= fde

.DEFAULT_GOAL := help

## ---- Local Python -------------------------------------------------------
install: ## Create the dev environment (pip editable install with dev extras)
	$(PY) -m pip install -e ".[dev]"

lint: ## Ruff lint (starter repos ignore unused-import noise from TODO stubs)
	@if [ -f .starter ]; then ruff check . --extend-ignore F401,F841,ARG001; else ruff check .; fi

fmt: ## Auto-format and fix imports
	ruff check . --fix && ruff format .

test: ## Unit and API tests (reference: with coverage gate; starter: skips exercises)
	@if [ -f .starter ]; then pytest -m "not exercise"; else pytest --cov --cov-report=term-missing; fi

exercises: ## Run the learner exercise tests (they fail until the TODOs are done)
	pytest -m exercise

structure: ## Check the required repo structure is present
	$(PY) scripts/check_structure.py

run: ## Run the API locally with reload
	uvicorn app.main:app --reload --port $(HOST_PORT)

e2e: ## Start the API locally, run the smoke checks, stop it
	@uvicorn app.main:app --port $(HOST_PORT) > /tmp/$(APP)-e2e.log 2>&1 & echo $$! > /tmp/$(APP)-e2e.pid; \
	 $(PY) scripts/smoke_test.py --base-url $(BASE_URL); rc=$$?; \
	 kill $$(cat /tmp/$(APP)-e2e.pid) 2>/dev/null; exit $$rc

smoke: ## Run the smoke checks against BASE_URL (any running deployment)
	$(PY) scripts/smoke_test.py --base-url $(BASE_URL)

starter: ## Generate the learner starter repo into ../<repo>-starter
	$(PY) scripts/make_starter.py --out ../$(notdir $(CURDIR))-starter --force

## ---- Evaluation (system under test: fde-02 checked out at FDE02_DIR) ---
FDE02_DIR ?= ../fde-02-llm-applications
FA        := $(FDE02_DIR)/.venv/bin/filing-assistant
SUT       := FDE02_DIR=$(FDE02_DIR) $(PY) scripts/sut.py
CONFIG    ?= advanced
LABEL     ?= v$(shell grep -m1 __version__ $(FDE02_DIR)/src/filing_assistant/__init__.py 2>/dev/null | cut -d'"' -f2)
FB_INDEX  ?= $(FDE02_DIR)/index
PROFILE   ?= ci-offline
BASELINE  ?= evals/baselines/financebench-test-advanced-v1.0.0.jsonl

fetch: ## Download the pinned raw sources (FinanceBench, PubMedQA, CUAD); checksums verified
	rag-eval fetch

goldens: fetch ## Build the FinanceBench golden set locally and verify every golden set
	@[ -f goldens/financebench/v1/items.jsonl ] || rag-eval golden build financebench --force
	rag-eval golden verify

corpora: ## Write PubMedQA, CUAD and red-team PDFs and index them with fde-02
	rag-eval corpus pubmedqa && rag-eval corpus cuad && rag-eval corpus redteam
	$(FA) --index-dir data/index/corpus ingest --pdfs data/corpus/pubmedqa data/corpus/cuad --embed lsa
	$(FA) --data-dir $(FDE02_DIR)/data --index-dir data/index/redteam ingest --demo --pdfs data/corpus/redteam --embed lsa

sut-up: ## Start fde-02 on :8001 with CONFIG (config/sut.yaml) and INDEX
	$(SUT) up --config $(CONFIG) --index $(or $(INDEX),$(FB_INDEX))

sut-down: ## Stop the system under test
	$(SUT) down

eval-financebench: ## FinanceBench test half + refusal set against CONFIG (starts and stops fde-02)
	$(SUT) up --config $(CONFIG) --index $(FB_INDEX)
	rag-eval run --golden financebench --split test --label $(LABEL)-$(CONFIG) --run-id $(LABEL)-$(CONFIG)-financebench; \
	 rag-eval run --golden refusal --split all --label $(LABEL)-$(CONFIG) --run-id $(LABEL)-$(CONFIG)-refusal; \
	 rc=$$?; $(SUT) down; exit $$rc

eval-corpora: ## PubMedQA and CUAD test halves (finance scope guard off: advanced-open)
	$(SUT) up --config advanced-open --index data/index/corpus
	for g in pubmedqa cuad; do for s in routed doc; do \
	  rag-eval run --golden $$g --split test --scope $$s --label $(LABEL)-$$g-$$s --run-id $(LABEL)-$$g-$$s || break; \
	done; done; rc=$$?; $(SUT) down; exit $$rc

redteam: ## Red-team suite against fde-02 on the poisoned corpus (CONFIG, RT_INDEX to override)
	$(SUT) up --config $(CONFIG) --index $(or $(RT_INDEX),data/index/redteam)
	rag-eval redteam --out runs/$(LABEL)-redteam; rc=$$?; $(SUT) down; exit $$rc

calibrate: ## Reference-judge calibration on the constructed set (JUDGE=llm needs a key)
	rag-eval calibrate --judge $(or $(JUDGE),reference) --out runs/calibration-$(or $(JUDGE),reference).json

gate: ## Release gate for the current LABEL against BASELINE (exit 1 on failure)
	rag-eval gate --run runs/$(LABEL)-advanced-financebench --baseline $(BASELINE) \
	  --redteam runs/$(LABEL)-redteam/redteam.json --calibration runs/calibration-reference.json \
	  --profile $(PROFILE) --out runs/$(LABEL)-gate.md

eval-offline: ## Everything behind the README results, offline (51 s measured, after fde-02 `make ingest`)
	for c in basic basic-routed advanced; do $(MAKE) eval-financebench CONFIG=$$c || exit 1; done
	$(MAKE) eval-corpora redteam calibrate gate

eval-llm: ## Mistral answers, prompt-only baseline, LLM judge (needs MISTRAL_API_KEY; costs cents)
	$(SUT) up --config advanced-llm --index $(FB_INDEX)
	rag-eval run --golden financebench --split test --judge llm --label $(LABEL)-llm --run-id $(LABEL)-llm-financebench; \
	 rag-eval run --golden refusal --split all --judge llm --label $(LABEL)-llm --run-id $(LABEL)-llm-refusal; \
	 rc=$$?; $(SUT) down; [ $$rc = 0 ] || exit $$rc
	rag-eval run --golden financebench --split test --prompt-only --judge llm --label prompt-only --run-id prompt-only-financebench
	rag-eval run --golden refusal --split all --prompt-only --judge llm --label prompt-only --run-id prompt-only-refusal
	rag-eval calibrate --judge llm --out runs/calibration-llm.json

label-export: ## Export 40 judged LLM answers to labels.csv for a person to label (stays local)
	rag-eval label export --run runs/$(LABEL)-llm-financebench --out labels.csv -n 40

label-import: ## Agreement and kappa of the LLM judge against your labels.csv
	rag-eval label import --csv labels.csv

## ---- Docker Desktop ------------------------------------------------------
up-docker: ## Docker Desktop: build and start with Compose, then smoke test
	@$(LOADENV) docker compose -f $(COMPOSE) up -d --build
	$(MAKE) smoke

down-docker: ## Docker Desktop: stop and remove the Compose stack
	docker compose -f $(COMPOSE) down -v

## ---- Podman Desktop ------------------------------------------------------
up-podman: ## Podman Desktop: build the image and run the pod with `podman kube play`
	podman build -t localhost/$(IMAGE) .
	podman kube play --replace deploy/podman/pod.yaml
	$(MAKE) smoke

down-podman: ## Podman Desktop: stop and remove the pod
	podman kube down deploy/podman/pod.yaml

up-podman-compose: ## Podman Desktop alternative: run the same Compose file with podman compose
	@$(LOADENV) podman compose -f $(COMPOSE) up -d --build
	$(MAKE) smoke

## ---- Rancher Desktop -----------------------------------------------------
up-rancher: ## Rancher Desktop (dockerd/moby engine): build and start with Compose
	@$(LOADENV) $(RANCHER) compose -f $(COMPOSE) up -d --build
	$(MAKE) smoke

down-rancher: ## Rancher Desktop: stop the Compose stack
	$(RANCHER) compose -f $(COMPOSE) down -v

## ---- Local Kubernetes ----------------------------------------------------
k8s-docker: ## Docker Desktop Kubernetes: build, deploy overlay, port-forward, smoke
	docker build -t $(IMAGE) .
	kubectl --context docker-desktop apply -k deploy/kubernetes/overlays/docker-desktop
	kubectl --context docker-desktop -n $(NAMESPACE) rollout status deploy/$(APP) --timeout=120s
	$(MAKE) _portforward CONTEXT=docker-desktop

k8s-rancher: ## Rancher Desktop k3s (moby engine shares the image store): deploy and smoke
	$(RANCHER) build -t $(IMAGE) .
	kubectl --context rancher-desktop apply -k deploy/kubernetes/overlays/rancher-desktop
	kubectl --context rancher-desktop -n $(NAMESPACE) rollout status deploy/$(APP) --timeout=120s
	$(MAKE) _portforward CONTEXT=rancher-desktop

k8s-kind: ## kind (works with Podman Desktop: KIND_EXPERIMENTAL_PROVIDER=podman)
	kind get clusters | grep -qx $(KIND_NAME) || kind create cluster --name $(KIND_NAME)
	podman build -t localhost/$(IMAGE) . 2>/dev/null || docker build -t localhost/$(IMAGE) .
	(podman save localhost/$(IMAGE) 2>/dev/null || docker save localhost/$(IMAGE)) > /tmp/$(APP).tar
	kind load image-archive /tmp/$(APP).tar --name $(KIND_NAME)
	kubectl --context kind-$(KIND_NAME) apply -k deploy/kubernetes/overlays/kind
	kubectl --context kind-$(KIND_NAME) -n $(NAMESPACE) rollout status deploy/$(APP) --timeout=180s
	$(MAKE) _portforward CONTEXT=kind-$(KIND_NAME)

k8s-delete: ## Delete the app from the current kube context
	kubectl delete namespace $(NAMESPACE) --ignore-not-found

_portforward:
	@kubectl --context $(CONTEXT) -n $(NAMESPACE) port-forward svc/$(APP) $(HOST_PORT):80 > /tmp/$(APP)-pf.log 2>&1 & echo $$! > /tmp/$(APP)-pf.pid; \
	 sleep 3; $(MAKE) smoke; rc=$$?; kill $$(cat /tmp/$(APP)-pf.pid) 2>/dev/null; exit $$rc

## ---- OpenShift and Helm --------------------------------------------------
k8s-openshift: ## Render the OpenShift overlay (apply with `oc apply -k deploy/openshift` when logged in)
	kubectl kustomize deploy/openshift

helm-lint: ## Lint and render the Helm chart
	helm lint deploy/helm/$(APP)
	helm template $(APP) deploy/helm/$(APP) > /dev/null

## ---- Clouds (Terraform/OpenTofu) -----------------------------------------
TF ?= terraform
tf-%-init: ## Init a cloud stack: make tf-aws-init | tf-azure-init | tf-gcp-init
	$(TF) -chdir=terraform/$* init

tf-%-plan: ## Plan a cloud stack (safe; no changes): make tf-aws-plan
	$(TF) -chdir=terraform/$* plan -out=tfplan

tf-%-apply: ## Apply a planned stack (costs money; stay inside the lab budget)
	$(TF) -chdir=terraform/$* apply tfplan

tf-%-destroy: ## Destroy a cloud stack at the end of every lab
	$(TF) -chdir=terraform/$* destroy

tf-validate: ## Format-check and validate all three clouds without credentials
	@for c in aws azure gcp; do $(TF) -chdir=terraform/$$c init -backend=false -input=false >/dev/null && \
	  $(TF) -chdir=terraform/$$c validate || exit 1; done; $(TF) fmt -check -recursive terraform

## ---- Docs ----------------------------------------------------------------
diagrams: ## Render Mermaid sources to SVG (needs Node.js)
	@mkdir -p diagrams/rendered
	@for f in diagrams/source/*.mmd; do npx -y @mermaid-js/mermaid-cli -i $$f -o diagrams/rendered/$$(basename $${f%.mmd}).svg; done

clean: ## Remove caches and local artefacts
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov dist build **/__pycache__

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_%-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-20s\033[0m %s\n",$$1,$$2}'

.PHONY: fetch goldens corpora sut-up sut-down eval-financebench eval-corpora redteam calibrate \
        gate eval-offline eval-llm label-export label-import \
        install lint fmt test exercises structure run e2e smoke starter up-docker down-docker \
        up-podman down-podman up-podman-compose up-rancher down-rancher k8s-docker k8s-rancher \
        k8s-kind k8s-delete _portforward k8s-openshift helm-lint tf-validate diagrams clean help
