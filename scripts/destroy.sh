#!/usr/bin/env bash
#
# Bash equivalent of scripts/destroy.py:
# 1) Empty the S3 bucket
# 2) Destroy infrastructure with Terraform (frontend, then api)
# 3) Clean up local artifacts
#

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT

# ---------------------------------------------------------------------------
run() {
  echo "Running: $*"
  "$@" || return 1
}

# ---------------------------------------------------------------------------

confirm_destruction() {
  echo "⚠️  WARNING: This will destroy all Legal Companion infrastructure!"
  echo "This includes:"
  echo "  - CloudFront distribution"
  echo "  - API Gateway"
  echo "  - Lambda function"
  echo "  - S3 bucket and all contents"
  echo "  - IAM roles and policies"
  echo ""
  read -r -p "Are you sure you want to continue? Type 'yes' to confirm: " response
  [[ "${response,,}" == "yes" ]]
}

get_bucket_name() {
  local fe_dir="$ROOT/terraform/frontend"
  if [[ ! -d "$fe_dir" ]]; then
    echo "  ❌ Terraform directory not found: $fe_dir" >&2
    return
  fi
  (cd "$fe_dir" && terraform output -raw s3_bucket_name 2>/dev/null) || true
}

# Remove remaining object versions and delete markers (versioned buckets).
# The old Python used a subprocess call that did not run shell $(...), so it never
# actually executed; this implements the intended behavior via aws + python3.
purge_s3_object_versions() {
  local bucket_name=$1
  python3 - "$bucket_name" <<'PY'
import json, subprocess, sys

bucket = sys.argv[1]
aws = ["aws", "s3api"]


def main() -> None:
    while True:
        p = subprocess.run(
            aws + ["list-object-versions", "--bucket", bucket, "--output", "json"],
            capture_output=True,
            text=True,
        )
        if p.returncode != 0:
            break
        d = json.loads(p.stdout or "{}")
        objs = []
        for v in d.get("Versions", []):
            objs.append({"Key": v["Key"], "VersionId": v["VersionId"]})
        for m in d.get("DeleteMarkers", []):
            objs.append({"Key": m["Key"], "VersionId": m["VersionId"]})
        if not objs:
            break
        # delete-objects max 1000 per request
        for i in range(0, len(objs), 1000):
            chunk = objs[i : i + 1000]
            payload = json.dumps({"Objects": chunk})
            subprocess.run(
                aws + [
                    "delete-objects",
                    "--bucket",
                    bucket,
                    "--delete",
                    payload,
                ],
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    main()
PY
}

empty_s3_bucket() {
  local bucket_name=$1
  if [[ -z "$bucket_name" ]]; then
    echo "  ⚠️  No bucket name provided, skipping..."
    return
  fi

  echo ""
  echo "🗑️  Emptying S3 bucket: $bucket_name"

  if ! aws s3 ls "s3://$bucket_name" &>/dev/null; then
    echo "  Bucket $bucket_name doesn't exist or is already empty"
    return
  fi

  echo "  Deleting all objects from $bucket_name..."
  # shellcheck disable=SC2312
  run aws s3 rm "s3://$bucket_name/" --recursive

  if command -v python3 &>/dev/null; then
    echo "  Deleting all object versions (if any)…"
    purge_s3_object_versions "$bucket_name"
  else
    echo "  ⚠️  python3 not found; if the bucket is versioned, you may need to clear versions in the console"
  fi

  echo "  ✅ Bucket $bucket_name emptied"
}

# Destroy frontend (S3 + CloudFront) first, then api, matching destroy.py
destroy_terraform() {
  echo ""
  echo "🏗️  Destroying infrastructure with Terraform..."

  local fe_dir="$ROOT/terraform/frontend"
  local api_dir="$ROOT/terraform/api"
  local name
  for name_dir in "frontend:$fe_dir" "api:$api_dir"; do
    name=${name_dir%%:*}
    local d=${name_dir#*:}
    if [[ ! -d "$d" ]]; then
      echo "  ⚠️  Skipping $name: directory not found: $d"
      continue
    fi
    if [[ ! -d "$d/.terraform" ]]; then
      echo "  ⚠️  Skipping $name: not initialized"
      continue
    fi
    echo "  Running terraform destroy in $name…"
    echo "  Type 'yes' when prompted to confirm destruction."
    if ! (cd "$d" && terraform destroy); then
      echo "  ❌ Failed to destroy $name"
      echo "  You may need to manually clean up resources in AWS Console"
      return 1
    fi
    echo "  ✅ $name stack destroyed"
  done
  return 0
}

clean_local_artifacts() {
  echo ""
  echo "🧹 Cleaning up local artifacts..."

  local a
  for a in \
    "$ROOT/backend/api/api_lambda.zip" \
    "$ROOT/frontend/dist"; do
    if [[ -e "$a" ]]; then
      if [[ -f "$a" ]]; then
        rm -f -- "$a"
        echo "  Deleted: $a"
      else
        rm -rf -- "$a"
        echo "  Deleted directory: $a"
      fi
    fi
  done
  echo "  ✅ Local artifacts cleaned"
}

main() {
  echo "💥 Legal Companion Infrastructure Destruction"
  echo "============================================================"

  if ! confirm_destruction; then
    echo ""
    echo "❌ Destruction cancelled"
    exit 0
  fi

  local bucket_name
  bucket_name=$(get_bucket_name) || true

  if [[ -n "${bucket_name:-}" ]]; then
    empty_s3_bucket "$bucket_name"
  else
    echo "  ⚠️  Could not read s3_bucket_name (skip emptying, or not initialized?)"
  fi

  # Same as destroy.py: does not short-circuit on failed destroy (local cleanup still runs)
  destroy_terraform || true

  clean_local_artifacts

  echo ""
  echo "============================================================"
  echo "✅ Destruction complete!"
  echo ""
  echo "To redeploy, run:"
  echo "  ./scripts/deploy.sh"
  echo "  # or: uv run scripts/deploy.py"
}

main "$@"
