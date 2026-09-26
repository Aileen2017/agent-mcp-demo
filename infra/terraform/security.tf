# Public entry point. Only the ALB is reachable from the internet.
resource "aws_security_group" "alb" {
  name_prefix = "${var.project}-${var.environment}-alb-"
  description = "ALB ingress from the internet."
  vpc_id      = data.aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-${var.environment}-alb-sg" }
}

# Agent API: only the ALB may reach port 8000.
resource "aws_security_group" "agent" {
  name_prefix = "${var.project}-${var.environment}-agent-"
  description = "Agent API tasks."
  vpc_id      = data.aws_vpc.main.id

  ingress {
    description     = "Agent API from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-${var.environment}-agent-sg" }
}

# MCP servers are private: only the agent may reach them. No internet ingress.
resource "aws_security_group" "mcp" {
  name_prefix = "${var.project}-${var.environment}-mcp-"
  description = "Flight and calendar MCP servers."
  vpc_id      = data.aws_vpc.main.id

  ingress {
    description     = "MCP ports from agent"
    from_port       = 3001
    to_port         = 3002
    protocol        = "tcp"
    security_groups = [aws_security_group.agent.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-${var.environment}-mcp-sg" }
}
