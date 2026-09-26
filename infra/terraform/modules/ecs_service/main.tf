resource "aws_ecs_task_definition" "this" {
  family                   = "${var.name}-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = var.name
      image     = var.container_image
      command   = var.command
      essential = true

      portMappings = [
        {
          name          = var.name
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [for k, v in var.environment_variables : { name = k, value = v }]
      secrets     = [for k, v in var.secrets : { name = k, valueFrom = v }]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.log_group_name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = var.name
        }
      }
    }
  ])
}

resource "aws_ecs_service" "this" {
  name            = "${var.name}-${var.environment}"
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = var.assign_public_ip
  }

  service_connect_configuration {
    enabled   = true
    namespace = var.namespace_arn

    dynamic "service" {
      for_each = var.publish ? [1] : []
      content {
        port_name      = var.name
        discovery_name = var.name

        client_alias {
          port     = var.container_port
          dns_name = var.name
        }
      }
    }
  }

  dynamic "load_balancer" {
    for_each = var.target_group_arn == null ? [] : [1]
    content {
      target_group_arn = var.target_group_arn
      container_name   = var.name
      container_port   = var.container_port
    }
  }

  health_check_grace_period_seconds = var.target_group_arn == null ? null : 60
}
