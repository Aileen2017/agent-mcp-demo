data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # One ECR repository holds the image that all three functions run.
  ecr_repo_name = "${var.project}-lambda-${var.environment}"
  image_uri     = "${aws_ecr_repository.lambda.repository_url}:${var.image_tag}"

  name_prefix = "${var.project}-${var.environment}"
}
