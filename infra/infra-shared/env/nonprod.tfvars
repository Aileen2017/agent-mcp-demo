# Settings for the nonprod network and ECR repository that dev and qa share.
# Passed by the Infra workflow with -var-file=env/nonprod.tfvars.

environment = "nonprod"

vpc_cidr            = "10.0.0.0/16"
public_subnet_cidrs = ["10.0.0.0/24", "10.0.1.0/24"]
