provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = local.environment2
      ManagedBy   = "terraform"
    }
  }
}
