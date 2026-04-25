variable "aws_region" {
  description = "AWS region for resources"
  type        = string
}

variable "assistant_model" {
  description = "Model for the assistant agent"
  type        = string
  default     = "bedrock/amazon.nova-pro-v1:0"
}

variable "openai_api_key" {
  description = "OpenAI API key for the assistant agent"
  type        = string
  sensitive   = true
}

variable "counsel_api_endpoint" {
  description = "Counsel API endpoint"
  type        = string
}

variable "counsel_api_key" {
  description = "Counsel API key for ingestion"
  type        = string
  sensitive   = true
}

variable "scheduler_enabled" {
  description = "Enable automated assistant scheduler"
  type        = bool
  default     = false
}