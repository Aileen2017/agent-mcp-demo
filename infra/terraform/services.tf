module "flights" {
  source = "./modules/ecs_service"

  name               = "flights-mcp"
  cluster_arn        = aws_ecs_cluster.main.arn
  container_image    = local.container_image
  container_port     = 3001
  command            = ["python", "servers/flight_server.py"]
  cpu                = var.task_cpu
  memory             = var.task_memory
  desired_count      = var.mcp_desired_count
  subnet_ids         = aws_subnet.public[*].id
  security_group_ids = [aws_security_group.mcp.id]
  execution_role_arn = aws_iam_role.execution.arn
  log_group_name     = aws_cloudwatch_log_group.flights.name
  aws_region         = var.aws_region
  namespace_arn      = aws_service_discovery_http_namespace.main.arn
  publish            = true

  environment_variables = {
    MCP_HOST = "0.0.0.0"
  }
}

module "calendar" {
  source = "./modules/ecs_service"

  name               = "calendar-mcp"
  cluster_arn        = aws_ecs_cluster.main.arn
  container_image    = local.container_image
  container_port     = 3002
  command            = ["python", "servers/calendar_server.py"]
  cpu                = var.task_cpu
  memory             = var.task_memory
  desired_count      = var.mcp_desired_count
  subnet_ids         = aws_subnet.public[*].id
  security_group_ids = [aws_security_group.mcp.id]
  execution_role_arn = aws_iam_role.execution.arn
  log_group_name     = aws_cloudwatch_log_group.calendar.name
  aws_region         = var.aws_region
  namespace_arn      = aws_service_discovery_http_namespace.main.arn
  publish            = true

  environment_variables = {
    MCP_HOST = "0.0.0.0"
  }
}

module "agent" {
  source = "./modules/ecs_service"

  name               = "travel-agent"
  cluster_arn        = aws_ecs_cluster.main.arn
  container_image    = local.container_image
  container_port     = 8000
  command            = ["python", "-m", "agent.api"]
  cpu                = var.task_cpu
  memory             = var.task_memory
  desired_count      = var.agent_desired_count
  subnet_ids         = aws_subnet.public[*].id
  security_group_ids = [aws_security_group.agent.id]
  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.agent_task.arn
  log_group_name     = aws_cloudwatch_log_group.agent.name
  aws_region         = var.aws_region
  namespace_arn      = aws_service_discovery_http_namespace.main.arn
  target_group_arn   = aws_lb_target_group.agent.arn

  environment_variables = {
    AGENT_API_HOST        = "0.0.0.0"
    AGENT_API_PORT        = "8000"
    AGENT_MODEL           = var.agent_model
    BEDROCK_MODEL_ID      = var.bedrock_model_id
    AWS_REGION            = var.aws_region
    FLIGHT_MCP_URL        = "http://flights-mcp:3001/mcp"
    CALENDAR_MCP_URL      = "http://calendar-mcp:3002/mcp"
    AGENT_ALLOWED_ORIGINS = var.allowed_origins
  }

  secrets = {
    AGENT_API_KEY = aws_secretsmanager_secret.agent_api_key.arn
  }

  # Listeners must exist before the service attaches to the target group.
  depends_on = [module.flights, module.calendar, aws_lb_listener.http, aws_lb_listener.https]
}
