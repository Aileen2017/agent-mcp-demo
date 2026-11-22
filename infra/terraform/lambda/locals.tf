data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id



  # Lambda Web Adapter from AWS's public layer (account 753240598075). The layer runs the
  # app behind the handler and proxies Function URL requests to it. Layer version 24 is the
  # one the Lambda Web Adapter v0.9.1 README documents for x86_64.
  web_adapter_layer_arn = "arn:aws:lambda:${var.aws_region}:753240598075:layer:LambdaAdapterLayerX86:${var.web_adapter_layer_version}"

  # Shared by all three functions. ASGI_APP (set per function) picks the app.
  lambda_base_env = {
    AWS_LAMBDA_EXEC_WRAPPER      = "/opt/bootstrap"
    AWS_LWA_PORT                 = "8080"
    AWS_LWA_READINESS_CHECK_PATH = "/health"
    PYTHONUNBUFFERED             = "1"
    PYTHONDONTWRITEBYTECODE      = "1"
  }

  name_prefix = "${var.project}-${var.environment}"

  # Bucket created by infra/infra-shared: one per tier (dev and qa share nonprod).
  artifacts_environment = var.environment == "prod" ? "prod" : "nonprod"
  artifacts_bucket_name = "${var.project}-${local.artifacts_environment}-lambda-artifacts-${local.account_id}"

  # Per-environment key, so dev and qa zips in the shared bucket don't overwrite each other.
  lambda_object_key = "lambda/${var.environment}/mcp-demo-lambda.zip"
}
