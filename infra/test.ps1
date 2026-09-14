
$repoRoot = Split-Path -Parent $PSScriptRoot
$terraformDir = Join-Path $repoRoot 'infra\terraform'

Write-Host "  terraformDir : $terraformDir"
Write-Host "Reading ECR repository URL and region from Terraform..."

$ecr = terraform "-chdir=$terraformDir" output -raw ecr_repository_url
$region = terraform "-chdir=$terraformDir" output -raw aws_region 2>$null
if (-not $region) { $region = 'eu-west-2' }
$cluster = terraform "-chdir=$terraformDir" output -raw cluster_name

Write-Host "  ECR repo : $ecr"
Write-Host "  Region   : $region"