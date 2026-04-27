output "apprunner_service_url" {
  description = "App Runner HTTPS URL for the FastAPI service (direct; CloudFront can proxy /api in frontend stack)"
  value       = aws_apprunner_service.api.service_url
}

output "ecr_repository_url" {
  description = "ECR repository base URI (use tag e.g. :latest when pushing images)"
  value       = aws_ecr_repository.api.repository_url
}

output "apprunner_service_arn" {
  description = "App Runner service ARN"
  value       = aws_apprunner_service.api.arn
}

output "setup_instructions" {
  description = "Post-apply and image push notes"
  value       = <<-EOT
    API stack: App Runner (FastAPI) + ECR

    1) Build and push from the repo root (image must exist before first App Runner create if ECR is empty):
         docker build -f backend/api/Dockerfile -t counsel-api:latest .
         aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin <registry>
         docker tag counsel-api:latest ${aws_ecr_repository.api.repository_url}:latest
         docker push ${aws_ecr_repository.api.repository_url}:latest

    2) Or use: scripts/python deploy (builds, pushes, applies this stack + frontend).

    3) After apply, get URL: terraform output -raw apprunner_service_url

    4) Apply order for the full app: database → agents → this directory (api) → ../frontend
  EOT
}
