# ADR-003: Deployment matrix of three desktops and three clouds

- **Status:** Accepted
- **Date:** 2026-10-13

## Context

Forward-deployed engineers ship into whatever the customer runs. Learners use different desktops; employers use different clouds; regulated customers often run OpenShift. Budget is USD 50 per month per cloud.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Docker Desktop and one cloud | Simple | Excludes Podman and Rancher users; single-cloud story |
| Kubernetes only | One target | Too steep for early phases; costly in the cloud |
| **Compose + pod spec + Kubernetes overlays + Helm + Terraform per cloud** | Same image everywhere; each learner's setup works; enterprise story intact | More files to maintain; CI must render all of them |

## Decision

One image, built from one Dockerfile, runs through:

- **Docker Desktop:** Compose, then its built-in Kubernetes with the `docker-desktop` overlay.
- **Podman Desktop:** `podman kube play` with `deploy/podman/pod.yaml` (or `podman compose`), then kind with the `kind` overlay.
- **Rancher Desktop:** Compose on the dockerd (moby) engine, then its k3s with the `rancher-desktop` overlay.
- **OpenShift:** the base plus a Route; no fixed UID so the restricted SCC applies.
- **Clouds:** the cheapest managed container service per cloud (ECS Fargate, Container Apps, Cloud Run) with budgets; managed Kubernetes only from fde-05, in short scripted windows.

## Consequences

- CI renders and validates every target, so none rots unnoticed.
- Only one desktop engine should run at a time (port and socket clashes); the labs say so.
- Cloud stacks trade some hardening for cost (public lab endpoints, no customer-managed keys); see the threat model.
