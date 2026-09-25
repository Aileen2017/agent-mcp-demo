resource "aws_service_discovery_http_namespace" "main" {
  name        = "${var.project}-${var.environment}"
  description = "Service Connect namespace for the MCP demo."
}

resource "aws_ecs_cluster" "main" {
  name = "${var.project}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  service_connect_defaults {
    namespace = aws_service_discovery_http_namespace.main.arn
  }
}
