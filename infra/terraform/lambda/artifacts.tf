# S3 bucket for the Lambda zip package. The zip is about 58 MB, over the 50 MB limit for a
# direct upload, so Lambda reads it from S3. Build it first with scripts/build_lambda_zip.py.

resource "aws_s3_bucket" "artifacts" {
  bucket        = "${local.name_prefix}-lambda-artifacts-${local.account_id}"
  force_destroy = var.environment != "prod"
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "lambda_package" {
  bucket = aws_s3_bucket.artifacts.id
  key    = "lambda/mcp-demo-lambda.zip"
  source = local.lambda_zip_path
  etag   = filemd5(local.lambda_zip_path)
}
