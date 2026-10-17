# Cloud lab stacks

| Cloud | Compute | Registry | Secrets | Logs | Budget |
| --- | --- | --- | --- | --- | --- |
| [AWS](aws/README.md) | ECS Fargate (public IP, no load balancer) | ECR | Secrets Manager | CloudWatch | AWS Budgets, email at 50/80/100% |
| [Azure](azure/README.md) | Container Apps, scale to zero | ACR Basic | Key Vault (RBAC) + managed identity | Log Analytics | Consumption budget, email at 50/80/100% |
| [GCP](gcp/README.md) | Cloud Run, scale to zero | Artifact Registry | Secret Manager | Cloud Logging | Billing budget at 50/80/100% |

Rules for every lab:

1. Use a sandbox account, subscription or project; never production.
2. Budget is USD 50 per month per cloud. Each stack creates its own budget alert.
3. `plan` is safe and runs in CI (`iac` workflow, no credentials). `apply` is a manual lab step.
4. Run `make tf-<cloud>-destroy` at the end of every lab.
5. Never commit state, plans or `.tfvars` with secrets (all ignored by `.gitignore`).

State is local by default. For a team, add a remote backend (S3, Azure Storage, GCS) in a
`backend.tf` that is not committed with real names.
