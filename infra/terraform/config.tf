locals {
  account_id   = data.aws_caller_identity.current.account_id
  environment2 = var.environment == "prod" ? "prod" : "nonprod"
  # Prefix of every IAM role infra/terraform creates (see infra/terraform/iam.tf).
  app_prefix    = "${var.project}-${local.environment2}"
  app_roles_arn = "arn:aws:iam::${local.account_id}:role/${local.app_prefix}-*"
  ecr_repo_arn  = "arn:aws:ecr:${var.aws_region}:${local.account_id}:repository/${local.app_prefix}"
}