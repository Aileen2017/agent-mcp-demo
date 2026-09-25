terraform {
  required_version = ">= 1.7" # removed blocks

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

  backend "s3" {
    bucket       = "mcp-demo-tfstate-730335559354"
    key          = "mcp-demo/terraform.tfstate"
    region       = "eu-west-2"
    encrypt      = true
    use_lockfile = true # S3-native state locking (Terraform 1.10+, no DynamoDB needed)
  }

}
