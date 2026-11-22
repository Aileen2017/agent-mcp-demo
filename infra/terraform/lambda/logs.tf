resource "aws_cloudwatch_log_group" "flights" {
  name              = "/aws/lambda/${local.name_prefix}-flights-mcp"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "calendar" {
  name              = "/aws/lambda/${local.name_prefix}-calendar-mcp"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "agent" {
  name              = "/aws/lambda/${local.name_prefix}-travel-agent"
  retention_in_days = 30
}
