variable "aws_region" {
  description = "AWS region for App Runner, ECR, and IAM"
  type        = string
  default     = "eu-west-1"
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL for JWT validation in the API (App Runner)"
  type        = string
}

variable "clerk_issuer" {
  description = "Clerk issuer URL (optional; match your Clerk app)"
  type        = string
  default     = ""
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
