# MCP servers: only need to write logs. Their Function URLs require IAM, so the agent
# must sign each call (agent/aws_auth.py).
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "mcp" {
  name_prefix        = "${local.name_prefix}-mcp-"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "mcp_logs" {
  role       = aws_iam_role.mcp.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Agent: writes logs, invokes the MCP functions, and calls Bedrock.
resource "aws_iam_role" "agent" {
  name_prefix        = "${local.name_prefix}-agent-"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "agent_logs" {
  role       = aws_iam_role.agent.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "agent_invoke_mcp" {
  statement {
    sid     = "InvokeMcpFunctionUrls"
    actions = ["lambda:InvokeFunctionUrl", "lambda:InvokeFunction"]
    resources = [
      aws_lambda_function.flights.arn,
      aws_lambda_function.calendar.arn,
    ]
  }
}

resource "aws_iam_role_policy" "agent_invoke_mcp" {
  name   = "invoke-mcp-functions"
  role   = aws_iam_role.agent.id
  policy = data.aws_iam_policy_document.agent_invoke_mcp.json
}

# Scoped to the configured inference profile. Cross-region profiles call the underlying
# foundation models in other regions, so those ARNs use a wildcard region.
data "aws_iam_policy_document" "agent_bedrock" {
  count = var.agent_model == "bedrock" ? 1 : 0

  statement {
    sid     = "InvokeModel"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:aws:bedrock:${var.aws_region}:${local.account_id}:inference-profile/${var.bedrock_model_id}",
      "arn:aws:bedrock:*::foundation-model/*",
    ]
  }
}

resource "aws_iam_role_policy" "agent_bedrock" {
  count = var.agent_model == "bedrock" ? 1 : 0

  name   = "invoke-bedrock"
  role   = aws_iam_role.agent.id
  policy = data.aws_iam_policy_document.agent_bedrock[0].json
}
