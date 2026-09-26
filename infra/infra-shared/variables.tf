variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "eu-west-2"
}

variable "project" {
  description = "Short project name used for resource naming and tags; must match infra/terraform."
  type        = string
  default     = "mcp-demo"
}

variable "environment" {
  description = "Tier to build: nonprod (shared by dev and qa) or prod."
  type        = string
  default     = "nonprod"
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
