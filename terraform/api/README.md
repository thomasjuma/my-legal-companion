# Terraform API Stack (App Runner + ECR)

This directory deploys the Legal Companion API container to AWS App Runner.

## What this stack creates

- ECR repository for the API image (`counsel-api`)
- App Runner service (`counsel-api`)
- App Runner IAM roles (ECR access + runtime role)
- Runtime IAM policies for:
  - Aurora credentials access (Secrets Manager)
  - SQS send/get access
  - Bedrock / SageMaker invoke access
- App Runner VPC connector in the default VPC

## Files

- `main.tf` - core infrastructure resources
- `variables.tf` - configurable inputs
- `outputs.tf` - service/repository outputs
- `terraform.tfvars.example` - starter variables file

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured (`aws sts get-caller-identity` works)
- Docker running (for image build/push)
- `backend/api/Dockerfile` present

## Quick start

1. From this directory, copy the vars template:

```bash
cp terraform.tfvars.example terraform.tfvars
```

2. Fill required values in `terraform.tfvars`:

- `openai_api_key`
- `aurora_cluster_arn`
- `aurora_cluster_endpoint`
- `aurora_secret_arn`
- `clerk_jwks_url`
- `clerk_issuer`

3. Initialize and apply:

```bash
terraform init
terraform plan
terraform apply
```

If this is your first deploy in a fresh account, push the API image to ECR first (or use `scripts/deploy.py` / `scripts/deploy.sh`, which handles build/push).

## Build and push API image

App Runner points to ECR image `${ecr_repository_url}:latest` by default.

From repo root:

```bash
docker build -f backend/api/Dockerfile -t counsel-api:latest .
ECR_URL=$(cd terraform/api && terraform output -raw ecr_repository_url)
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin "${ECR_URL%%/*}"
docker tag counsel-api:latest "${ECR_URL}:latest"
docker push "${ECR_URL}:latest"
```

If `auto_deployments_enabled = true`, App Runner redeploys automatically after push.

## Useful outputs

```bash
terraform output -raw ecr_repository_url
terraform output -raw apprunner_service_url
terraform output -raw apprunner_service_arn
```

## Common issues

- **`Error: reading Secrets Manager Secret Version ... couldn't find resource`**
  - Check `aurora_secret_arn` is correct and exists in the selected region.
- **`RepositoryAlreadyExists` / `EntityAlreadyExists` / `InvalidGroup.Duplicate` on apply**
  - Existing AWS resources are not yet imported into Terraform state.
  - Run:

```bash
cd terraform/api
./import_existing_resources.sh
terraform plan
terraform apply
```

- **`Failed to pull your application image. Reason: ECR image doesn't exist.`**
  - The configured tag (default: `latest`) was not available in ECR at deploy time.
  - Push an image first, then apply:

```bash
docker build -f backend/api/Dockerfile -t counsel-api:latest .
cd terraform/api
ECR_URL=$(terraform output -raw ecr_repository_url)
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin "${ECR_URL%%/*}"
docker tag counsel-api:latest "${ECR_URL}:latest"
docker push "${ECR_URL}:latest"
terraform apply -replace=aws_apprunner_service.api
```

- **App starts but DB calls fail**
  - Verify `aurora_cluster_endpoint`, secret contents, network/security groups, and VPC routing.
- **`403` from protected routes**
  - Verify `clerk_jwks_url` and `clerk_issuer`.

## Apply order (full app)

Use this order for complete infrastructure:

1. `terraform/database`
2. `terraform/agents` (optional)
3. `terraform/api`
4. `terraform/frontend`

