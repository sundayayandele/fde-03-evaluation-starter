# Cloud labs: AWS, Azure, GCP

Each repo ships a Terraform lab stack per cloud using that cloud's cheapest managed container service, a secret store and a budget alert. Step-by-step commands are in each stack's README:

- [AWS: ECS Fargate](../../terraform/aws/README.md)
- [Azure: Container Apps](../../terraform/azure/README.md)
- [GCP: Cloud Run](../../terraform/gcp/README.md)

## Rules

1. **Sandbox only.** Use a dedicated sandbox account, subscription or project.
2. **Budget:** USD 50 per month per cloud, alerts at 50, 80 and 100 percent (created by the stack).
3. **Plan first.** `make tf-<cloud>-plan` is free and safe. Read the plan before `apply`.
4. **Destroy every time.** `make tf-<cloud>-destroy` at the end of the lab, then check the console for leftovers.
5. **Never commit** state files, plans or `.tfvars` with secrets.

## Typical lab flow

```bash
docker build -t fde-03-evaluation:local .                 # add --platform linux/amd64 on Apple silicon
make tf-<cloud>-init
# first apply: registry, secret store, identity, budget (see the stack README)
# push the image to the registry the stack created
# second apply (Azure/GCP: deploy_app=true; AWS: update the service)
python scripts/smoke_test.py --base-url <url printed by terraform output>
# set target_url to the fde-02 URL from its own stack (`-var target_url=...`) to run evaluations there
make tf-<cloud>-destroy
```

## Evidence for your portfolio

The `terraform plan` summary, the smoke-test output against the cloud URL, a screenshot of the budget, and the `destroy` output. Record the date and region.
