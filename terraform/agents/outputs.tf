output "sqs_queue_url" {
  description = "URL of the SQS queue used to enqueue work for agents"
  value       = aws_sqs_queue.agents.url
}

output "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  value       = aws_sqs_queue.agents.arn
}

output "setup_instructions" {
  description = "Order of apply for the Legal Companion Terraform stacks"
  value       = <<-EOT
    Apply in order (each uses local terraform.tfstate in its directory):
      1. terraform/database
      2. terraform/agents   (this directory)
      3. terraform/api     (App Runner + ECR for FastAPI; reads 1. and 2.)
      4. terraform/frontend (S3 + CloudFront; reads 3. for the API origin)
  EOT
}
