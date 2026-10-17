# Azure lab stack

Container Registry (Basic), Container Apps (0.25 vCPU, 0.5 GiB, scale to zero), Log Analytics,
Key Vault with RBAC and a user-assigned managed identity, and a monthly budget with alerts at
50, 80 and 100 percent of USD 50.

```bash
az login && az account set -s <sandbox-subscription-id>
make tf-azure-init

# 1) Registry, identity, Key Vault and budget (no app yet)
terraform -chdir=terraform/azure apply -var subscription_id=<id> -var alert_email=you@example.com \
  -var mistral_api_key="$MISTRAL_API_KEY"

# 2) Push the image
ACR=$(terraform -chdir=terraform/azure output -raw registry_name)
az acr login -n $ACR
docker tag fde-03-evaluation:local $ACR.azurecr.io/fde-03-evaluation:1.0.0 && docker push $ACR.azurecr.io/fde-03-evaluation:1.0.0

# 3) Create the Container App, smoke test, destroy
terraform -chdir=terraform/azure apply -var subscription_id=<id> -var alert_email=you@example.com \
  -var mistral_api_key="$MISTRAL_API_KEY" -var deploy_app=true
python scripts/smoke_test.py --base-url $(terraform -chdir=terraform/azure output -raw app_url)
make tf-azure-destroy
```

Set `budget_start_date` to the first day of the current month. On Apple silicon build with
`--platform linux/amd64`. Never put the API key in a committed `.tfvars` file.
