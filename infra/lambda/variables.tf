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
  description = "Deployment environment (dev, qa, prod)."
  type        = string
  default     = "dev"
}

variable "image_tag" {
  description = "Tag of the shared Lambda image in ECR. Push it with scripts/push_lambda_image.ps1 before apply."
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

variable "mcp_memory_mb" {
  description = "Memory for the flight and calendar MCP functions."
  type        = number
  default     = 512
}

variable "agent_memory_mb" {
  description = "Memory for the agent function. Lambda CPU scales with memory."
  type        = number
  default     = 1024
}

variable "mcp_timeout_seconds" {
  description = "Timeout for the MCP functions."
  type        = number
  default     = 30
}

variable "agent_timeout_seconds" {
  description = "Timeout for the agent function. Must exceed AGENT_REQUEST_TIMEOUT_SECONDS (120) plus cold start."
  type        = number
  default     = 180
}
