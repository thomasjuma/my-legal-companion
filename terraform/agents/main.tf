# SQS and shared resources for the assistant / agent workers (consumed by frontend API Lambda)
terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  name_prefix  = "counsel"
  queue_name   = "${local.name_prefix}-agents"
  project_tags = { Project = local.name_prefix, Part = "agents" }
}

resource "aws_sqs_queue" "agents" {
  name = local.queue_name
  tags = local.project_tags
}
