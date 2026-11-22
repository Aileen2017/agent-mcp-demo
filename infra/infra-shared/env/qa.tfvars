# Settings for the qa environment. Passed by the Infra workflows with -var-file=env/qa.tfvars.
# Committed, so never put secrets here. image_tag comes from the workflow input.

environment2 = "nonprod"

vpc_cidr            = "10.0.0.0/16"
public_subnet_cidrs = ["10.0.0.0/24", "10.0.1.0/24"]
