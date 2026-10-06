[CmdletBinding()]
param(
  [ValidateSet("development", "production")]
  [string]$Environment = "development",
  [string]$Region = "ap-south-1",
  [ValidateSet("mock", "bedrock")]
  [string]$ClassifierProvider = "mock",
  [ValidateSet("true", "false")]
  [string]$BedrockDisabled = "true",
  [ValidateSet("true", "false")]
  [string]$AllowDemoIdentity = "false",
  [string]$KnowledgeBaseId = "",
  [ValidateSet("true", "false")]
  [string]$NotificationsEnabled = "false",
  [ValidateSet("true", "false")]
  [string]$SesEnabled = "false",
  [string]$SesSenderEmail = ""
)

$ErrorActionPreference = "Stop"
$stackName = "kasamukti-$Environment"

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
  throw "AWS CLI v2 is required."
}
if (-not (Get-Command sam -ErrorAction SilentlyContinue)) {
  throw "AWS SAM CLI is required. Install it before deploying."
}
if ($Environment -eq "production" -and $BedrockDisabled -eq "false" -and [string]::IsNullOrWhiteSpace($KnowledgeBaseId)) {
  throw "Production Bedrock deployment requires -KnowledgeBaseId for the approved guidance Knowledge Base."
}
if ($SesEnabled -eq "true" -and [string]::IsNullOrWhiteSpace($SesSenderEmail)) {
  throw "SES email delivery requires -SesSenderEmail."
}

aws sts get-caller-identity --region $Region | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "AWS credentials are unavailable or expired. Reauthenticate before deployment."
}

sam validate --lint --template-file template.yaml
if ($LASTEXITCODE -ne 0) { throw "SAM template validation failed." }

sam build --template-file template.yaml
if ($LASTEXITCODE -ne 0) { throw "SAM build failed." }

$overrides = @(
  "EnvironmentName=$Environment",
  "WasteClassifierProvider=$ClassifierProvider",
  "BedrockDisabled=$BedrockDisabled",
  "AllowDemoIdentity=$AllowDemoIdentity",
  "KnowledgeBaseId=$KnowledgeBaseId",
  "NotificationsEnabled=$NotificationsEnabled",
  "SesEnabled=$SesEnabled",
  "SesSenderEmail=$SesSenderEmail"
)

if (Test-Path .\samconfig.toml) {
  sam deploy `
    --template-file .aws-sam\build\template.yaml `
    --stack-name $stackName `
    --region $Region `
    --capabilities CAPABILITY_IAM `
    --resolve-s3 `
    --parameter-overrides $overrides `
    --no-confirm-changeset
} else {
  Write-Output "No samconfig.toml found; starting guided deployment."
  sam deploy `
    --guided `
    --template-file .aws-sam\build\template.yaml `
    --stack-name $stackName `
    --region $Region `
    --capabilities CAPABILITY_IAM `
    --resolve-s3 `
    --parameter-overrides $overrides
}

if ($LASTEXITCODE -ne 0) { throw "SAM deployment failed." }
aws cloudformation describe-stacks --stack-name $stackName --region $Region --query "Stacks[0].Outputs" --output table
