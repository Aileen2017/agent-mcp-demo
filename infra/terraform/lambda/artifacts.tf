# The Lambda zip is uploaded to the artifacts bucket that infra/infra-shared creates. The bucket
# is looked up by name here, so this stack needs no access to infra-shared's state.
# The zip is built by scripts/build_lambda_zip.py before this stack is planned.

data "aws_s3_bucket" "artifacts" {
  bucket = local.artifacts_bucket_name
}

# The Lambda zip, uploaded under this environment's key (see locals.tf).
# resource "aws_s3_object" "lambda_package" {
#  bucket = data.aws_s3_bucket.artifacts.id
#  key    = local.lambda_object_key
#  source = local.lambda_zip_path
#  etag   = filemd5(local.lambda_zip_path)
# }
