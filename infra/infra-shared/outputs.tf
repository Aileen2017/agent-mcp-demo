output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "artifacts_bucket" {
  description = "S3 bucket that holds the Lambda zip packages for dev and qa (or prod)."
  value       = aws_s3_bucket.artifacts.id
}

output "ecr_repository_url" {
  description = "Push the container image here before applying infra/terraform."
  value       = aws_ecr_repository.app.repository_url
}
