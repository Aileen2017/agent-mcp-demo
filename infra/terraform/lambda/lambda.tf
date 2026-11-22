# All three functions run the same zip package (see lambda/run.sh and lambda/lambda_handlers.py).
# ASGI_APP picks the app for each function. Each function gets a Function URL.
#
# Function URLs are the only network entry point. The MCP URLs are IAM-only, so just the
# agent role can reach them. The agent URL is public, guarded by X-API-Key, as on ECS.

resource "aws_lambda_function" "flights" {
  function_name = "${local.name_prefix}-flights-mcp"
  description   = "Mock flight search and booking MCP server."
  role          = aws_iam_role.mcp.arn
  package_type  = "Zip"
  runtime       = "python3.13"
  handler       = "run.sh"
  s3_bucket     = data.aws_s3_bucket.artifacts.id
  s3_key        = "mcp-demo-lambda.zip"

  architectures = ["x86_64"]
  layers        = [local.web_adapter_layer_arn]
  memory_size   = var.mcp_memory_mb
  timeout       = var.mcp_timeout_seconds

  environment {
    variables = merge(local.lambda_base_env, {
      ASGI_APP = "lambda_handlers:flights_app"
    })
  }

  depends_on = [aws_iam_role_policy_attachment.mcp_logs, aws_cloudwatch_log_group.flights]
}

resource "aws_lambda_function" "calendar" {
  function_name = "${local.name_prefix}-calendar-mcp"
  description   = "Mock personal calendar MCP server."
  role          = aws_iam_role.mcp.arn
  package_type  = "Zip"
  runtime       = "python3.13"
  handler       = "run.sh"
  s3_bucket     = data.aws_s3_bucket.artifacts.id
  s3_key        = "mcp-demo-lambda.zip"

  architectures = ["x86_64"]
  layers        = [local.web_adapter_layer_arn]
  memory_size   = var.mcp_memory_mb
  timeout       = var.mcp_timeout_seconds

  environment {
    variables = merge(local.lambda_base_env, {
      ASGI_APP = "lambda_handlers:calendar_app"
    })
  }

  depends_on = [aws_iam_role_policy_attachment.mcp_logs, aws_cloudwatch_log_group.calendar]
}

resource "aws_lambda_function" "agent" {
  function_name = "${local.name_prefix}-travel-agent"
  description   = "Holiday-planning agent API (LangGraph over the flight and calendar MCP servers)."
  role          = aws_iam_role.agent.arn
  package_type  = "Zip"
  runtime       = "python3.13"
  handler       = "run.sh"
  s3_bucket     = data.aws_s3_bucket.artifacts.id
  s3_key        = "mcp-demo-lambda.zip"
  architectures = ["x86_64"]
  layers        = [local.web_adapter_layer_arn]
  memory_size   = var.agent_memory_mb
  timeout       = var.agent_timeout_seconds

  environment {
    variables = merge(local.lambda_base_env, {
      ASGI_APP = "lambda_handlers:agent_app"

      # Lambda Web Adapter streams the /chat/stream server-sent events back to the caller.
      AWS_LWA_INVOKE_MODE = "response_stream"

      AGENT_MODEL           = var.agent_model
      BEDROCK_MODEL_ID      = var.bedrock_model_id
      AGENT_ALLOWED_ORIGINS = var.allowed_origins
      AGENT_API_KEY         = aws_secretsmanager_secret_version.agent_api_key.secret_string

      # The MCP functions are IAM-authenticated Function URLs, so the agent signs each call.
      MCP_IAM_AUTH     = "true"
      FLIGHT_MCP_URL   = "${trimsuffix(aws_lambda_function_url.flights.function_url, "/")}/mcp"
      CALENDAR_MCP_URL = "${trimsuffix(aws_lambda_function_url.calendar.function_url, "/")}/mcp"
    })
  }

  depends_on = [
    aws_iam_role_policy_attachment.agent_logs,
    aws_iam_role_policy.agent_invoke_mcp,
    aws_cloudwatch_log_group.agent,
  ]
}

resource "aws_lambda_function_url" "flights" {
  function_name      = aws_lambda_function.flights.function_name
  authorization_type = "AWS_IAM"
}

resource "aws_lambda_function_url" "calendar" {
  function_name      = aws_lambda_function.calendar.function_name
  authorization_type = "AWS_IAM"
}

resource "aws_lambda_function_url" "agent" {
  function_name      = aws_lambda_function.agent.function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"
}

# Public access for the agent URL. The app itself rejects requests without a valid X-API-Key.
resource "aws_lambda_permission" "agent_public_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.agent.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}
