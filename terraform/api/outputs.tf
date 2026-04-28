output "ecr_repository_url" {
  description = "ECR repository URL for the API image."
  value       = aws_ecr_repository.api.repository_url
}

output "apprunner_service_arn" {
  description = "App Runner service ARN."
  value       = aws_apprunner_service.api.arn
}

output "apprunner_service_url" {
  description = "HTTPS URL for the App Runner API service."
  value       = "https://${aws_apprunner_service.api.service_url}"
}

output "vpc_connector_arn" {
  description = "ARN of the App Runner VPC connector."
  value       = aws_apprunner_vpc_connector.api.arn
}

output "setup_instructions" {
  description = "Post-deploy guidance."
  value       = <<-EOT
    API stack: App Runner (FastAPI) + ECR

    1) Build and push from the repo root (image must exist before first App Runner create if ECR is empty):
         docker build -f backend/api/Dockerfile -t counsel-api:latest .
         aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${split("/", aws_ecr_repository.api.repository_url)[0]}
         docker tag counsel-api:latest ${aws_ecr_repository.api.repository_url}:latest
         docker push ${aws_ecr_repository.api.repository_url}:latest

    2) Or use: scripts/deploy.py (builds, pushes, and applies api + frontend stacks).

    3) Service URL:
         https://${aws_apprunner_service.api.service_url}

    4) Apply order for the full app:
         terraform/database -> terraform/agents (optional) -> terraform/api -> terraform/frontend
  EOT
}
