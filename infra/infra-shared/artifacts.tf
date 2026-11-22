# S3 bucket for the Lambda zip packages, shared by dev and qa (one bucket per tier). Each
# environment uploads its zip under its own prefix, lambda/<environment>/, so the two never
# overwrite each other. Created here, before the infra job applies the lambda stack.

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "artifacts" {
  bucket        = "${var.project}-${var.environment}-lambda-artifacts-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.environment != "prod"
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
