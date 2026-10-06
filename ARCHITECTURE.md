# KasaMukti architecture and repository assessment

## Scope of this document

This document records the architecture that exists in the repository as of the
assessment date and compares it with the intended KasaMukti platform:

`Collect -> Identify -> Verify -> Reward -> Aggregate -> Match -> Recover -> Measure`

This is an assessment and implementation plan. The current phase intentionally
does not rewrite the application.

## Waste Intelligence boundary

Image classification is normalized through
[backend/ai/waste_intelligence.py](f:/KasaMukti/backend/ai/waste_intelligence.py).
The `WasteClassifier` protocol supports Bedrock today and an AWS computer-vision
or custom ML provider later. Provider output is untrusted until enum validation
and confidence calibration produce the `WasteAnalysis` contract. Unknown,
low-confidence, high-risk, and critical results require manual verification.
The API preserves the legacy `recoveryOptions` field for current clients while
exposing the canonical `recommendedPathway`.

### Deterministic safety boundary

`backend/ai/risk_engine.py` evaluates raw classifier evidence with ordered,
configurable `RiskRule` objects before a scan is persisted. Verified rules take
precedence over model confidence and can prohibit recycling, reuse, public
upcycling, or residual routing. The engine returns only risk, handling,
verification, and allowed/prohibited path metadata; disposal wording remains
owned by the configured human-approved guidance registry.

## 1. Current architecture summary

### Frontend

- Framework: React 18.3 with Vite 6 and JavaScript JSX.
- Styling: Tailwind CSS 3, custom CSS, glassmorphism styling.
- Interaction: Framer Motion 11.
- Icons: Lucide React.
- Transport: browser `fetch` calls to `VITE_API_BASE_URL`.
- State: local React state and `localStorage` for a generated demo identity.
- Build: `npm run build` produces a Vite `dist` bundle.
- The project is **not TypeScript** and is **not Next.js**.
- `VITE_DEMO_MODE=true` enables a clearly labelled local presentation controller
  with deterministic seeded records and a guided Collect → Identify → Verify →
  Recover → Measure journey. It does not change live API behavior when disabled.

Primary files:

- [frontend/src/App.jsx](f:/KasaMukti/frontend/src/App.jsx)
- [frontend/src/components/Scanner.jsx](f:/KasaMukti/frontend/src/components/Scanner.jsx)
- [frontend/src/main.jsx](f:/KasaMukti/frontend/src/main.jsx)
- [frontend/src/index.css](f:/KasaMukti/frontend/src/index.css)
- [frontend/package.json](f:/KasaMukti/frontend/package.json)

### Backend

- Runtime: one Python 3.12 Lambda entry point, `handler.lambda_handler`.
- API adapter and domain logic are currently colocated in [backend/handler.py](f:/KasaMukti/backend/handler.py).
- API Gateway is an AWS SAM `AWS::Serverless::HttpApi`.
- The Lambda performs input parsing, identity extraction, RBAC checks, Bedrock calls, DynamoDB operations, S3 writes, SNS alerts, and audit writes.
- The implementation is modular by operation/function name but is not yet split into domain services, repositories, or adapters.

### Database

- DynamoDB table: `KasaMuktiCore`.
- Billing: `PAY_PER_REQUEST`.
- Primary key: `PK` and `SK`, both strings.
- GSIs:
  - `MaterialTypeIndex` on `materialType` and `createdAt`.
  - `WorkflowIndex` is declared on `workflowStatus` and `createdAt`.
- The code currently uses broad table scans for many list/read operations rather than the declared indexes.
- Current logical entities include scans, wallets, collection events, material batches, recovery partners, collection centers, audits, and derived match objects.

### Authentication and authorization

- Cognito User Pool and User Pool Client are declared in [template.yaml](f:/KasaMukti/template.yaml).
- A Cognito JWT authorizer resource is also declared.
- The Lambda can read `requestContext.authorizer.jwt.claims` and Cognito groups.
- Protected `HttpApi` events now attach the `KasaMuktiApiAuthorizer`; the public QR lookup remains intentionally unauthenticated.
- An unauthenticated demo identity path is available when `ALLOW_DEMO_IDENTITY=true`, using `X-Demo-User` and `X-Demo-Role`.
- The frontend does not implement register, login, token refresh, logout, or Cognito Hosted UI flows.
- The frontend sends role and identity headers on every request; these are suitable only for an explicitly enabled demo environment.

### Existing AWS integrations

Declared and used:

- API Gateway HTTP API through SAM.
- AWS Lambda.
- DynamoDB.
- S3 private bucket with encryption and CORS.
- Amazon Bedrock Runtime for Claude vision/text calls.
- SNS for CRITICAL hazard notifications.
- Amazon Cognito resources and protected route authorizers are declared, but the frontend still needs a complete register/login/token-refresh UI.

Not currently implemented:

- CloudFront/static hosting deployment.
- SQS/EventBridge asynchronous processing.
- CloudWatch dashboards/alarms.
- Location services or a map provider for collection-center discovery.
- QR generation/scanning for citizen deposits.
- Secrets Manager or Parameter Store for managed configuration.

## 2. Existing UI components and workflows

### Existing UI

Reusable UI logic is currently defined inside [frontend/src/App.jsx](f:/KasaMukti/frontend/src/App.jsx), rather than in a component library or feature folders:

- `StatusPill`: live/offline/loading network indicator.
- `StatCard`: analytics metric card.
- `CitizenView`: GreenPoints, scans, profile impact, centers, scanner, and chat.
- `WorkerView`: pending verification and batch creation.
- `VerifyCard`: weight and center entry for verification.
- `OfficerView`: waste, hazard, inventory, and recovery-match metrics.
- `PartnerView`: partner profile and match acceptance.
- `Chat`: role-aware text assistant UI.

[frontend/src/components/Scanner.jsx](f:/KasaMukti/frontend/src/components/Scanner.jsx) is the only extracted feature component. It provides:

- Drag-and-drop upload.
- Mobile camera capture.
- Image preview.
- Animated scan line.
- Live `/analyze` request.
- Hazard badge and multilingual disposal guidance display.
- Browser speech synthesis for English instructions.

### Existing end-to-end workflow

The currently demonstrable path is:

1. Citizen/Farmer chooses a role in the client.
2. Citizen uploads an image.
3. `/analyze` stores media in S3 and calls Bedrock.
4. Backend persists a `PENDING` scan.
5. Worker enters a center ID and weight.
6. `/collection-events` conditionally verifies the scan and awards points.
7. Worker selects verified scans and creates a batch.
8. Officer can see analytics/inventory and configured recovery matches.
9. Recovery partner can register accepted materials and accept matches.
10. Citizen can ask the assistant a text question.

The workflow is real API-backed when an API endpoint and AWS resources are
configured; the frontend does not seed mock records.

## 3. Existing API routes

Routes declared in [template.yaml](f:/KasaMukti/template.yaml) and dispatched in [backend/handler.py](f:/KasaMukti/backend/handler.py):

| Method | Route | Current purpose |
|---|---|---|
| `POST` | `/analyze` | Store image, classify with Bedrock, persist `PENDING` scan, alert on CRITICAL |
| `POST` | `/verify` | Backwards-compatible direct verification path |
| `GET` | `/inventory` | Return scans, pending records, batches, and aggregate inventory |
| `POST` | `/collection-events` | Idempotent worker verification and GreenPoints award |
| `POST` | `/batches` | Aggregate verified scans into a material batch |
| `GET` | `/matches` | Derive eligible partner matches from available batches |
| `POST` | `/matches/{matchId}/accept` | Accept a recovery match |
| `PUT` | `/partners/me` | Create/update a recovery partner profile |
| `PATCH` | `/partners/{partnerId}/verification` | Officer/admin verification decision for a recovery partner |
| `GET` | `/centers` | List configured collection centers |
| `POST` | `/centers` | Create a center for officer/admin roles |
| `GET` | `/profile` | Return wallet, badges, impact, and leaderboard |
| `GET` | `/analytics` | Return municipal metrics |
| `POST` | `/chat` | Bedrock assistant with live inventory context and optional image analysis |

There is no explicit route yet for:

- User registration/login/token lifecycle.
- Citizen collection-event submission separate from worker verification.
- QR creation or QR scan.
- Badge definitions or reward history as first-class resources.
- Producer/recycler/upcycler onboarding and quality-rule management.
- Recovery status progression after a match is accepted.
- Ward-level analytics and campaign recommendations.
- Chat conversation persistence, feedback, moderation, or citations.

## 4. Existing environment variables

### Frontend

Declared in [frontend/.env.example](f:/KasaMukti/frontend/.env.example):

- `VITE_API_BASE_URL`: deployed API Gateway HTTP API base URL.
- `VITE_DEMO_MODE`: opt-in local hackathon presentation mode.
- `VITE_COGNITO_ID_TOKEN`: optional bearer token for Cognito-enabled demonstrations.

### Lambda

Configured in [template.yaml](f:/KasaMukti/template.yaml):

- `TABLE_NAME`
- `BUCKET_NAME`
- `TOPIC_ARN`
- `BEDROCK_MODEL_ID`
- `ALLOW_DEMO_IDENTITY`
- `POWERTOOLS_SERVICE_NAME`

AWS SDK credentials, region, and Cognito claims are expected from the Lambda
execution environment and are not checked into the repository. There is no
frontend Cognito configuration yet, such as user-pool ID, client ID, issuer,
redirect URI, or token storage policy.

## 5. Existing tests and validation

Current tests:

- [backend/test_handler.py](f:/KasaMukti/backend/test_handler.py)
  - Rejects non-image data URLs.
  - Verifies CRITICAL guidance comes from the trusted backend registry and is not requested from Bedrock.

Current validation already used:

- Python compilation with `py_compile`.
- Python `unittest`.
- Frontend production build with `npm run build`.
- Editor diagnostics for touched files.

Missing test coverage:

- Authorization/RBAC matrix.
- Cognito claims and invalid-role handling.
- Idempotent collection-event replay.
- Duplicate reward prevention under concurrent requests.
- Batch eligibility and hazardous/public-upcycling restrictions.
- Match acceptance authorization and state transitions.
- DynamoDB query/index behavior.
- API contract/integration tests.
- React component and accessibility tests.
- End-to-end citizen-to-recovery workflow.
- SAM/CloudFormation validation in CI.

## 6. Reusable components and code boundaries

Reusable application pieces currently exist as functions in `App.jsx`, but the
repository does not yet have reusable modules for:

- API client and typed request/response contracts.
- Authentication/session context.
- Role/permission guards.
- Toast, modal, table, form, empty-state, and error-boundary primitives.
- Scanner result model and status badge model.
- DynamoDB repository access.
- Audit logging abstraction.
- Bedrock prompt/response schemas.
- Verified knowledge repository.
- Recovery matching service.

The safest next refactor is extraction into feature modules without changing
the existing route contracts or the visual design.

## 7. Comparison with the target KasaMukti architecture

### Present

- Live AWS-backed image identification.
- S3 media storage.
- Bedrock vision/text integration.
- Human verification gate before points.
- DynamoDB persistence.
- SNS critical hazard alerting.
- Material batching.
- Basic recovery matching.
- Basic partner, center, analytics, and chatbot surfaces.
- Role names represented in the frontend and backend.
- Audit records for state-changing backend operations.
- Verified hazard guidance instead of LLM-authored hazardous instructions.

### Missing or incomplete

1. **Real authentication**
   - The client has no login/register flow yet; protected route authorizers are attached in SAM.
2. **Strict TypeScript architecture**
   - Frontend is JavaScript JSX; backend remains Python despite the preferred TypeScript direction.
3. **Domain separation**
   - One Lambda file owns transport, policy, persistence, AI, and notification responsibilities.
4. **Reliable data access**
   - Broad scans are used instead of targeted queries and pagination.
5. **Full municipal operations**
   - No QR workflow, ward analytics, collection-status management, campaign planning, or operational audit views.
6. **Recovery coordination**
   - Matches are derived transiently; match records and recovery lifecycle states are not persisted.
7. **Producer/recycler/upcycler management**
   - Partner profile is minimal and lacks verification, quality rules, capacity, geography, and compliance documents.
8. **Citizen participation**
   - No formal registration, collection-center navigation, leaderboard UX, reward history, or abuse review queue.
9. **AI governance**
   - No persisted prompt/version metadata, confidence review queue, model fallback, or human correction workflow.
10. **Operational production readiness**
    - No CI/CD, alarms, tracing, rate limiting, WAF policy, media-size limits, retention/lifecycle policy, or backup/restore plan.
11. **Frontend accessibility and maintainability**
    - Large JSX expressions, duplicated inline styles, no routing, no form schema validation, no shared API client, and no accessibility test suite.
12. **Chat architecture**
    - No durable conversations, verified knowledge citations, image upload path in the chat UI, voice interface abstraction, or prompt-injection controls beyond a system prompt.

## 8. Technical risks

### High priority

- **Authentication/session risk**: the frontend has not yet implemented Cognito registration, login, refresh, and logout; demo identity headers remain available only when explicitly enabled.
- **Reward consistency risk**: collection-event creation and scan verification are separate writes; partial failure can leave a collection record without a completed reward or vice versa.
- **Unbounded scan risk**: full-table scans will become slow and expensive as citizen, audit, batch, and inventory data grow.
- **Unsafe deployment drift**: `AllowDemoIdentity=true` would create a non-production identity boundary if used outside an isolated judge environment.
- **Hazard guidance governance**: the in-code registry is safer than LLM output but needs versioning, approval, locale coverage, and operational ownership.

### Medium priority

- **Single-Lambda blast radius**: a chat, Bedrock, or analytics failure can affect unrelated operations and deployments.
- **Bedrock latency/cost**: synchronous image and chat calls run inside a 30-second Lambda timeout.
- **Media abuse**: image size, content type, malware scanning, retention, and S3 object lifecycle are not fully enforced.
- **Match integrity**: derived matches are not persisted, so acceptance and state transitions are not durable.
- **Concurrency**: batch creation and partner acceptance need conditional state transitions to prevent double assignment.
- **Frontend identity**: `localStorage` generated IDs are not suitable for account ownership, privacy, or cross-device history.

### Lower priority

- **Observability gap**: no structured correlation ID, metric dimensions, dashboards, or alert thresholds are configured.
- **CloudFormation verification**: SAM CLI validation is not currently part of an automated pipeline.
- **Accessibility/regression gap**: no browser or component tests verify responsive and keyboard behavior.

## 9. Recommended implementation order

Do not implement the entire platform in one step. Use these increments:

### Phase 0: protect the baseline

- Keep the existing scanner, worker verification, batch, and analytics paths working.
- Add API contract fixtures and a local mocked AWS adapter only for tests, never for the production UI.
- Add SAM validation and frontend build to CI.
- Record current route payloads before changing them.

### Phase 1: authentication and API boundaries

- Implement the frontend Cognito registration/login/token-refresh/logout flow.
- Implement frontend sign-up, sign-in, logout, refresh, and role-aware session context.
- Remove `X-Demo-*` headers from production builds; keep the opt-in parameter isolated to judge deployments.
- Extract a small API client and shared error/loading contract.

### Phase 2: trusted collection and rewards

- Model collection events and reward ledger entries as durable records.
- Use idempotency and conditional writes in one transactional boundary where possible.
- Add QR creation/scanning and center selection.
- Add reward history, badge definitions, leaderboard pagination, and abuse review signals.

### Phase 3: domain modularization

- Split [backend/handler.py](f:/KasaMukti/backend/handler.py) into:
  - `api/` route adapters and validation.
  - `domain/` policies and state transitions.
  - `repositories/` DynamoDB/S3/SNS access.
  - `ai/` Bedrock prompts, schemas, and safety filters.
  - `knowledge/` versioned verified hazard guidance.
  - `observability/` audit, metrics, and correlation IDs.
- Keep HTTP payloads backward-compatible during extraction.

### Phase 4: recovery marketplace

- Persist match records and state transitions.
- Add partner onboarding, verification, accepted materials, quality requirements, capacity, geography, and recovery outcomes.
- Support producer, recycler, reuse partner, verified upcycler, specialized treatment, and residual pathways.
- Enforce no hazardous/public-upcycling routing at the domain layer.

### Phase 5: municipal intelligence

- Add ward/center dimensions to events and batches.
- Add officer dashboards for diversion, hazards, inventory aging, recovery outcomes, and campaign recommendations.
- Add Municipal Copilot with retrieved facts, citations, and human approval for recommendations.

### Phase 6: scale and operations

- Move long-running Bedrock/image jobs to SQS or Step Functions.
- Add CloudWatch metrics, alarms, traces, dashboards, retries, and dead-letter handling.
- Add S3 lifecycle, media limits, backups, data retention, privacy controls, and CI/CD deployment gates.

## 10. Files to create in future phases

These should be created incrementally, not all at once:

- `frontend/src/lib/apiClient.ts`
- `frontend/src/auth/AuthProvider.tsx`
- `frontend/src/auth/ProtectedRoute.tsx`
- `frontend/src/features/citizen/`
- `frontend/src/features/municipal/`
- `frontend/src/features/recovery/`
- `frontend/src/features/chat/`
- `frontend/src/components/ui/`
- `frontend/src/types/`
- `backend/api/`
- `backend/domain/`
- `backend/repositories/`
- `backend/ai/`
- `backend/knowledge/`
- `backend/observability/`
- `backend/tests/fixtures/`
- `.github/workflows/ci.yml`
- `samconfig.toml` (only when deployment configuration is intentionally committed)

## 11. Files to modify in future phases

- [template.yaml](f:/KasaMukti/template.yaml): route authorizers, least-privilege policies, parameters, indexes, alarms, and asynchronous resources.
- [backend/handler.py](f:/KasaMukti/backend/handler.py): only during controlled extraction or compatibility fixes.
- [backend/requirements.txt](f:/KasaMukti/backend/requirements.txt): only when a runtime dependency is actually introduced.
- [frontend/src/App.jsx](f:/KasaMukti/frontend/src/App.jsx): gradually replace the current role-switching shell with route/layout composition.
- [frontend/src/components/Scanner.jsx](f:/KasaMukti/frontend/src/components/Scanner.jsx): preserve the live scan contract while extracting API and result components.
- [backend/seed_demo.py](f:/KasaMukti/backend/seed_demo.py): additive fixed-key seed for a dedicated AWS hackathon demonstration table.
- [frontend/package.json](f:/KasaMukti/frontend/package.json): only for TypeScript, routing, auth, validation, and testing dependencies.
- [frontend/.env.example](f:/KasaMukti/frontend/.env.example): add Cognito/API configuration only when the auth flow is implemented.
- [README.md](f:/KasaMukti/README.md): update deployment and local development instructions with each completed phase.
- [ARCHITECTURE.md](f:/KasaMukti/ARCHITECTURE.md): update this assessment after each architectural phase.

## 12. Files that should not be unnecessarily changed

- [frontend/src/index.css](f:/KasaMukti/frontend/src/index.css): the current visual foundation is working; change only for an intentional design-system or accessibility fix.
- [frontend/src/main.jsx](f:/KasaMukti/frontend/src/main.jsx): keep the current React bootstrap unless adding a router/provider root.
- [frontend/src/components/Scanner.jsx](f:/KasaMukti/frontend/src/components/Scanner.jsx): do not rewrite the scanner while implementing unrelated municipal or partner features.
- [backend/requirements.txt](f:/KasaMukti/backend/requirements.txt): do not add libraries when standard library or existing dependencies suffice.
- Generated `frontend/dist/` and dependency directories such as `frontend/node_modules/` and `.venv/`: do not hand-edit or treat them as source architecture.

## Architectural decision

The repository is a credible AWS-backed hackathon MVP and should be evolved
incrementally. The next major change should be the authentication/API boundary,
not a wholesale frontend rewrite or a complete microservice split. Preserve the
working live scanner and human verification path while introducing stronger
identity, transactionality, query patterns, and test coverage around it.
