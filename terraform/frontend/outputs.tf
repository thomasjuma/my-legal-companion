output "cloudfront_url" {
  description = "CloudFront distribution URL (static site + /api to App Runner)"
  value       = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "apprunner_service_url" {
  description = "Direct App Runner service URL (from api stack; prefer CloudFront /api in production)"
  value       = try(data.terraform_remote_state.api.outputs.apprunner_service_url, "apply ../api first")
}

output "ecr_repository_url" {
  description = "ECR image URI for the API (api stack; tag e.g. :latest)"
  value       = try(data.terraform_remote_state.api.outputs.ecr_repository_url, "apply ../api first")
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for the frontend"
  value       = aws_s3_bucket.frontend.id
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for cache invalidation)"
  value       = aws_cloudfront_distribution.main.id
}

output "setup_instructions" {
  description = "Post-deploy notes"
  value       = <<-EOT

    ✅ Frontend & App Runner API deployed (App Runner/ECR in ../api)

    Public site + API: https://${aws_cloudfront_distribution.main.domain_name} (paths /api/* → App Runner)
    App Runner: ${try(data.terraform_remote_state.api.outputs.apprunner_service_url, "(not set — run terraform/apply in ../api)")}
    S3: ${aws_s3_bucket.frontend.id}
    ECR: ${try(data.terraform_remote_state.api.outputs.ecr_repository_url, "(not set — run apply in ../api)")}

    1) Push a new image to ECR, tag `latest`, to redeploy the API (auto deploy if enabled on the service).

    2) Invalidate CloudFront after frontend upload:
         aws cloudfront create-invalidation --distribution-id ${aws_cloudfront_distribution.main.id} --paths "/*"

    3) Logs: AWS Console → App Runner → counsel-api → Logs

    Destroy: from repo `scripts/uv run destroy.py` (or `terraform destroy` in this directory).
  EOT
}
