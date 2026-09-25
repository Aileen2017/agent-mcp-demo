terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }

  # Separate state from infra/terraform, so destroying an app environment (dev, qa)
  # never touches the VPC and ECR repository they share.
  backend "s3" {
    bucket       = "mcp-demo-tfstate-730335559354"
    key          = "mcp-demo/infra-shared.tfstate"
    region       = "eu-west-2"
    encrypt      = true
    use_lockfile = true
  }
}
