variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "eu-west-2"
}

variable "project" {
  description = "Short project name used for resource naming and tags."
  type        = string
  default     = "mcp-demo"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the public subnets (one per AZ)."
  type        = list(string)
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "image_tag" {
  description = "Container image tag to deploy. Build and push to ECR before apply."
  type        = string
  default     = "latest"
}

variable "agent_model" {
  description = "Model backend for the agent: bedrock or mock."
  type        = string
  default     = "bedrock"

  validation {
    condition     = contains(["bedrock", "mock"], var.agent_model)
    error_message = "agent_model must be either 'bedrock' or 'mock'."
  }
}

variable "bedrock_model_id" {
  description = "Bedrock model or inference-profile ID for the agent."
  type        = string
  default     = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "allowed_origins" {
  description = "Comma-separated CORS origins the agent API accepts."
  type        = string
  default     = "https://example.com"
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for the HTTPS listener. Empty string serves HTTP on port 80 (dev only)."
  type        = string
  default     = ""
}

variable "task_cpu" {
  description = "Fargate task CPU units (256, 512, 1024, ...)."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

variable "agent_desired_count" {
  description = "Number of agent API tasks."
  type        = number
  default     = 1
}

variable "mcp_desired_count" {
  description = "Number of tasks per MCP server."
  type        = number
  default     = 1
}
