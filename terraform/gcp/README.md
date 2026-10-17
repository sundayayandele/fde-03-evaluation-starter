# GCP lab stack

Artifact Registry, Cloud Run (1 vCPU, 512 MiB, scale to zero, CPU only during requests),
Secret Manager, a dedicated runtime service account and an optional billing budget with
alerts at 50, 80 and 100 percent of USD 50.

```bash
gcloud auth application-default login && gcloud config set project <sandbox-project>
make tf-gcp-init

# 1) APIs, registry, secret, service account, budget
terraform -chdir=terraform/gcp apply -var project_id=<project> -var billing_account=<id> \
  -var mistral_api_key="$MISTRAL_API_KEY"

# 2) Push the image
REPO=$(terraform -chdir=terraform/gcp output -raw image_repository)
gcloud auth configure-docker ${REPO%%/*}
docker tag fde-03-evaluation:local $REPO/fde-03-evaluation:1.0.0 && docker push $REPO/fde-03-evaluation:1.0.0

# 3) Deploy Cloud Run, smoke test, destroy
terraform -chdir=terraform/gcp apply -var project_id=<project> -var billing_account=<id> \
  -var mistral_api_key="$MISTRAL_API_KEY" -var deploy_app=true
python scripts/smoke_test.py --base-url $(terraform -chdir=terraform/gcp output -raw app_url)
make tf-gcp-destroy
```

Budget alerts go to the billing account's admins by default. On Apple silicon build with
`--platform linux/amd64`.
