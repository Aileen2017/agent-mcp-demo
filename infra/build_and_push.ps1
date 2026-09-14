<#
.SYNOPSIS
    Builds the container image, pushes it to the project's ECR repository, and
    optionally forces the ECS services to redeploy with the new image.

.PARAMETER Tag
    Image tag to build and push. Defaults to "latest".

.PARAMETER Redeploy
    After pushing, force a new deployment of all three ECS services.

.EXAMPLE
    .\build_and_push.ps1
    .\build_and_push.ps1 -Tag v1 -Redeploy
#>
[CmdletBinding()]
param(
    [string] $Tag = "latest",
    [switch] $Redeploy
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$terraformDir = Join-Path $repoRoot 'infra\terraform'

Write-Host "  terraformDir : $terraformDir"
Write-Host "Reading ECR repository URL and region from Terraform..."

$ecr = terraform "-chdir=$terraformDir" output -raw ecr_repository_url
$ecr = "730335559354.dkr.ecr.eu-west-2.amazonaws.com"
$region = terraform "-chdir=$terraformDir" output -raw aws_region 2>$null
if (-not $region) { $region = 'eu-west-2' }
$cluster = terraform "-chdir=$terraformDir" output -raw cluster_name

Write-Host "  ECR repo : $ecr"
Write-Host "  Region   : $region"
Write-Host "  Cluster  : $cluster"
Write-Host "  repoRoot  : $repoRoot"

$registry = ($ecr -replace '/.*$', '')
$image = "mcp-demo-dev:${Tag}"

Write-Host "Logging Docker in to $registry..."
aws ecr get-login-password --region $region | docker login --username AWS --password-stdin $registry

Write-Host "Building $image (context: $repoRoot)..."
docker build -t $image $repoRoot

docker tag $image $registry/$image

Write-Host "Pushing $image..."
docker push $registry/$image

if ($Redeploy) {
    foreach ($service in 'flights', 'calendar', 'agent') {
        Write-Host "Forcing new deployment of $service..."
        aws ecs update-service --cluster $cluster --service $service `
            --force-new-deployment --region $region | Out-Null
    }
    Write-Host "Redeployment triggered for all services."
}

Write-Host "Done. Pushed $image"
