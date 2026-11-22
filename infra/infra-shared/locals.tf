locals {
  # dev and qa share one nonprod network and ECR repository; prod gets its own.
  environment2 = var.environment == "dev" || var.environment == "qa" ? "nonprod" : "prod"

}
