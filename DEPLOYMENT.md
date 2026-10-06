# KasaMukti deployment guide

## Current deployment shape

This repository already has an AWS SAM application in [template.yaml](./template.yaml).
It deploys one Python 3.12 Lambda behind API Gateway HTTP API, DynamoDB, private
S3, SNS, Cognito JWT authorization, and least-privilege data-plane policies.
The current frontend is React/Vite, not Next.js. It can be hosted by Amplify
Hosting as a static Vite build; migrating to Next.js/TypeScript is a separate
application change and is intentionally not part of this deployment step.

Use separate CloudFormation stack names and `EnvironmentName` values for
`development` and `production`.

## Prerequisites

- AWS account and a region with the required services enabled.
- AWS CLI v2, SAM CLI, Node.js 18+, npm, and Python 3.12+.
- A deploy identity allowed to create/update CloudFormation, Lambda, API Gateway,
  DynamoDB, S3, Cognito, SNS, IAM roles, CloudWatch Logs, and (when enabled)
  Bedrock model invocation.
- Bedrock model access approved in the selected region before production use.
- Amplify Hosting access if deploying the frontend through Amplify.

Never put access keys, secret keys, Cognito secrets, or database credentials in
the frontend or in committed files. Prefer AWS IAM Identity Center or an assumed
deployment role.

## Environment variables

### SAM parameters

- `EnvironmentName`: `development` or `production`.
- `WasteClassifierProvider`: `mock` or `bedrock`.
- `BedrockDisabled`: `true` or `false`. Keep `true` until Bedrock access is verified.
- `AllowDemoIdentity`: only `true` for an isolated judge demo; keep `false` in production.
- `TableName`: optional custom DynamoDB table name.
- `KnowledgeBaseId`: optional Bedrock Knowledge Base ID containing reviewed guidance and policies.
- `NotificationsEnabled`: `true` to publish domain notification events to SNS.
- `SesEnabled`: `true` only after the SES sender identity is verified.
- `SesSenderEmail`: verified SES email/domain sender identity.

### Frontend

Copy [frontend/.env.example](./frontend/.env.example) for development or
[frontend/.env.production.example](./frontend/.env.production.example) for production.

- `VITE_API_BASE_URL`: API Gateway URL from the stack output.
- `VITE_DEMO_MODE`: `false` for deployed environments unless presenting local simulated data.
- `VITE_COGNITO_USER_POOL_ID`: Cognito User Pool ID (public identifier).
- `VITE_COGNITO_CLIENT_ID`: Cognito public app-client ID.
- `VITE_API_VERSIONED`: `true` (default) uses the `/api/v1` contract.
- `VITE_COGNITO_ID_TOKEN`: legacy temporary token forwarding option; do not commit it.

Vite variables are public build-time configuration. Do not place AWS credentials
or secrets in them.

## Local validation

```powershell
Set-Location .\frontend
npm ci
npm run build
Set-Location ..

& .\.venv\Scripts\python.exe -m unittest .\backend\test_handler.py
```

If SAM CLI is installed:

```powershell
sam validate --lint --template-file template.yaml
sam build --template-file template.yaml
```

## Deployment commands

The repository includes [scripts/deploy.ps1](./scripts/deploy.ps1). It refuses to
deploy until the AWS caller identity succeeds.

Development mock deployment:

```powershell
.\scripts\deploy.ps1 -Environment development -Region ap-south-1 -ClassifierProvider mock -BedrockDisabled true
```

Production Bedrock deployment with an approved Knowledge Base:

```powershell
.\scripts\deploy.ps1 -Environment production -Region ap-south-1 -ClassifierProvider bedrock -BedrockDisabled false -KnowledgeBaseId "KB_ID"
```

The script uses `sam deploy --guided` on the first run and stores deployment
configuration in the local ignored `samconfig.toml`. Review the generated change
set before accepting it.

## Database and S3 setup

DynamoDB is created by SAM with on-demand billing, encrypted server-side, and
the material/workflow indexes required by the application. Do not manually
create or delete the table. Use stack outputs and the Lambda environment values.

The S3 bucket is private, encrypted, and has restrictive public-access blocks.
The current application uploads through the trusted Lambda path. If direct
browser uploads are introduced later, add short-lived presigned PUT URLs with
content-type, size, key-prefix, and owner conditions; never make the bucket public.

## Cognito setup

The stack creates a user pool, app client, groups, and a post-confirmation
trigger that assigns newly confirmed users to `CITIZEN` by default:

`CITIZEN`, `FARMER`, `MUNICIPAL_WORKER`, `MUNICIPAL_OFFICER`,
`RECOVERY_PARTNER`, and `ADMIN`.

Create users through Cognito or the application auth flow, then add them to the
appropriate elevated group for municipal, farmer, partner, or admin access.
API Gateway validates the JWT audience and issuer. Lambda also enforces role
authorization from the `cognito:groups` claim. Example:

```powershell
aws cognito-idp admin-add-user-to-group `
  --user-pool-id <USER_POOL_ID> `
  --username user@example.com `
  --group-name MUNICIPAL_OFFICER `
  --region ap-south-1
```

## Bedrock and Knowledge Bases

Set `WasteClassifierProvider=bedrock` and `BedrockDisabled=false` only after
enabling the selected Claude model in the region. The Lambda role is restricted
to `bedrock:InvokeModel` on the configured Anthropic foundation-model ARN.

The Lambda retrieves approved contextual documents through
`bedrock-agent-runtime:Retrieve` when `KnowledgeBaseId` is configured. The
repository also contains deterministic verified guidance in
[backend/knowledge/guidance.py](./backend/knowledge/guidance.py). Provision the
Knowledge Base with an operator-owned corpus, embedding model, vector store,
and data-source lifecycle. Never use an unverified Knowledge Base as the
authority for hazardous disposal instructions.

## Notifications and Amazon SES

Notifications are generated by backend domain events, published to the
environment-specific SNS notification topic, and consumed by the dedicated
`NotificationWorker` Lambda. The worker writes a `NOTIFICATION` record to
DynamoDB before attempting email delivery:

```text
PENDING -> SENT
        -> FAILED
```

The worker resolves recipient email addresses from Cognito and sends through
Amazon SES. It never runs in the browser. Lambda errors are surfaced to the
SNS event source so transient delivery failures are retried by AWS; failed
records retain a truncated failure reason for operations.

Before enabling SES:

1. Verify the sender email address or domain in the same AWS region.
2. If the account is in the SES sandbox, verify every recipient address too.
3. Request production access before sending to unverified recipients.
4. Set `SesSenderEmail` to the verified identity.
5. Deploy with `NotificationsEnabled=true` and `SesEnabled=true`.

For safe demo mode, leave both flags `false`. Domain events are then not
published and no email is sent. Never place SES credentials in frontend
environment variables; the worker uses its IAM execution role.

Example production deployment:

```powershell
.\scripts\deploy.ps1 -Environment production -ClassifierProvider bedrock `
  -BedrockDisabled false -KnowledgeBaseId KB_ID `
  -NotificationsEnabled true -SesEnabled true `
  -SesSenderEmail notifications@example.org
```

## Amplify Hosting

Connect the repository to Amplify Hosting, select the frontend application
directory, and configure:

```text
Build command: npm ci && npm run build
Output directory: dist
```

Set `VITE_API_BASE_URL`, `VITE_DEMO_MODE=false`, `VITE_COGNITO_USER_POOL_ID`,
and `VITE_COGNITO_CLIENT_ID` as Amplify environment variables. The repository
root [amplify.yml](./amplify.yml) builds the Vite frontend from `frontend/`.
These are public identifiers; do not add AWS credentials or private secrets.

## Verification checklist

- [ ] `aws sts get-caller-identity` succeeds with the intended role.
- [ ] `sam validate --lint` succeeds.
- [ ] CloudFormation stack reaches `CREATE_COMPLETE` or `UPDATE_COMPLETE`.
- [ ] API Gateway output responds to unauthenticated protected-route requests with 401.
- [ ] Cognito login produces a JWT with the correct group claim.
- [ ] Authenticated citizen requests reach `/profile`, `/centers`, and `/analyze`.
- [ ] Invalid and duplicate image submissions are rejected safely.
- [ ] Worker verification awards points only after physical-deposit verification.
- [ ] Material batches persist in DynamoDB.
- [ ] Officer analytics and chatbot routes work.
- [ ] Bedrock calls work only when explicitly enabled.
- [ ] CloudWatch logs show no secrets or image contents.
- [ ] Amplify frontend loads with the deployed API URL.

## Troubleshooting

- **Expired AWS session:** reauthenticate with IAM Identity Center or the
  organization-approved credential mechanism, then rerun `aws sts get-caller-identity`.
- **SAM transform failure:** run `sam validate --lint`; inspect duplicate YAML
  keys and generated `.aws-sam/build/template.yaml`.
- **401 from API:** verify the bearer token issuer, audience, region, and group claim.
- **Bedrock access denied:** enable the model in the same region and confirm the
  Lambda execution role policy and model ID.
- **Mock mode unavailable:** deploy with `WasteClassifierProvider=mock` and
  `BedrockDisabled=true`; the rest of the API remains testable.
- **CORS failure:** confirm the frontend URL and API Gateway CORS configuration.

## Cleanup

Review the stack before deletion. This is destructive to the stack-managed table,
bucket, user pool, and topic:

```powershell
aws cloudformation delete-stack --stack-name kasamukti-development --region ap-south-1
aws cloudformation wait stack-delete-complete --stack-name kasamukti-development --region ap-south-1
```

Production cleanup requires explicit approval. S3 versioning/retention policies
and backups should be configured before any production deletion policy is changed.
