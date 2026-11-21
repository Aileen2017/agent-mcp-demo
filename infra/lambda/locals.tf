data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # Zip built by scripts/build_lambda_zip.py. Path is relative to this module.
  lambda_zip_path = "${path.module}/../../build/lambda/mcp-demo-lambda.zip"

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
}
