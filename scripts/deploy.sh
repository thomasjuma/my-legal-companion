#!/usr/bin/env bash
#
# Bash equivalent of scripts/deploy.py:
# 1) Ensure ECR exists (terraform apply -target) and build/push the API Docker image
# 2) Apply Terraform (api then frontend)
# 3) Set apiBaseUrl in environment.production.ts and ng build
# 4) Sync the Angular browser bundle to S3 and invalidate CloudFront
#
# Set openai_api_key in terraform/api/terraform.tfvars for chat, etc.

set -euo pipefail

# Angular 20+ application output (see frontend/angular.json project name)
readonly ANGULAR_PROJECT="my-legal-companion-ui"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT

if [[ -n "${DEFAULT_AWS_REGION:-}" && -z "${TF_VAR_aws_region:-}" ]]; then
  export TF_VAR_aws_region="$DEFAULT_AWS_REGION"
fi

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

run() {
  # shellcheck disable=SC2145
  echo "Running: $*"
  "$@"
}

# ---------------------------------------------------------------------------
# prerequisite checks (see deploy.py)
# ---------------------------------------------------------------------------

check_prerequisites() {
  echo "🔍 Checking prerequisites..."

  for tool in docker terraform npm aws python3; do
    if ! command -v "$tool" &>/dev/null; then
      case "$tool" in
        docker) echo "  ❌ Docker is required to build the API image" ;;
        terraform) echo "  ❌ Terraform is required for infrastructure deployment" ;;
        npm) echo "  ❌ npm is required for building the frontend" ;;
        aws) echo "  ❌ AWS CLI is required for S3 sync and CloudFront invalidation" ;;
        python3) echo "  ❌ python3 is required to patch environment.production.ts" ;;
      esac
      exit 1
    fi
    if ! "$tool" --version &>/dev/null; then
      echo "  ❌ $tool is not working (try: $tool --version)"
      exit 1
    fi
    echo "  ✅ $tool is installed"
  done

  if ! run docker info &>/dev/null; then
    echo "  ❌ Docker is not running. Please start Docker."
    exit 1
  fi
  echo "  ✅ Docker is running"

  if ! run aws sts get-caller-identity &>/dev/null; then
    echo "  ❌ AWS credentials not configured. Run 'aws configure'"
    exit 1
  fi
  echo "  ✅ AWS credentials configured"
}

# ---------------------------------------------------------------------------
# ECR: ensure repo, build, push
# ---------------------------------------------------------------------------

ecr_registry_host() {
  local ecr_url="$1"
  echo "${ecr_url%%/*}" | tr -d '[:space:]'
}

terraform_state_has() {
  local tf_dir="$1"
  local address="$2"

  run_in_dir "$tf_dir" terraform state show "$address" &>/dev/null
}

terraform_import_if_missing() {
  local tf_dir="$1"
  local address="$2"
  local import_id="$3"
  local label="$4"

  if [[ -z "$import_id" || "$import_id" == "None" ]]; then
    return
  fi

  if terraform_state_has "$tf_dir" "$address"; then
    return
  fi

  echo "  $label already exists; importing into Terraform state…"
  run_in_dir "$tf_dir" terraform import "$address" "$import_id"
}

ensure_api_existing_resource_state() {
  local api_tf_dir="$1"
  local repository_name="counsel-api"
  local sg_name="counsel-apprunner-connector"
  local ecr_access_role="counsel-apprunner-ecr-access"
  local instance_role="counsel-apprunner-instance"

  if aws ecr describe-repositories --repository-names "$repository_name" &>/dev/null; then
    terraform_import_if_missing "$api_tf_dir" aws_ecr_repository.api "$repository_name" "ECR repository $repository_name"
  fi

  local vpc_id
  vpc_id=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text 2>/dev/null || true)
  if [[ -n "$vpc_id" && "$vpc_id" != "None" ]]; then
    local sg_id
    sg_id=$(
      aws ec2 describe-security-groups \
        --filters "Name=vpc-id,Values=$vpc_id" "Name=group-name,Values=$sg_name" \
        --query 'SecurityGroups[0].GroupId' \
        --output text 2>/dev/null || true
    )
    terraform_import_if_missing "$api_tf_dir" aws_security_group.apprunner_vpc_connector "$sg_id" "Security group $sg_name"
  fi

  if aws iam get-role --role-name "$ecr_access_role" &>/dev/null; then
    terraform_import_if_missing "$api_tf_dir" aws_iam_role.apprunner_ecr_access "$ecr_access_role" "IAM role $ecr_access_role"

    local ecr_access_policy_arn="arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
    local attached_ecr_policy
    attached_ecr_policy=$(
      aws iam list-attached-role-policies \
        --role-name "$ecr_access_role" \
        --query "AttachedPolicies[?PolicyArn=='$ecr_access_policy_arn'].PolicyArn | [0]" \
        --output text 2>/dev/null || true
    )
    if [[ "$attached_ecr_policy" == "$ecr_access_policy_arn" ]]; then
      terraform_import_if_missing \
        "$api_tf_dir" \
        aws_iam_role_policy_attachment.apprunner_ecr \
        "$ecr_access_role/$ecr_access_policy_arn" \
        "IAM policy attachment for $ecr_access_role"
    fi
  fi

  if aws iam get-role --role-name "$instance_role" &>/dev/null; then
    terraform_import_if_missing "$api_tf_dir" aws_iam_role.apprunner_instance "$instance_role" "IAM role $instance_role"

    if aws iam get-role-policy --role-name "$instance_role" --policy-name counsel-apprunner-aurora &>/dev/null; then
      terraform_import_if_missing "$api_tf_dir" aws_iam_role_policy.apprunner_aurora "$instance_role:counsel-apprunner-aurora" "IAM inline policy counsel-apprunner-aurora"
    fi
    if aws iam get-role-policy --role-name "$instance_role" --policy-name counsel-apprunner-sqs &>/dev/null; then
      terraform_import_if_missing "$api_tf_dir" aws_iam_role_policy.apprunner_sqs "$instance_role:counsel-apprunner-sqs" "IAM inline policy counsel-apprunner-sqs"
    fi
    if aws iam get-role-policy --role-name "$instance_role" --policy-name counsel-apprunner-invoke &>/dev/null; then
      terraform_import_if_missing "$api_tf_dir" aws_iam_role_policy.apprunner_invoke "$instance_role:counsel-apprunner-invoke" "IAM inline policy counsel-apprunner-invoke"
    fi
  fi

  local vpc_connector_arn
  vpc_connector_arn=$(
    aws apprunner list-vpc-connectors \
      --query "VpcConnectors[?VpcConnectorName=='counsel-api-vpc'].VpcConnectorArn | [0]" \
      --output text 2>/dev/null || true
  )
  terraform_import_if_missing "$api_tf_dir" aws_apprunner_vpc_connector.api "$vpc_connector_arn" "App Runner VPC connector counsel-api-vpc"

  local service_arn
  service_arn=$(
    aws apprunner list-services \
      --query "ServiceSummaryList[?ServiceName=='counsel-api'].ServiceArn | [0]" \
      --output text 2>/dev/null || true
  )
  terraform_import_if_missing "$api_tf_dir" aws_apprunner_service.api "$service_arn" "App Runner service counsel-api"
}

ensure_agents_existing_resource_state() {
  local agents_tf_dir="$1"
  local queue_name="counsel-agents"
  local queue_url

  queue_url=$(aws sqs get-queue-url --queue-name "$queue_name" --query QueueUrl --output text 2>/dev/null || true)
  terraform_import_if_missing "$agents_tf_dir" aws_sqs_queue.agents "$queue_url" "SQS queue $queue_name"
}

build_and_push_api_image() {
  echo ""
  echo "🐳 Building and pushing API image to ECR..."

  if [[ ! -f "$ROOT/backend/api/Dockerfile" ]]; then
    echo "  ❌ backend/api/Dockerfile not found"
    exit 1
  fi

  local api_tf_dir="$ROOT/terraform/api"
  if [[ ! -d "$api_tf_dir/.terraform" ]]; then
    run_in_dir "$api_tf_dir" terraform init
  fi

  echo "  Ensuring ECR repository exists…"
  ensure_api_existing_resource_state "$api_tf_dir"
  run_in_dir "$api_tf_dir" terraform apply -auto-approve -target=aws_ecr_repository.api

  local ecr_url
  ecr_url=$(cd "$api_tf_dir" && terraform output -raw ecr_repository_url)
  local reg
  reg=$(ecr_registry_host "$ecr_url")

  local local_tag="counsel-api:latest"
  local remote="${ecr_url}:latest"

  run_in_dir "$ROOT" docker build -f backend/api/Dockerfile -t "$local_tag" .
  run_in_dir "$ROOT" docker tag "$local_tag" "$remote"

  local region
  region=$(aws configure get region 2>/dev/null | tr -d '[:space:]') || true
  region=${region:-"${AWS_DEFAULT_REGION:-us-east-1}"}

  echo "  Logging in to ECR and pushing…"
  aws ecr get-login-password --region "$region" | run docker login --username AWS --password-stdin "$reg"
  run_in_dir "$ROOT" docker push "$remote"
  echo "  ✅ Pushed $remote"
}

# ---------------------------------------------------------------------------
# environment.production.ts + ng build
# ---------------------------------------------------------------------------

angular_browser_dir() {
  echo "$ROOT/frontend/dist/$ANGULAR_PROJECT/browser"
}

patch_angular_production_api_url() {
  local env_path="$ROOT/frontend/src/environments/environment.production.ts"
  local api_url=$1
  if [[ ! -f "$env_path" ]]; then
    echo "  ❌ Missing $env_path"
    exit 1
  fi
  python3 - "$env_path" "$api_url" <<'PY'
import re
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])
api_url = sys.argv[2]
text = p.read_text(encoding="utf-8")
value = json.dumps(api_url)
new_text, n = re.subn(
    r"apiBaseUrl:\s*('[^']*'|\"[^\"]*\")",
    f"apiBaseUrl: {value}",
    text,
    count=1,
)
if n != 1:
    print("  ❌ Could not find apiBaseUrl: '...' in environment.production.ts to patch", file=sys.stderr)
    sys.exit(1)
p.write_text(new_text, encoding="utf-8")
print(f"  ✅ Set apiBaseUrl in environment.production.ts: {api_url!r}")
PY
}

build_frontend() {
  local api_url=${1-}
  echo ""
  echo "🎨 Building frontend..."

  local fe="$ROOT/frontend"
  if [[ ! -d "$fe" ]]; then
    echo "  ❌ Frontend directory not found: $fe"
    exit 1
  fi

  if [[ ! -d "$fe/node_modules" ]]; then
    echo "  Installing dependencies..."
    run_in_dir "$fe" npm install
  fi

  patch_angular_production_api_url "$api_url"

  echo "  Building Angular app for production (ng build)..."
  (
    export NODE_ENV=production
    cd "$fe" && run npm run build -- --configuration production
  )

  local out
  out="$(angular_browser_dir)"
  if [[ ! -d "$out" ]]; then
    echo "  ❌ Build output not found: $out"
    echo "  Expected the browser bundle at dist/${ANGULAR_PROJECT}/browser/"
    exit 1
  fi
  echo "  ✅ Frontend built successfully"
}

# ---------------------------------------------------------------------------
# Terraform (api then frontend)
# ---------------------------------------------------------------------------

run_in_dir() {
  local d=$1
  shift
  (cd "$d" && "$@")
}

deploy_prerequisite_terraform() {
  echo ""
  echo "🏗️  Deploying prerequisite infrastructure with Terraform..."

  local agents_dir="$ROOT/terraform/agents"

  if [[ ! -d "$agents_dir" ]]; then
    echo "  ❌ Terraform directory not found: $agents_dir"
    exit 1
  fi

  if [[ ! -d "$agents_dir/.terraform" ]]; then
    echo "  Initializing Terraform in agents…"
    run_in_dir "$agents_dir" terraform init
  fi

  echo ""
  echo "  Planning agents…"
  ensure_agents_existing_resource_state "$agents_dir"
  run_in_dir "$agents_dir" terraform plan
  echo ""
  echo "  Applying agents (SQS)…"
  run_in_dir "$agents_dir" terraform apply -auto-approve
}

deploy_terraform() {
  echo ""
  echo "🏗️  Deploying infrastructure with Terraform..."

  local api_dir="$ROOT/terraform/api"
  local fe_dir="$ROOT/terraform/frontend"

  for d in "$api_dir" "$fe_dir"; do
    if [[ ! -d "$d" ]]; then
      echo "  ❌ Terraform directory not found: $d"
      exit 1
    fi
  done

  for d in "$api_dir" "$fe_dir"; do
    if [[ ! -d "$d/.terraform" ]]; then
      echo "  Initializing Terraform in $(basename "$d")…"
      run_in_dir "$d" terraform init
    fi
  done

  echo "  Planning api…"
  ensure_api_existing_resource_state "$api_dir"
  run_in_dir "$api_dir" terraform plan
  echo ""
  echo "  Applying api (App Runner, ECR, IAM)…"
  run_in_dir "$api_dir" terraform apply -auto-approve

  echo ""
  echo "  Planning frontend…"
  run_in_dir "$fe_dir" terraform plan
  echo ""
  echo "  Applying frontend (S3, CloudFront)…"
  run_in_dir "$fe_dir" terraform apply -auto-approve
}

# ---------------------------------------------------------------------------
# S3 + CloudFront
# ---------------------------------------------------------------------------

upload_frontend() {
  local bucket_name=$1
  local cloudfront_id=$2
  local frontend_dir
  frontend_dir="$(angular_browser_dir)"

  echo ""
  echo "📤 Uploading frontend to S3 bucket: $bucket_name"

  if [[ ! -d "$frontend_dir" ]]; then
    echo "  ❌ Frontend build not found: $frontend_dir"
    exit 1
  fi

  local fd_slash=${frontend_dir%/}/

  echo "  Clearing S3 bucket..."
  run aws s3 rm "s3://$bucket_name/" --recursive

  echo "  Uploading HTML files..."
  run aws s3 cp "$fd_slash" "s3://$bucket_name/" --recursive --exclude '*' --include '*.html' \
    --content-type text/html --cache-control 'max-age=0,no-cache,no-store,must-revalidate'

  echo "  Uploading CSS files..."
  run aws s3 cp "$fd_slash" "s3://$bucket_name/" --recursive --exclude '*' --include '*.css' \
    --content-type text/css --cache-control 'max-age=31536000,public'

  echo "  Uploading JavaScript files..."
  run aws s3 cp "$fd_slash" "s3://$bucket_name/" --recursive --exclude '*' --include '*.js' \
    --content-type application/javascript --cache-control 'max-age=31536000,public'

  echo "  Uploading JSON files..."
  run aws s3 cp "$fd_slash" "s3://$bucket_name/" --recursive --exclude '*' --include '*.json' \
    --content-type application/json --cache-control 'max-age=31536000,public'

  local _ext _ct
  for pair in \
    "*.png:image/png" \
    "*.jpg:image/jpeg" \
    "*.jpeg:image/jpeg" \
    "*.gif:image/gif" \
    "*.svg:image/svg+xml" \
    "*.ico:image/x-icon"; do
    _ext=${pair%%:*}
    _ct=${pair#*:}
    run aws s3 cp "$fd_slash" "s3://$bucket_name/" --recursive --exclude '*' --include "$_ext" \
      --content-type "$_ct" --cache-control 'max-age=31536000,public'
  done

  echo "  Uploading remaining files..."
  run aws s3 sync "$fd_slash" "s3://$bucket_name/" --cache-control 'max-age=31536000,public'
  echo "  ✅ Frontend uploaded successfully"

  echo ""
  echo "🔄 Invalidating CloudFront cache..."
  run aws cloudfront create-invalidation --distribution-id "$cloudfront_id" --paths "/*"
  echo "  ✅ CloudFront invalidation created"
}

upload_frontend_sync_only() {
  local bucket_name=$1
  local out
  out="$(angular_browser_dir)"
  local out_slash=${out%/}/
  echo ""
  echo "📤 Uploading frontend to S3 (no distribution id in outputs)…"
  run aws s3 sync "$out_slash" "s3://$bucket_name/" --delete
}

display_deployment_info() {
  local cloudfront_url=$1
  local appr_url=$2
  echo ""
  echo "📝 Deployment Information"
  echo ""
  echo "  ✅ Deployment successful!"
  echo ""
  echo "  CloudFront (site + /api/*): $cloudfront_url"
  if [[ -n "$appr_url" ]]; then
    echo "  App Runner (direct): $appr_url"
  fi
  echo ""
  echo "  Note: \`src/environments/environment.ts\` for local dev is unchanged."
  echo "  Production build uses apiBaseUrl '' for same-origin /api on CloudFront."
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

main() {
  echo "🚀 Legal Companion Deployment"
  echo "=================================================="

  check_prerequisites

  deploy_prerequisite_terraform
  build_and_push_api_image
  deploy_terraform

  local fe_dir="$ROOT/terraform/frontend"
  local bucket_name
  bucket_name=$(cd "$fe_dir" && terraform output -raw s3_bucket_name)
  local dist_id
  dist_id=$(cd "$fe_dir" && terraform output -raw cloudfront_distribution_id 2>/dev/null || true)

  # Same-origin API on CloudFront: leave apiBaseUrl empty
  build_frontend ""

  if [[ -n "$dist_id" ]]; then
    upload_frontend "$bucket_name" "$dist_id"
  else
    upload_frontend_sync_only "$bucket_name"
  fi

  local cf_url
  cf_url=$(cd "$fe_dir" && terraform output -raw cloudfront_url)
  local appr
  appr=$(cd "$fe_dir" && terraform output -raw apprunner_service_url 2>/dev/null || echo "")

  display_deployment_info "$cf_url" "$appr"

  echo ""
  echo "=================================================="
  echo "✅ Deployment complete!"
  echo ""
  echo "🌐 Your application is available at:"
  echo "   $cf_url"
  local apu
  if [[ -z "$appr" ]]; then
    apu="counsel-api"
  else
    apu="$appr"
  fi
  echo ""
  echo "📊 Monitor the API: AWS Console → App Runner (URL: $apu)"
  echo ""
  echo "⏳ Note: CloudFront distribution may take 5-10 minutes to fully propagate"
}

main "$@"
