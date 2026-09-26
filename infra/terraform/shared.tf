# The VPC, subnets and ECR repository live in infra/infra-shared, which must be applied
# first. They are looked up by the names that stack gives them.

data "aws_vpc" "main" {
  tags = { Name = "${var.project}-${local.environment2}-vpc" }
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.main.id]
  }

  tags = { Name = "${var.project}-${local.environment2}-public-*" }
}

data "aws_ecr_repository" "app" {
  name = "${var.project}-${local.environment2}"
}

locals {
  container_image = "${data.aws_ecr_repository.app.repository_url}:${var.image_tag}"
}

# These used to be managed here. Drop them from this stack's state without destroying
# them, so infra/infra-shared can import and own them.
removed {
  from = aws_ecr_repository.app
  lifecycle { destroy = false }
}

removed {
  from = aws_ecr_lifecycle_policy.app
  lifecycle { destroy = false }
}

removed {
  from = aws_vpc.main
  lifecycle { destroy = false }
}

removed {
  from = aws_internet_gateway.main
  lifecycle { destroy = false }
}

removed {
  from = aws_subnet.public
  lifecycle { destroy = false }
}

removed {
  from = aws_route_table.public
  lifecycle { destroy = false }
}

removed {
  from = aws_route_table_association.public
  lifecycle { destroy = false }
}
