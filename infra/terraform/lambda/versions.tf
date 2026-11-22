terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # The key is supplied at init time so each environment has its own state, for example:
  #   terraform init -backend-config="key=mcp-demo-lambda/dev/terraform.tfstate"
  backend "s3" {
    bucket       = "mcp-demo-tfstate-730335559354"
    region       = "eu-west-2"
    encrypt      = true
    use_lockfile = true # S3-native state locking (Terraform 1.10+, no DynamoDB needed)
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Stack       = "lambda"
    }
  }
}
