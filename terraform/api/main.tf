# FastAPI (backend/api) on AWS App Runner (Managed Containers) + ECR
# Apply after terraform/database and terraform/agents; terraform/frontend reads this stack via remote state.

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
data "aws_region" "current" {}

data "terraform_remote_state" "agents" {
  backend = "local"
  config = {
    path = "../agents/terraform.tfstate"
  }
}

data "aws_secretsmanager_secret_version" "aurora_db" {
  secret_id = var.aurora_secret_arn
}

locals {
  name_prefix = "counsel"

  common_tags = {
    Project   = "counsel"
    Part      = "api"
    ManagedBy = "terraform"
  }

  cors_env = join(",", compact(concat(
    ["http://localhost:4200"],
    [for o in var.cors_extra_origins : chomp(o) if chomp(o) != ""]
  )))

  db_creds     = jsondecode(data.aws_secretsmanager_secret_version.aurora_db.secret_string)
  database_url = "postgresql+psycopg://${urlencode(local.db_creds.username)}:${urlencode(local.db_creds.password)}@${var.aurora_cluster_endpoint}:5432/${var.aurora_database_name}"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "apprunner_vpc_connector" {
  name        = "${local.name_prefix}-apprunner-connector"
  description = "App Runner VPC connector: egress to Aurora and AWS APIs"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-apprunner-connector" })
}

resource "aws_apprunner_vpc_connector" "api" {
  vpc_connector_name = "${local.name_prefix}-api-vpc"
  subnets            = data.aws_subnets.default.ids
  security_groups    = [aws_security_group.apprunner_vpc_connector.id]
  tags               = local.common_tags
}

resource "aws_ecr_repository" "api" {
  name                 = "${local.name_prefix}-api"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
  tags = local.common_tags
}

resource "aws_iam_role" "apprunner_ecr_access" {
  name = "${local.name_prefix}-apprunner-ecr-access"
  tags = local.common_tags
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "build.apprunner.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr" {
  role       = aws_iam_role.apprunner_ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

resource "aws_iam_role" "apprunner_instance" {
  name = "${local.name_prefix}-apprunner-instance"
  tags = local.common_tags
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "tasks.apprunner.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "apprunner_aurora" {
  name = "${local.name_prefix}-apprunner-aurora"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds-data:ExecuteStatement",
          "rds-data:BatchExecuteStatement",
          "rds-data:BeginTransaction",
          "rds-data:CommitTransaction",
          "rds-data:RollbackTransaction"
        ]
        Resource = var.aurora_cluster_arn
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.aurora_secret_arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "apprunner_sqs" {
  name = "${local.name_prefix}-apprunner-sqs"
  role = aws_iam_role.apprunner_instance.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage", "sqs:GetQueueAttributes"]
      Resource = data.terraform_remote_state.agents.outputs.sqs_queue_arn
    }]
  })
}

resource "aws_iam_role_policy" "apprunner_invoke" {
  name = "${local.name_prefix}-apprunner-invoke"
  role = aws_iam_role.apprunner_instance.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:counsel-planner"
    }]
  })
}

resource "aws_apprunner_service" "api" {
  service_name = "${local.name_prefix}-api"
  tags         = local.common_tags

  source_configuration {
    auto_deployments_enabled = true
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access.arn
    }
    image_repository {
      image_identifier = "${aws_ecr_repository.api.repository_url}:latest"
      image_configuration {
        port = "8000"
        runtime_environment_variables = merge(
          {
            AURORA_CLUSTER_ARN  = var.aurora_cluster_arn
            AURORA_SECRET_ARN   = var.aurora_secret_arn
            AURORA_DATABASE     = var.aurora_database_name
            AURORA_CLUSTER_HOST = var.aurora_cluster_endpoint
            DATABASE_URL        = local.database_url
            DEFAULT_AWS_REGION  = var.aws_region
            SQS_QUEUE_URL       = data.terraform_remote_state.agents.outputs.sqs_queue_url
            CLERK_JWKS_URL      = var.clerk_jwks_url
            CLERK_ISSUER        = var.clerk_issuer
            CORS_ORIGINS        = local.cors_env
            CHAT_OPENAI_MODEL   = "gpt-4o"
          },
          var.openai_api_key != "" ? { OPENAI_API_KEY = var.openai_api_key } : {}
        )
      }
      image_repository_type = "ECR"
    }
  }

  instance_configuration {
    instance_role_arn = aws_iam_role.apprunner_instance.arn
    cpu               = "1 vCPU"
    memory            = "2 GB"
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 20
    timeout             = 10
    healthy_threshold   = 1
    unhealthy_threshold = 3
  }

  network_configuration {
    ingress_configuration {
      is_publicly_accessible = true
    }
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.api.arn
    }
  }

  depends_on = [
    aws_iam_role_policy.apprunner_aurora,
    aws_iam_role_policy.apprunner_sqs,
    aws_iam_role_policy.apprunner_invoke,
  ]
}
