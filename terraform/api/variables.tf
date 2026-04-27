variable "aws_region" {
  description = "AWS region for App Runner, ECR, and IAM"
  type        = string
  default     = "eu-west-1"
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL for JWT validation in the API (App Runner)"
  type        = string

  validation {
    condition     = can(regex("^https://.+/.well-known/jwks\\.json$", var.clerk_jwks_url))
    error_message = "clerk_jwks_url must be a valid HTTPS Clerk JWKS URL ending in /.well-known/jwks.json."
  }
}

variable "clerk_issuer" {
  description = "Clerk issuer URL (optional; match your Clerk app)"
  type        = string
  default     = ""
}

variable "aurora_cluster_arn" {
  description = "Existing Aurora cluster ARN used by the API"
  type        = string
}

variable "aurora_cluster_endpoint" {
  description = "Existing Aurora writer endpoint used by the API"
  type        = string
}

variable "aurora_secret_arn" {
  description = "Secrets Manager secret ARN containing Aurora database credentials"
  type        = string
}

variable "aurora_database_name" {
  description = "Aurora database name used by the API"
  type        = string
  default     = "counsel"
}

variable "openai_api_key" {
  description = "OpenAI API key for the chat service (sensitive; prefer App Runner / Secrets in production)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "cors_extra_origins" {
  description = "Optional extra CORS origins (e.g. CloudFront URL) when not using same-origin /api on CloudFront"
  type        = list(string)
  default     = []
}
