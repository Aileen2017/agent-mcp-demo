resource "aws_cloudwatch_log_group" "flights" {
  name              = "/ecs/${var.project}-${var.environment}/flights"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "calendar" {
  name              = "/ecs/${var.project}-${var.environment}/calendar"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "agent" {
  name              = "/ecs/${var.project}-${var.environment}/agent"
  retention_in_days = 14
}
