#!/usr/bin/env bash
#
# Import pre-existing API infrastructure resources into terraform/api state.
# Use when apply fails with RepositoryAlreadyExists / EntityAlreadyExists / Duplicate SG errors.

set -euo pipefail

TF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_in_tf() {
  (cd "$TF_DIR" && "$@")
}

tf_state_has() {
  local address="$1"
  run_in_tf terraform state show "$address" >/dev/null 2>&1
}

import_if_missing() {
  local address="$1"
  local import_id="${2:-}"
  local label="$3"

  if [[ -z "$import_id" || "$import_id" == "None" ]]; then
    return 0
  fi

  if tf_state_has "$address"; then
    echo "✓ Already in state: $address"
    return 0
  fi

  echo "→ Importing $label"
  run_in_tf terraform import "$address" "$import_id"
}

echo "Preparing terraform/api state imports..."

if [[ ! -d "$TF_DIR/.terraform" ]]; then
  echo "Initializing Terraform..."
  run_in_tf terraform init
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGION="$(aws configure get region 2>/dev/null | tr -d '[:space:]')"
REGION="${REGION:-${AWS_DEFAULT_REGION:-eu-west-1}}"

REPO_NAME="counsel-api"
ECR_ACCESS_ROLE="counsel-apprunner-ecr-access"
INSTANCE_ROLE="counsel-apprunner-instance"
SG_NAME="counsel-apprunner-connector"
VPC_CONNECTOR_NAME="counsel-api-vpc"
APP_RUNNER_SERVICE_NAME="counsel-api"

if aws ecr describe-repositories --repository-names "$REPO_NAME" >/dev/null 2>&1; then
  import_if_missing "aws_ecr_repository.api" "$REPO_NAME" "ECR repository $REPO_NAME"
fi

if aws iam get-role --role-name "$ECR_ACCESS_ROLE" >/dev/null 2>&1; then
  import_if_missing "aws_iam_role.apprunner_ecr_access" "$ECR_ACCESS_ROLE" "IAM role $ECR_ACCESS_ROLE"

  ECR_POLICY_ARN="arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
  ATTACHED_ECR_POLICY="$(
    aws iam list-attached-role-policies \
      --role-name "$ECR_ACCESS_ROLE" \
      --query "AttachedPolicies[?PolicyArn=='$ECR_POLICY_ARN'].PolicyArn | [0]" \
      --output text 2>/dev/null || true
  )"
  if [[ "$ATTACHED_ECR_POLICY" == "$ECR_POLICY_ARN" ]]; then
    import_if_missing \
      "aws_iam_role_policy_attachment.apprunner_ecr" \
      "$ECR_ACCESS_ROLE/$ECR_POLICY_ARN" \
      "IAM role policy attachment for $ECR_ACCESS_ROLE"
  fi
fi

if aws iam get-role --role-name "$INSTANCE_ROLE" >/dev/null 2>&1; then
  import_if_missing "aws_iam_role.apprunner_instance" "$INSTANCE_ROLE" "IAM role $INSTANCE_ROLE"

  if aws iam get-role-policy --role-name "$INSTANCE_ROLE" --policy-name counsel-apprunner-aurora >/dev/null 2>&1; then
    import_if_missing \
      "aws_iam_role_policy.apprunner_aurora" \
      "$INSTANCE_ROLE:counsel-apprunner-aurora" \
      "IAM inline policy counsel-apprunner-aurora"
  fi

  if aws iam get-role-policy --role-name "$INSTANCE_ROLE" --policy-name counsel-apprunner-sqs >/dev/null 2>&1; then
    import_if_missing \
      "aws_iam_role_policy.apprunner_sqs" \
      "$INSTANCE_ROLE:counsel-apprunner-sqs" \
      "IAM inline policy counsel-apprunner-sqs"
  fi

  if aws iam get-role-policy --role-name "$INSTANCE_ROLE" --policy-name counsel-apprunner-invoke >/dev/null 2>&1; then
    import_if_missing \
      "aws_iam_role_policy.apprunner_invoke" \
      "$INSTANCE_ROLE:counsel-apprunner-invoke" \
      "IAM inline policy counsel-apprunner-invoke"
  fi
fi

DEFAULT_VPC_ID="$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text 2>/dev/null || true)"
if [[ -n "$DEFAULT_VPC_ID" && "$DEFAULT_VPC_ID" != "None" ]]; then
  SG_ID="$(
    aws ec2 describe-security-groups \
      --filters "Name=vpc-id,Values=$DEFAULT_VPC_ID" "Name=group-name,Values=$SG_NAME" \
      --query 'SecurityGroups[0].GroupId' \
      --output text 2>/dev/null || true
  )"
  import_if_missing "aws_security_group.apprunner_vpc_connector" "$SG_ID" "security group $SG_NAME"
fi

VPC_CONNECTOR_ARN="$(
  aws apprunner list-vpc-connectors \
    --query "VpcConnectors[?VpcConnectorName=='$VPC_CONNECTOR_NAME'].VpcConnectorArn | [0]" \
    --output text 2>/dev/null || true
)"
import_if_missing "aws_apprunner_vpc_connector.api" "$VPC_CONNECTOR_ARN" "App Runner VPC connector $VPC_CONNECTOR_NAME"

SERVICE_ARN="$(
  aws apprunner list-services \
    --query "ServiceSummaryList[?ServiceName=='$APP_RUNNER_SERVICE_NAME'].ServiceArn | [0]" \
    --output text 2>/dev/null || true
)"
import_if_missing "aws_apprunner_service.api" "$SERVICE_ARN" "App Runner service $APP_RUNNER_SERVICE_NAME"

echo ""
echo "✅ Import pass complete for account $ACCOUNT_ID in region $REGION."
echo "Next:"
echo "  cd terraform/api"
echo "  terraform plan"
echo "  terraform apply"
