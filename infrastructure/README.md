# Infrastructure

KasaMukti uses AWS SAM as its infrastructure-as-code framework. The canonical
template is [../template.yaml](../template.yaml); it creates the HTTP API,
Cognito/JWT authorization, Lambda, DynamoDB, private S3 bucket, SNS alerts,
CloudWatch Lambda logs, IAM policies, and deployment outputs. The repository
root [../amplify.yml](../amplify.yml) configures Amplify Hosting for the
existing Vite frontend; SAM remains the source of truth for the backend data
plane.

The template also creates an SNS notification topic and a dedicated
`NotificationWorker` Lambda. Enable SES only with a verified sender identity;
keep `NotificationsEnabled=false` and `SesEnabled=false` for local/demo
deployments.

Use `..\scripts\deploy.ps1` for environment-aware deployment. Use different
CloudFormation stacks for `development` and `production`.

The default deployment uses the deterministic mock provider so the API can be
smoke-tested without Bedrock model access. Enable Bedrock and an approved
Knowledge Base explicitly with:

```powershell
.\scripts\deploy.ps1 -Environment production -ClassifierProvider bedrock -BedrockDisabled false -KnowledgeBaseId <KB_ID>
```
