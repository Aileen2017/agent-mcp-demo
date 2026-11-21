# Build the shared Lambda image and push it to the ECR repository created by infra/lambda.
#
# First-time setup (the functions need the image, so create the repository first):
#   cd infra/lambda
#   terraform init -backend-config="key=mcp-demo-lambda/dev/terraform.tfstate"
#   terraform apply -target=aws_ecr_repository.lambda -var-file=env/dev.tfvars
#   ..\..\scripts\push_lambda_image.ps1 -Environment dev
#   terraform apply -var-file=env/dev.tfvars -var image_tag=<tag printed above>
#
# Use a new tag for each deploy. Lambda caches the image digest, so re-pushing the same
# tag does not update the functions.
param(
    [string]$Environment = "dev",
    [string]$Tag = "",
    [string]$Region = "eu-west-2",
    [string]$Project = "mcp-demo"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $Tag) {
    $Tag = (git -C $repoRoot rev-parse --short HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Tag) { throw "Pass -Tag, or run from a git checkout." }
}

$account = (aws sts get-caller-identity --query Account --output text).Trim()
if ($LASTEXITCODE -ne 0) { throw "aws sts get-caller-identity failed. Check your AWS credentials." }

$repo = "$Project-lambda-$Environment"
$registry = "$account.dkr.ecr.$Region.amazonaws.com"
$image = "$registry/${repo}:$Tag"

aws ecr describe-repositories --repository-names $repo --region $Region *> $null
if ($LASTEXITCODE -ne 0) {
    throw "ECR repository $repo does not exist yet. Run: terraform apply -target=aws_ecr_repository.lambda in infra/lambda."
}

aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $registry
if ($LASTEXITCODE -ne 0) { throw "docker login to $registry failed." }

Push-Location $repoRoot
try {
    # Lambda runs x86_64 (see infra/lambda/lambda.tf), so build that platform even on ARM hosts.
    docker build --platform linux/amd64 -f lambda/Dockerfile -t $image .
    if ($LASTEXITCODE -ne 0) { throw "docker build failed." }

    docker push $image
    if ($LASTEXITCODE -ne 0) { throw "docker push failed." }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Pushed $image"
Write-Host "Deploy with: terraform -chdir=infra/lambda apply -var-file=env/$Environment.tfvars -var image_tag=$Tag"
