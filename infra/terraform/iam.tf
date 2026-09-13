data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Shared execution role: pulls images, writes logs, reads the API-key secret.
resource "aws_iam_role" "execution" {
  name_prefix = "${var.project}-${var.environment}-exec-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "read-agent-api-key"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.agent_api_key.arn]
    }]
  })
}

# Task role for the agent only: permission to invoke the Bedrock model.
resource "aws_iam_role" "agent_task" {
  name_prefix = "${var.project}-${var.environment}-agent-task-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

# Cross-region inference profiles fan out to the model in several EU regions,
# so the policy covers both the profile and the underlying foundation models.
resource "aws_iam_role_policy" "agent_bedrock" {
  count = var.agent_model == "bedrock" ? 1 : 0

  name = "invoke-bedrock"
  role = aws_iam_role.agent_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ]
      Resource = [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-*",
        "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:inference-profile/eu.anthropic.claude-3-5-sonnet-*"
      ]
    }]
  })
}
