variable "aws_region" {
  description = "AWS region for App Runner and ECR."
  type        = string
  default     = "eu-west-1"
}

variable "image_tag" {
  description = "Docker image tag to deploy from ECR."
  type        = string
  default     = "latest"
}

variable "auto_deployments_enabled" {
  description = "Whether App Runner should auto-deploy new ECR image revisions."
  type        = bool
  default     = true
}

variable "instance_cpu" {
  description = "App Runner CPU setting."
  type        = string
  default     = "1 vCPU"
}

variable "instance_memory" {
  description = "App Runner memory setting."
  type        = string
  default     = "2 GB"
}

variable "openai_api_key" {
  description = "OpenAI API key used by the API service."
  type        = string
  sensitive   = true
}

variable "chat_openai_model" {
  description = "OpenAI chat model used by backend chat service."
  type        = string
  default     = "gpt-4o"
}

variable "aurora_cluster_arn" {
  description = "Aurora cluster ARN for IAM policy scope."
  type        = string
}

variable "aurora_cluster_endpoint" {
  description = "Aurora writer endpoint hostname."
  type        = string
}

variable "aurora_secret_arn" {
  description = "Secrets Manager ARN containing Aurora database credentials."
  type        = string
}

variable "aurora_database" {
  description = "Aurora database name used by the API."
  type        = string
  default     = "counsel"
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL for JWT validation."
  type        = string
}

variable "clerk_issuer" {
  description = "Clerk issuer for JWT validation."
  type        = string
}

variable "cors_origins" {
  description = "Comma-separated list of allowed CORS origins."
  type        = string
  default     = "http://localhost:3000,http://localhost:4200"
}

variable "sqs_queue_arn" {
  description = "Optional SQS queue ARN used by the API (defaults to counsel-agents in this account/region)."
  type        = string
  default     = ""
}

variable "sqs_queue_url" {
  description = "Optional SQS queue URL passed to the API runtime."
  type        = string
  default     = ""
}

variable "sagemaker_endpoint" {
  description = "Optional SageMaker endpoint name for embeddings."
  type        = string
  default     = ""
}
