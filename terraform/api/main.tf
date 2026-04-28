terraform {
  required_version = ">= 1.0"
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
data "aws_vpc" "default" {
  default = true
}
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

locals {
  name_prefix   = "counsel"
  sqs_queue_arn = trimspace(var.sqs_queue_arn) != "" ? trimspace(var.sqs_queue_arn) : "arn:aws:sqs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:counsel-agents"

  common_tags = {
    Project   = "counsel"
    Part      = "api"
    ManagedBy = "terraform"
  }
}

resource "aws_ecr_repository" "api" {
  name                 = "${local.name_prefix}-api"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }

  tags = local.common_tags
}

resource "aws_iam_role" "apprunner_ecr_access" {
  name = "${local.name_prefix}-apprunner-ecr-access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "build.apprunner.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr" {
  role       = aws_iam_role.apprunner_ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

resource "aws_iam_role" "apprunner_instance" {
  name = "${local.name_prefix}-apprunner-instance"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "tasks.apprunner.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
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
          "rds-db:connect"
        ]
        Resource = var.aurora_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
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
      Effect = "Allow"
      Action = [
        "sqs:SendMessage",
        "sqs:GetQueueUrl",
        "sqs:GetQueueAttributes"
      ]
      Resource = local.sqs_queue_arn
    }]
  })
}

resource "aws_iam_role_policy" "apprunner_invoke" {
  name = "${local.name_prefix}-apprunner-invoke"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sagemaker:InvokeEndpoint"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_security_group" "apprunner_vpc_connector" {
  name        = "${local.name_prefix}-apprunner-connector"
  description = "Security group for App Runner VPC connector"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_apprunner_vpc_connector" "api" {
  vpc_connector_name = "${local.name_prefix}-api-vpc"
  subnets            = data.aws_subnets.default.ids
  security_groups    = [aws_security_group.apprunner_vpc_connector.id]
  tags               = local.common_tags
}

resource "aws_apprunner_service" "api" {
  service_name = "${local.name_prefix}-api"

  source_configuration {
    auto_deployments_enabled = var.auto_deployments_enabled

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access.arn
    }

    image_repository {
      image_repository_type = "ECR"
      image_identifier      = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"

      image_configuration {
        port = "8000"
        runtime_environment_variables = {
          OPENAI_API_KEY      = var.openai_api_key
          CHAT_OPENAI_MODEL   = var.chat_openai_model
          DEFAULT_AWS_REGION  = var.aws_region
          AURORA_CLUSTER_HOST = var.aurora_cluster_endpoint
          AURORA_SECRET_ARN   = var.aurora_secret_arn
          AURORA_DATABASE     = var.aurora_database
          CLERK_JWKS_URL      = var.clerk_jwks_url
          CLERK_ISSUER        = var.clerk_issuer
          CORS_ORIGINS        = var.cors_origins
          SQS_QUEUE_URL       = var.sqs_queue_url
          SAGEMAKER_ENDPOINT  = var.sagemaker_endpoint
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.instance_cpu
    memory            = var.instance_memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.api.arn
    }
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    healthy_threshold   = 1
    unhealthy_threshold = 5
    interval            = 10
    timeout             = 5
  }

  tags = local.common_tags

  depends_on = [
    aws_iam_role_policy.apprunner_aurora,
    aws_iam_role_policy.apprunner_sqs,
    aws_iam_role_policy.apprunner_invoke
  ]
}
