#!/usr/bin/env python3
"""
Deploy the Legal Companion infrastructure.
This script:
1. Packages the Lambda function
2. Deploys infrastructure with Terraform to get API URL
3. Patches `frontend/src/environments/environment.production.ts` with the API base URL, then runs `ng build`
4. Uploads the Angular browser bundle from `dist/.../browser` to S3
5. Invalidates CloudFront cache

NOTE: `environment.production.ts` is overwritten for `apiBaseUrl` each deploy; commit other production
secrets/keys to that file as needed, or set them in CI. Local `environment.ts` / `environment.development` are not modified.
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
        "docker": "Docker is required for Lambda packaging",
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


def package_lambda():
    """Package the Lambda function using Docker."""
    print("\n📦 Packaging Lambda function...")

    api_dir = Path(__file__).parent.parent / "backend" / "api"

    if not api_dir.exists():
        print(f"  ❌ API directory not found: {api_dir}")
        sys.exit(1)

    # Run the packaging script
    run_command(["uv", "run", "package_docker.py"], cwd=api_dir)

    # Verify the package was created
    lambda_zip = api_dir / "api_lambda.zip"
    if not lambda_zip.exists():
        print(f"  ❌ Lambda package not created: {lambda_zip}")
        sys.exit(1)

    size_mb = lambda_zip.stat().st_size / (1024 * 1024)
    print(f"  ✅ Lambda package created: {lambda_zip} ({size_mb:.2f} MB)")


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


def build_frontend(api_url=None):
    """Build the Angular frontend (production configuration)."""
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

    if api_url:
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
    """Deploy infrastructure with Terraform."""
    print("\n🏗️  Deploying infrastructure with Terraform...")

    terraform_dir = Path(__file__).parent.parent / "terraform" / "frontend"

    if not terraform_dir.exists():
        print(f"  ❌ Terraform directory not found: {terraform_dir}")
        sys.exit(1)

    # Initialize Terraform if needed
    if not (terraform_dir / ".terraform").exists():
        print("  Initializing Terraform...")
        run_command(["terraform", "init"], cwd=terraform_dir)

    # Plan the deployment
    print("  Planning deployment...")
    run_command(["terraform", "plan"], cwd=terraform_dir)

    # Apply the deployment
    print("\n  Applying deployment...")
    print("  Creating AWS resources...")
    run_command(["terraform", "apply", "-auto-approve"], cwd=terraform_dir)

    # Get outputs
    print("\n  Getting outputs...")
    outputs = run_command(
        ["terraform", "output", "-json"],
        cwd=terraform_dir,
        capture_output=True
    )

    return json.loads(outputs)


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

    # Extract values from outputs
    api_url = outputs["api_gateway_url"]["value"]
    cloudfront_url = outputs["cloudfront_url"]["value"]

    print(f"\n  ✅ Deployment successful!")
    print(f"\n  CloudFront URL: {cloudfront_url}")
    print(f"  API Gateway URL: {api_url}")
    print(f"\n  Note: `src/environments/environment.ts` for local dev is unchanged.")
    print("  The deploy set `apiBaseUrl` in environment.production.ts for this build.")


def main():
    """Main deployment function."""
    print("🚀 Legal Companion Deployment")
    print("=" * 50)

    # Check prerequisites
    check_prerequisites()

    # Package Lambda
    package_lambda()

    # Deploy infrastructure first to get the API URL
    outputs = deploy_terraform()

    # Get the API URL from terraform outputs
    api_url = outputs["api_gateway_url"]["value"]

    # Build frontend with the production API URL
    build_frontend(api_url)

    # Extract CloudFront distribution ID
    cloudfront_url = outputs["cloudfront_url"]["value"]
    # Extract distribution ID from CloudFront URL
    dist_id_output = run_command([
        "aws", "cloudfront", "list-distributions",
        "--query", f"DistributionList.Items[?DomainName=='{cloudfront_url.replace('https://', '')}'].Id",
        "--output", "text"
    ], capture_output=True)

    if not dist_id_output:
        print("  ⚠️  Could not find CloudFront distribution ID")
        print("  You'll need to manually invalidate the cache")
        cloudfront_id = None
    else:
        cloudfront_id = dist_id_output

    # Upload frontend
    bucket_name = outputs["s3_bucket_name"]["value"]
    if cloudfront_id:
        upload_frontend(bucket_name, cloudfront_id)
    else:
        print("\n📤 Uploading frontend to S3...")
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
    print(f"\n📊 Monitor your Lambda function at:")
    print(f"   AWS Console > Lambda > {outputs['lambda_function_name']['value']}")
    print("\n⏳ Note: CloudFront distribution may take 5-10 minutes to fully propagate")


if __name__ == "__main__":
    main()