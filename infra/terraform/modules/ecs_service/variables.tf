variable "name" {
  description = "Service name (also the Service Connect DNS name)."
  type        = string
}

variable "cluster_arn" {
  type = string
}

variable "container_image" {
  type = string
}

variable "container_port" {
  type = number
}

variable "command" {
  description = "Container command override, e.g. [\"python\", \"servers/flight_server.py\"]."
  type        = list(string)
}

variable "cpu" {
  type = number
}

variable "memory" {
  type = number
}

variable "desired_count" {
  type = number
}

variable "subnet_ids" {
  type = list(string)
}

variable "security_group_ids" {
  type = list(string)
}

variable "assign_public_ip" {
  type    = bool
  default = true
}

variable "execution_role_arn" {
  type = string
}

variable "task_role_arn" {
  description = "Optional task role ARN. Null when the task needs no AWS permissions."
  type        = string
  default     = null
}

variable "log_group_name" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "environment_variables" {
  description = "Plain (non-secret) environment variables."
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Secret env vars: name => Secrets Manager / SSM ARN."
  type        = map(string)
  default     = {}
}

variable "namespace_arn" {
  description = "Service Connect namespace ARN."
  type        = string
}

variable "publish" {
  description = "Whether this service publishes a Service Connect endpoint (MCP servers) or is client-only (agent)."
  type        = bool
  default     = false
}

variable "target_group_arn" {
  description = "Optional ALB target group to attach (agent only)."
  type        = string
  default     = null
}

variable "environment" {
  description = "Deployment environment (dev, qa, prod)."
  type        = string
}

