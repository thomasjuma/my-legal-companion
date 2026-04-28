#!/usr/bin/env bash
#
# Deploy application artifacts only (no Terraform apply):
# 1) Build + push backend API image to existing ECR repository
# 2) Build frontend
# 3) Upload frontend bundle to existing S3 bucket + invalidate CloudFront
#
# Assumes infrastructure already exists in:
#   - terraform/api
#   - terraform/frontend

set -euo pipefail

readonly ANGULAR_PROJECT="my-legal-companion-ui"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT

run() {
  # shellcheck disable=SC2145
  echo "Running: $*"
  "$@"
}

run_in_dir() {
  local d=$1
  shift
  (cd "$d" && "$@")
}

check_prerequisites() {
  echo "🔍 Checking prerequisites..."
  for tool in docker npm aws terraform python3; do
    if ! command -v "$tool" &>/dev/null; then
      echo "  ❌ Missing required tool: $tool"
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

ensure_tf_ready() {
  local tf_dir="$1"
  if [[ ! -d "$tf_dir" ]]; then
    echo "  ❌ Terraform directory not found: $tf_dir"
    exit 1
  fi
  if [[ ! -d "$tf_dir/.terraform" ]]; then
    echo "  Initializing Terraform in $(basename "$tf_dir")..."
    run_in_dir "$tf_dir" terraform init
  fi
}

get_tf_output_raw() {
  local tf_dir="$1"
  local key="$2"
  local value
  value="$(cd "$tf_dir" && terraform output -raw "$key" 2>/dev/null || true)"
  # trim leading/trailing whitespace
  value="$(echo -n "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  echo "$value"
}

aws_account_id() {
  aws sts get-caller-identity --query Account --output text
}

resolve_ecr_repository_url() {
  local api_tf_dir="$1"
  local value
  value="$(get_tf_output_raw "$api_tf_dir" "ecr_repository_url")"
  if [[ -n "$value" ]]; then
    echo "$value"
    return 0
  fi
  aws ecr describe-repositories \
    --repository-names counsel-api \
    --query 'repositories[0].repositoryUri' \
    --output text 2>/dev/null || true
}

resolve_frontend_bucket_name() {
  local fe_tf_dir="$1"
  local value
  value="$(get_tf_output_raw "$fe_tf_dir" "s3_bucket_name")"
  if [[ -n "$value" ]]; then
    echo "$value"
    return 0
  fi
  local account
  account="$(aws_account_id)"
  echo "counsel-frontend-${account}"
}

resolve_cloudfront_distribution_id() {
  local fe_tf_dir="$1"
  local value
  value="$(get_tf_output_raw "$fe_tf_dir" "cloudfront_distribution_id")"
  if [[ -n "$value" ]]; then
    echo "$value"
    return 0
  fi
  aws cloudfront list-distributions \
    --query "DistributionList.Items[?Comment=='Legal Companion Frontend'].Id | [0]" \
    --output text 2>/dev/null || true
}

resolve_cloudfront_url() {
  local fe_tf_dir="$1"
  local value
  value="$(get_tf_output_raw "$fe_tf_dir" "cloudfront_url")"
  if [[ -n "$value" ]]; then
    echo "$value"
    return 0
  fi
  local domain
  domain="$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Comment=='Legal Companion Frontend'].DomainName | [0]" \
    --output text 2>/dev/null || true)"
  if [[ -n "$domain" && "$domain" != "None" ]]; then
    echo "https://${domain}"
  fi
}

resolve_apprunner_url() {
  local fe_tf_dir="$1"
  local value
  value="$(get_tf_output_raw "$fe_tf_dir" "apprunner_service_url")"
  if [[ -n "$value" && "$value" != "apply ../api first" ]]; then
    echo "$value"
    return 0
  fi
  local service_url
  service_url="$(aws apprunner list-services \
    --query "ServiceSummaryList[?ServiceName=='counsel-api'].ServiceUrl | [0]" \
    --output text 2>/dev/null || true)"
  if [[ -n "$service_url" && "$service_url" != "None" ]]; then
    echo "https://${service_url}"
  fi
}

require_tf_output_raw() {
  local tf_dir="$1"
  local key="$2"
  local hint="$3"
  local value
  value="$(get_tf_output_raw "$tf_dir" "$key")"
  if [[ -z "$value" ]]; then
    echo "  ❌ Missing Terraform output '$key' in $tf_dir"
    echo "     $hint"
    exit 1
  fi
  echo "$value"
}

validate_ecr_url() {
  local ecr_url="$1"
  if [[ ! "$ecr_url" =~ ^[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9._/-]+$ ]]; then
    echo "  ❌ Invalid ECR repository URL from Terraform output: '$ecr_url'"
    echo "     Run 'terraform -chdir=terraform/api apply' and ensure output ecr_repository_url exists."
    exit 1
  fi
}

ecr_registry_host() {
  local ecr_url="$1"
  echo "${ecr_url%%/*}" | tr -d '[:space:]'
}

build_and_push_backend() {
  echo ""
  echo "🐳 Deploying backend application image..."

  local api_tf_dir="$ROOT/terraform/api"
  ensure_tf_ready "$api_tf_dir"

  local ecr_url
  ecr_url="$(resolve_ecr_repository_url "$api_tf_dir")"
  if [[ -z "$ecr_url" ]]; then
    echo "  ❌ Could not resolve ECR repository URL."
    echo "     Ensure ECR repository 'counsel-api' exists or apply terraform/api first."
    exit 1
  fi
  validate_ecr_url "$ecr_url"
  local remote="${ecr_url}:latest"
  local reg
  reg="$(ecr_registry_host "$ecr_url")"

  run_in_dir "$ROOT" docker build -f backend/api/Dockerfile -t counsel-api:latest .
  run_in_dir "$ROOT" docker tag counsel-api:latest "$remote"

  local region
  region="$(aws configure get region 2>/dev/null | tr -d '[:space:]')" || true
  region="${region:-${AWS_DEFAULT_REGION:-us-east-1}}"

  echo "  Logging in to ECR and pushing image..."
  aws ecr get-login-password --region "$region" | run docker login --username AWS --password-stdin "$reg"
  run_in_dir "$ROOT" docker push "$remote"
  echo "  ✅ Backend image pushed: $remote"
}

patch_frontend_api_base_url() {
  local env_path="$ROOT/frontend/src/environments/environment.production.ts"
  local api_url=$1
  python3 - "$env_path" "$api_url" <<'PY'
import json
import re
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
    print("❌ Could not find apiBaseUrl in environment.production.ts", file=sys.stderr)
    sys.exit(1)
p.write_text(new_text, encoding="utf-8")
print(f"✅ Set production apiBaseUrl to {api_url!r}")
PY
}

build_frontend() {
  echo ""
  echo "🎨 Building frontend application..."

  local fe="$ROOT/frontend"
  if [[ ! -d "$fe/node_modules" ]]; then
    run_in_dir "$fe" npm install
  fi

  # CloudFront routes /api/* to App Runner, so same-origin empty base URL.
  patch_frontend_api_base_url ""
  run_in_dir "$fe" npm run build -- --configuration production

  local out="$ROOT/frontend/dist/$ANGULAR_PROJECT/browser"
  if [[ ! -d "$out" ]]; then
    echo "  ❌ Frontend build output not found: $out"
    exit 1
  fi
  echo "  ✅ Frontend build complete"
}

upload_frontend() {
  echo ""
  echo "📤 Uploading frontend artifacts..."

  local fe_tf_dir="$ROOT/terraform/frontend"
  ensure_tf_ready "$fe_tf_dir"

  local bucket_name
  bucket_name="$(resolve_frontend_bucket_name "$fe_tf_dir")"
  if [[ -z "$bucket_name" || "$bucket_name" == "None" ]]; then
    echo "  ❌ Could not resolve frontend S3 bucket name."
    echo "     Ensure bucket exists or apply terraform/frontend first."
    exit 1
  fi
  local dist_id
  dist_id="$(resolve_cloudfront_distribution_id "$fe_tf_dir")"
  local cloudfront_url
  cloudfront_url="$(resolve_cloudfront_url "$fe_tf_dir")"
  local apprunner_url
  apprunner_url="$(resolve_apprunner_url "$fe_tf_dir")"

  local out="$ROOT/frontend/dist/$ANGULAR_PROJECT/browser/"
  run aws s3 sync "$out" "s3://$bucket_name/" --delete
  echo "  ✅ Frontend uploaded to s3://$bucket_name/"

  if [[ -n "$dist_id" && "$dist_id" != "None" ]]; then
    run aws cloudfront create-invalidation --distribution-id "$dist_id" --paths "/*" >/dev/null
    echo "  ✅ CloudFront invalidation created ($dist_id)"
  else
    echo "  ⚠️ No CloudFront distribution id found; skipped invalidation."
  fi

  echo ""
  echo "✅ Application deployment complete"
  if [[ -n "$cloudfront_url" ]]; then
    echo "   CloudFront URL: $cloudfront_url"
  fi
  if [[ -n "$apprunner_url" ]]; then
    echo "   App Runner URL: $apprunner_url"
  fi
}

main() {
  echo "🚀 Legal Companion App-Only Deployment"
  echo "=================================================="
  check_prerequisites
  build_and_push_backend
  build_frontend
  upload_frontend
}

main "$@"
