# KasaMukti API

The production API is served by API Gateway and Lambda at `/api/v1`. Every
protected request must include a Cognito JWT:

```http
Authorization: Bearer <id-token>
Content-Type: application/json
```

Successful responses use:

```json
{"success": true, "data": {}, "requestId": "gateway-request-id"}
```

Errors use:

```json
{"success": false, "error": {"code": "FORBIDDEN", "message": "..."}, "requestId": "..."}
```

## Role authorization

| Role | Scope |
|---|---|
| `CITIZEN` | Analyze waste, submit collection events, view own profile, chat |
| `FARMER` | Citizen scope plus agricultural and special waste workflows |
| `MUNICIPAL_WORKER` | Verify deposits, manage batches, inventory, recovery operations |
| `MUNICIPAL_OFFICER` | Municipal analytics, Copilot tools, projects, partner administration |
| `RECOVERY_PARTNER` | Matching, recovery requests, pickup and recovery status for owned requests |
| `ADMIN` | All approved platform operations |

API Gateway authenticates the JWT. Lambda independently validates the Cognito
subject and group claim before every operation.

## Core endpoints

### `POST /api/v1/waste/analyze`

Roles: `CITIZEN`, `FARMER`, `ADMIN`.

Request:

```json
{"imageData":"data:image/jpeg;base64,...","description":"optional description","ocrText":"optional OCR"}
```

The Lambda stores the image in private S3, calls the configured Bedrock vision
provider, applies deterministic risk rules, and persists a `PENDING` scan in
DynamoDB. Image upload never awards GreenPoints.

Response data includes `scan`, `category`, `materialType`, `hazardLevel`,
`confidence`, `recommendedPathway`, `requiresManualVerification`, and verified
disposal guidance.

### `POST /api/v1/collections/events`

Roles: authenticated citizen/farmer creates a deposit event; only
`MUNICIPAL_WORKER`, `MUNICIPAL_OFFICER`, or `ADMIN` may verify it.

```json
{"scanId":"scan-id","collectionCenterId":"center-1","weightKg":2.5,"materialType":"PET"}
```

### `GET /api/v1/material-bank`

Roles: `MUNICIPAL_WORKER`, `MUNICIPAL_OFFICER`, `RECOVERY_PARTNER`, `ADMIN`.

Query filters: `materialType`, `mrfId`, `ward`, `workflowStatus`,
`qualityStatus`, `contaminationStatus`.

### `POST /api/v1/batches`

Roles: `MUNICIPAL_WORKER`, `MUNICIPAL_OFFICER`, `ADMIN`.

```json
{"scanIds":["verified-scan-id"],"materialType":"PET","quantity":10,"qualityStatus":"PASSED"}
```

### `PATCH /api/v1/batches/{batchId}/status`

Roles: municipal worker/officer/admin.

```json
{"status":"READY_FOR_RECOVERY","reason":"Quality check passed","metadata":{}}
```

Every valid transition records actor, timestamp, previous status, new status,
reason, and metadata.

### `POST /api/v1/aggregation/opportunities`

Roles: municipal worker/officer/admin.

```json
{"sourceBatchIds":["batch-1","batch-2"],"quality":"PASSED","contamination":"LOW"}
```

Digital aggregation stores source batch IDs, MRFs, wards, material, weight,
quality, contamination, and `physicalConsolidation:false`.

### `GET /api/v1/matching`

Roles: municipal officer, recovery partner, admin.

Returns deterministic, ranked partner matches with transparent eligibility
reasons. Hazardous material is never routed to incompatible ordinary partners.

### `POST /api/v1/recovery/requests`

Roles: recovery partner, municipal officer, admin.

```json
{"batchId":"batch-1","partnerId":"partner-1"}
```

### `PATCH /api/v1/recovery/{id}/status`

Roles: recovery partner for its own request, municipal roles, admin.

The batch lifecycle is:

```text
RESERVED -> PICKUP_SCHEDULED -> IN_TRANSIT -> RECEIVED ->
PROCESSING -> RECOVERED -> CLOSED
```

### `GET /api/v1/analytics/municipal`

Roles: municipal officer/admin.

Returns live DynamoDB-derived collection, material, hazard, recovery, partner,
participation, and GreenPoints metrics. It does not use demo seed data in live
mode.

### `POST /api/v1/copilot/query`

Roles: municipal officer/admin.

```json
{"message":"How much PET is currently available?","conversationId":"optional-id"}
```

The Copilot uses controlled read-only backend tools:

`getMaterialInventory`, `getWardStatistics`, `getHazardStatistics`,
`getRecoveryBatches`, `getRecoveryPartners`, `getRecoveryMatches`,
`getGreenPointStatistics`, `getCollectionTrends`, and `getRecoveryImpact`.

The model cannot directly query DynamoDB or mutate critical records.

### `POST /api/v1/chat`

Roles: citizen, farmer, municipal worker, municipal officer, recovery partner,
admin.

```json
{"message":"How should I dispose of this container?","conversationId":"optional-id"}
```

The response includes answer text, confidence, conversation ID, and source
metadata. Municipal operational context is only included for authorized roles.

### `POST /api/v1/greenpoints/award`

Roles: municipal worker/officer/admin.

GreenPoints are calculated server-side from a verified collection event.
Clients cannot provide an arbitrary points value or award themselves points.

### `GET /api/v1/impact`

Roles: municipal officer/admin.

Returns calculated impact metrics from verified DynamoDB records.

## Supporting endpoints

The same authenticated API also exposes:

```text
GET  /api/v1/profile
GET  /api/v1/centers
POST /api/v1/centers
GET  /api/v1/projects
POST /api/v1/projects
PATCH /api/v1/projects/{projectId}
POST /api/v1/projects/{projectId}/approval
POST /api/v1/projects/{projectId}/allocate
GET  /api/v1/campaigns
POST /api/v1/campaigns
GET  /api/v1/reports
GET  /api/v1/copilot/tools?name=<read-only-tool>
GET  /api/v1/qr/{token}
```

Campaign creation requires `MUNICIPAL_OFFICER` or `ADMIN` and persists a
campaign record in DynamoDB. Reports use the same live analytics calculation
path; they never read demo seed data in live mode.

The API is implemented by the Lambda in `backend/handler.py`. DynamoDB, S3,
Bedrock, SNS, and CloudWatch are accessed only by Lambda IAM permissions.
