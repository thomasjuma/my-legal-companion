#!/usr/bin/env python3
"""
Deploy the Legal Companion infrastructure.
1. Ensure ECR exists (terraform apply -target) and build/push the API Docker image to ECR
2. Apply Terraform (App Runner, CloudFront, S3, …)
3. Set `apiBaseUrl` in `environment.production.ts` (default `""` = same-origin `/api` on CloudFront) and `ng build`
4. Sync the Angular browser bundle to S3 and invalidate CloudFront

Set `openai_api_key` in `terraform/api/terraform.tfvars` (sensitive) for chat in App Runner, or add the key
in the AWS App Runner console / Secrets Manager after deploy. Apply `terraform/api` before `terraform/frontend`.
"""

import re
import subprocess
import sys
import os
import json
from pathlib import Path

# Angular 20+ application output (see frontend/angular.json project name)
ANGULAR_PROJECT = "my-legal-companion-ui"


def run_command(cmd, cwd=None, check=True, capture_output=False, env=None):
    """Run a command and optionally capture output."""
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")

    if capture_output:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=isinstance(cmd, str), env=env)
        if check and result.returncode != 0:
            print(f"Error: {result.stderr}")
            sys.exit(1)
        return result.stdout.strip()
    else:
        result = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), env=env)
        if check and result.returncode != 0:
            sys.exit(1)
        return None


def check_prerequisites():
    """Check that all required tools are installed."""
    print("🔍 Checking prerequisites...")

    # Check for required tools
    tools = {
        "docker": "Docker is required to build the API image",
        "terraform": "Terraform is required for infrastructure deployment",
        "npm": "npm is required for building the frontend",
        "aws": "AWS CLI is required for S3 sync and CloudFront invalidation"
    }

    for tool, message in tools.items():
        try:
            run_command([tool, "--version"], capture_output=True)
            print(f"  ✅ {tool} is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"  ❌ {message}")
            sys.exit(1)

    # Check if Docker is running
    try:
        run_command(["docker", "info"], capture_output=True)
        print("  ✅ Docker is running")
    except subprocess.CalledProcessError:
        print("  ❌ Docker is not running. Please start Docker Desktop.")
        sys.exit(1)

    # Check AWS credentials
    try:
        run_command(["aws", "sts", "get-caller-identity"], capture_output=True)
        print("  ✅ AWS credentials configured")
    except subprocess.CalledProcessError:
        print("  ❌ AWS credentials not configured. Run 'aws configure'")
        sys.exit(1)


def _ecr_registry_host(ecr_repo_url: str) -> str:
    return ecr_repo_url.split("/")[0].strip()


def build_and_push_api_image():
    """Create ECR repo in AWS, build the API image, and push :latest (App Runner auto-deploys)."""
    print("\n🐳 Building and pushing API image to ECR...")

    root = Path(__file__).parent.parent
    api_tf_dir = root / "terraform" / "api"
    if not (root / "backend" / "api" / "Dockerfile").exists():
        print("  ❌ backend/api/Dockerfile not found")
        sys.exit(1)

    if not (api_tf_dir / ".terraform").exists():
        run_command(["terraform", "init"], cwd=api_tf_dir)

    print("  Ensuring ECR repository exists…")
    run_command(
        [
            "terraform",
            "apply",
            "-auto-approve",
            "-target=aws_ecr_repository.api",
        ],
        cwd=api_tf_dir,
    )

    ecr_url = run_command(
        ["terraform", "output", "-raw", "ecr_repository_url"],
        cwd=api_tf_dir,
        capture_output=True,
    )
    reg = _ecr_registry_host(ecr_url)
    local_tag = "counsel-api:latest"
    remote = f"{ecr_url}:latest"

    run_command(
        [
            "docker",
            "build",
            "-f",
            "backend/api/Dockerfile",
            "-t",
            local_tag,
            ".",
        ],
        cwd=root,
    )
    run_command(["docker", "tag", local_tag, remote], cwd=root)

    print("  Logging in to ECR and pushing…")
    region = (
        run_command(["aws", "configure", "get", "region"], capture_output=True)
        or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    )
    login_pw = run_command(
        ["aws", "ecr", "get-login-password", "--region", region],
        capture_output=True,
    )
    p = subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", reg],
        input=login_pw,
        text=True,
        capture_output=True,
    )
    if p.returncode != 0:
        print(p.stderr or p.stdout, file=sys.stderr)
        sys.exit(1)
    run_command(["docker", "push", remote], cwd=root)
    print(f"  ✅ Pushed {remote}")


def _angular_browser_out_dir(frontend_dir: Path) -> Path:
    return frontend_dir / "dist" / ANGULAR_PROJECT / "browser"


def patch_angular_production_api_url(frontend_dir: Path, api_url: str) -> None:
    """
    Set `apiBaseUrl` in environment.production.ts (used by `ng build` via fileReplacements in angular.json).
    The API may be the API Gateway URL; CORS allows the CloudFront origin. Same-origin (empty) also works
    if you only call relative /api/... on CloudFront — we set the deploy URL to match a direct Gateway client.
    """
    env_path = frontend_dir / "src" / "environments" / "environment.production.ts"
    if not env_path.exists():
        print(f"  ❌ Missing {env_path}")
        sys.exit(1)

    text = env_path.read_text(encoding="utf-8")
    # json.dumps for correct TS/JS string escaping
    value = json.dumps(api_url)
    new_text, n = re.subn(
        r"apiBaseUrl:\s*('[^']*'|\"[^\"]*\")",
        f"apiBaseUrl: {value}",
        text,
        count=1,
    )
    if n != 1:
        print("  ❌ Could not find apiBaseUrl: '...' in environment.production.ts to patch")
        sys.exit(1)
    env_path.write_text(new_text, encoding="utf-8")
    print(f"  ✅ Set apiBaseUrl in environment.production.ts: {api_url}")


def build_frontend(api_url: str = ""):
    """Build the Angular frontend (production configuration). `apiBaseUrl` same-origin is ``""`` when the API is behind CloudFront /api/*."""
    print("\n🎨 Building frontend...")

    frontend_dir = Path(__file__).parent.parent / "frontend"

    if not frontend_dir.exists():
        print(f"  ❌ Frontend directory not found: {frontend_dir}")
        sys.exit(1)

    # Install dependencies if needed
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        print("  Installing dependencies...")
        run_command(["npm", "install"], cwd=frontend_dir)

    patch_angular_production_api_url(frontend_dir, api_url)

    build_env = os.environ.copy()
    build_env["NODE_ENV"] = "production"
    print("  Building Angular app for production (ng build)...")
    run_command(
        ["npm", "run", "build", "--", "--configuration", "production"],
        cwd=frontend_dir,
        env=build_env,
    )

    out_dir = _angular_browser_out_dir(frontend_dir)
    if not out_dir.exists():
        print(f"  ❌ Build output not found: {out_dir}")
        print(f"  Expected the browser bundle at dist/{ANGULAR_PROJECT}/browser/")
        sys.exit(1)

    print("  ✅ Frontend built successfully")


def deploy_terraform():
    """Apply terraform/api (App Runner + ECR) then terraform/frontend (S3 + CloudFront)."""
    print("\n🏗️  Deploying infrastructure with Terraform...")

    repo = Path(__file__).parent.parent
    api_dir = repo / "terraform" / "api"
    fe_dir = repo / "terraform" / "frontend"

    for d in (api_dir, fe_dir):
        if not d.exists():
            print(f"  ❌ Terraform directory not found: {d}")
            sys.exit(1)

    for d in (api_dir, fe_dir):
        if not (d / ".terraform").exists():
            print(f"  Initializing Terraform in {d.name}…")
            run_command(["terraform", "init"], cwd=d)

    print("  Planning api…")
    run_command(["terraform", "plan"], cwd=api_dir)
    print("\n  Applying api (App Runner, ECR, IAM)…")
    run_command(["terraform", "apply", "-auto-approve"], cwd=api_dir)

    print("\n  Planning frontend…")
    run_command(["terraform", "plan"], cwd=fe_dir)
    print("\n  Applying frontend (S3, CloudFront)…")
    run_command(["terraform", "apply", "-auto-approve"], cwd=fe_dir)

    print("\n  Getting outputs (frontend, includes remote api URLs)…")
    return json.loads(
        run_command(
            ["terraform", "output", "-json"],
            cwd=fe_dir,
            capture_output=True,
        )
    )


def upload_frontend(bucket_name, cloudfront_id):
    """Upload frontend files to S3."""
    print(f"\n📤 Uploading frontend to S3 bucket: {bucket_name}")

    frontend_dir = _angular_browser_out_dir(Path(__file__).parent.parent / "frontend")

    if not frontend_dir.exists():
        print(f"  ❌ Frontend build not found: {frontend_dir}")
        sys.exit(1)

    # First, clear the bucket
    print("  Clearing S3 bucket...")
    run_command([
        "aws", "s3", "rm",
        f"s3://{bucket_name}/",
        "--recursive"
    ])

    # Upload HTML files with correct content type and no-cache
    print("  Uploading HTML files...")
    run_command([
        "aws", "s3", "cp",
        str(frontend_dir) + "/",
        f"s3://{bucket_name}/",
        "--recursive",
        "--exclude", "*",
        "--include", "*.html",
        "--content-type", "text/html",
        "--cache-control", "max-age=0,no-cache,no-store,must-revalidate"
    ])

    # Upload CSS files
    print("  Uploading CSS files...")
    run_command([
        "aws", "s3", "cp",
        str(frontend_dir) + "/",
        f"s3://{bucket_name}/",
        "--recursive",
        "--exclude", "*",
        "--include", "*.css",
        "--content-type", "text/css",
        "--cache-control", "max-age=31536000,public"
    ])

    # Upload JS files
    print("  Uploading JavaScript files...")
    run_command([
        "aws", "s3", "cp",
        str(frontend_dir) + "/",
        f"s3://{bucket_name}/",
        "--recursive",
        "--exclude", "*",
        "--include", "*.js",
        "--content-type", "application/javascript",
        "--cache-control", "max-age=31536000,public"
    ])

    # Upload JSON files
    print("  Uploading JSON files...")
    run_command([
        "aws", "s3", "cp",
        str(frontend_dir) + "/",
        f"s3://{bucket_name}/",
        "--recursive",
        "--exclude", "*",
        "--include", "*.json",
        "--content-type", "application/json",
        "--cache-control", "max-age=31536000,public"
    ])

    # Upload images
    for ext, content_type in [
        ("*.png", "image/png"),
        ("*.jpg", "image/jpeg"),
        ("*.jpeg", "image/jpeg"),
        ("*.gif", "image/gif"),
        ("*.svg", "image/svg+xml"),
        ("*.ico", "image/x-icon")
    ]:
        run_command([
            "aws", "s3", "cp",
            str(frontend_dir) + "/",
            f"s3://{bucket_name}/",
            "--recursive",
            "--exclude", "*",
            "--include", ext,
            "--content-type", content_type,
            "--cache-control", "max-age=31536000,public"
        ])

    # Upload any remaining files with generic content type
    print("  Uploading remaining files...")
    run_command([
        "aws", "s3", "sync",
        str(frontend_dir) + "/",
        f"s3://{bucket_name}/",
        "--cache-control", "max-age=31536000,public"
    ])

    print(f"  ✅ Frontend uploaded successfully")

    # Invalidate CloudFront cache
    print(f"\n🔄 Invalidating CloudFront cache...")
    result = run_command([
        "aws", "cloudfront", "create-invalidation",
        "--distribution-id", cloudfront_id,
        "--paths", "/*"
    ], capture_output=True)

    print(f"  ✅ CloudFront invalidation created")


def display_deployment_info(outputs):
    """Display deployment information without modifying local env files."""
    print("\n📝 Deployment Information")

    cloudfront_url = outputs["cloudfront_url"]["value"]
    ar = outputs.get("apprunner_service_url")
    appr = (ar or {}).get("value", "")

    print(f"\n  ✅ Deployment successful!")
    print(f"\n  CloudFront (site + /api/*): {cloudfront_url}")
    if appr:
        print(f"  App Runner (direct): {appr}")
    print(f"\n  Note: `src/environments/environment.ts` for local dev is unchanged.")
    print("  Production build uses `apiBaseUrl` '' for same-origin /api on CloudFront.")


def main():
    """Main deployment function."""
    print("🚀 Legal Companion Deployment")
    print("=" * 50)

    # Check prerequisites
    check_prerequisites()

    build_and_push_api_image()

    # Full Terraform (App Runner, CloudFront, S3, …)
    outputs = deploy_terraform()

    # Same-origin API on CloudFront: leave apiBaseUrl empty
    build_frontend("")

    bucket_name = outputs["s3_bucket_name"]["value"]
    dist_o = outputs.get("cloudfront_distribution_id")
    dist_id = (dist_o or {}).get("value")
    if dist_id:
        upload_frontend(bucket_name, dist_id)
    else:
        print("\n📤 Uploading frontend to S3 (no distribution id in outputs)…")
        run_command([
            "aws", "s3", "sync",
            str(_angular_browser_out_dir(Path(__file__).parent.parent / "frontend")) + "/",
            f"s3://{bucket_name}/",
            "--delete"
        ])

    # Display deployment info (no longer modifies .env.local)
    display_deployment_info(outputs)

    print("\n" + "=" * 50)
    print("✅ Deployment complete!")
    print(f"\n🌐 Your application is available at:")
    print(f"   {outputs['cloudfront_url']['value']}")
    ap = outputs.get("apprunner_service_url")
    apu = (ap or {}).get("value", "counsel-api")
    print(f"\n📊 Monitor the API: AWS Console → App Runner (URL: {apu})")
    print("\n⏳ Note: CloudFront distribution may take 5-10 minutes to fully propagate")


if __name__ == "__main__":
    main()