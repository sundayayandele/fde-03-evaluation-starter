#!/usr/bin/env python3
"""Fail if a required part of the FDE repo structure is missing.

Runs in CI for the template, every reference repo and every starter repo, so the
deployment matrix (three desktops, three clouds) can never silently drop out.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = [
    "README.md", "AGENTS.md", "CLAUDE.md", "LICENSE", "CHANGELOG.md", "Makefile",
    "pyproject.toml", ".env.example", "Dockerfile", "config/providers.yaml",
    "app/main.py", "tests/e2e/smoke.yaml",
    "scripts/smoke_test.py", "scripts/make_starter.py",
    "evals/README.md", "labs/README.md",
    "docs/architecture/ARCHITECTURE.md", "docs/architecture/C4.md",
    "docs/adr", "docs/customer/CUSTOMER-BRIEF.md", "docs/customer/DECISION-MEMO.md",
    "docs/security/SECURITY.md", "docs/security/THREAT-MODEL.md",
    "docs/mlops/MODEL-CARD.md", "docs/mlops/EVALUATION.md", "docs/datasets/DATASETS.md",
    "docs/infrastructure/INFRASTRUCTURE.md", "docs/infrastructure/CAPACITY-PLANNING.md",
    "docs/learning/LEARNING-GUIDE.md", "docs/learning/DESKTOP-LABS.md",
    "docs/learning/CLOUD-LABS.md", "docs/COST-TCO.md", "docs/DEPLOYMENT.md",
    "diagrams/source",
    "deploy/compose/compose.yaml", "deploy/podman/pod.yaml",
    "deploy/kubernetes/base/kustomization.yaml",
    "deploy/kubernetes/overlays/docker-desktop/kustomization.yaml",
    "deploy/kubernetes/overlays/rancher-desktop/kustomization.yaml",
    "deploy/kubernetes/overlays/kind/kustomization.yaml",
    "deploy/kubernetes/overlays/cloud/kustomization.yaml",
    "deploy/openshift/kustomization.yaml", "deploy/helm",
    "terraform/aws/main.tf", "terraform/azure/main.tf", "terraform/gcp/main.tf",
    "monitoring/prometheus.yml", "monitoring/alerts.yml",
    ".github/workflows/ci.yml", ".github/workflows/e2e.yml", ".github/workflows/security.yml",
    ".github/workflows/iac.yml", ".github/workflows/manifests.yml",
    ".github/workflows/diagrams.yml",
    # Phase 3: evaluation
    "config/rubric.yaml", "config/redteam.yaml", "config/gate.yaml", "config/sut.yaml",
    "goldens/financebench/v1/manifest.json", "goldens/pubmedqa/v1/items.jsonl",
    "goldens/cuad/v1/items.jsonl", "goldens/refusal/v1/items.jsonl", "evals/baselines",
    "scripts/sut.py", "docs/RELEASE-READINESS.md", "docs/JUDGE-CALIBRATION.md",
    "deploy/kubernetes/jobs/kustomization.yaml", "monitoring/grafana/dashboards/evaluation.json",
    ".github/workflows/gate.yml", ".github/workflows/evals.yml",
]
REFERENCE_ONLY = [".github/workflows/publish-starter.yml"]


def main() -> int:
    starter = (ROOT / ".starter").exists()
    required = REQUIRED + ([] if starter else REFERENCE_ONLY)
    missing = [p for p in required if not (ROOT / p).exists()]
    if missing:
        print("check_structure: missing required paths:", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"check_structure: OK ({len(required)} paths, {'starter' if starter else 'reference'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
