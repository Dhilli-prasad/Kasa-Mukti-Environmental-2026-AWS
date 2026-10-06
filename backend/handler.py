"""KasaMukti API adapter and domain operations.

The hackathon keeps these operations in one Lambda for simple deployment. Each
operation has an explicit boundary so it can be moved into separate modules or
functions without changing the HTTP contract.
"""

import base64
import binascii
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import boto3
from botocore.exceptions import ClientError

from ai.assistant import BedrockAssistantProvider, LocalAssistantProvider, answer as assistant_answer
from ai.waste_intelligence import (
    BedrockWasteClassifier,
    MockWasteClassifier,
    WasteAnalysis,
    normalize_analysis,
)
from ai.risk_engine import WasteRiskEngine
from green_points import (
    action_for_verified_deposit,
    badges_for,
    calculate_points,
    configured_reward_rules,
    leaderboard as calculate_leaderboard,
)
from recovery_matching import match_batch
from public_upcycling import PROJECT_STATUSES, project_requirements_eligibility, public_material_eligibility
from knowledge.guidance import HAZARD_GUIDANCE, verified_guidance
from recovery_workflow import RECOVERY_STATUSES, validate_transition, completion_metrics
from ai.copilot_tools import run_tool
from notification_events import publish_notification

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime")
sns = boto3.client("sns")

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")
ALLOWED_ROLES = {
    "CITIZEN",
    "FARMER",
    "MUNICIPAL_WORKER",
    "MUNICIPAL_OFFICER",
    "RECOVERY_PARTNER",
    "ADMIN",
}
HAZARDOUS_MATERIALS = {"HAZARDOUS", "E_WASTE"}
BATCH_STATUSES = {
    "COLLECTING", "AGGREGATING", "QUALITY_CHECK", "READY_FOR_RECOVERY",
    "PARTNER_REQUESTED", "PICKUP_SCHEDULED", "RECOVERED", "REJECTED",
    *RECOVERY_STATUSES,
}
def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def response(status_code: int, payload: dict[str, Any], request_id: str | None = None, versioned: bool = False) -> dict[str, Any]:
    request_id = request_id or str(uuid.uuid4())
    body = (
        {"success": True, "data": payload, "requestId": request_id}
        if versioned
        else payload
    )
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Demo-Role,X-Demo-User",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,PUT,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


def error_response(status_code: int, code: str, message: str, request_id: str, versioned: bool) -> dict[str, Any]:
    if versioned:
        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Demo-Role,X-Demo-User",
                "Access-Control-Allow-Methods": "GET,POST,PATCH,PUT,OPTIONS",
            },
            "body": json.dumps({"success": False, "error": {"code": code, "message": message}, "requestId": request_id}),
        }
    return response(status_code, {"error": message}, request_id=request_id)


def require_fields(body: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if body.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def parse_body(event: dict[str, Any]) -> dict[str, Any]:
    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")
    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Request body must be valid JSON") from exc
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    return body


def identity(event: dict[str, Any], body: dict[str, Any] | None = None) -> tuple[str, str]:
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    user_id = str(claims.get("sub") or "").strip()
    groups = claims.get("cognito:groups", "")
    role = str(groups[0] if isinstance(groups, list) and groups else groups).upper()
    if not user_id and os.environ.get("ALLOW_DEMO_IDENTITY", "false").lower() == "true":
        headers = {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}
        user_id = headers.get("x-demo-user") or str((body or {}).get("citizenId") or "").strip()
        role = headers.get("x-demo-role", role or "CITIZEN").upper()
    if not user_id:
        raise PermissionError("Authentication is required")
    if role not in ALLOWED_ROLES:
        raise PermissionError("A valid KasaMukti role is required")
    return user_id, role


def require_role(role: str, *allowed: str) -> None:
    if role != "ADMIN" and role not in allowed:
        raise PermissionError("This operation is not available for the current role")


def audit(actor: str, role: str, operation: str, entity_id: str, outcome: str) -> None:
    table.put_item(
        Item={
            "PK": f"AUDIT#{entity_id}",
            "SK": f"{now()}#{uuid.uuid4()}",
            "entityType": "AUDIT",
            "actorId": actor,
            "actorRole": role,
            "operation": operation,
            "outcome": outcome,
            "createdAt": now(),
        }
    )


def media_from_data_url(image_data: str) -> tuple[str, bytes]:
    if not image_data.startswith("data:image/") or ";base64," not in image_data:
        raise ValueError("imageData must be a base64 image data URL")
    metadata, encoded = image_data.split(";base64,", 1)
    media_type = metadata.removeprefix("data:image/")
    if media_type == "jpg":
        media_type = "jpeg"
    if media_type not in {"jpeg", "png", "webp", "gif"}:
        raise ValueError("Only JPEG, PNG, WEBP, and GIF images are supported")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("imageData contains invalid base64") from exc
    if not image_bytes:
        raise ValueError("imageData cannot be empty")
    return media_type, image_bytes


def bedrock_json(request: dict[str, Any]) -> dict[str, Any]:
    result = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(request),
    )
    raw = json.loads(result["body"].read())
    content = raw.get("content", [{}])[0].get("text", "").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Bedrock returned invalid JSON") from exc


def classify_image(media_type: str, image_bytes: bytes) -> dict[str, Any]:
    provider_name = os.environ.get("WASTE_CLASSIFIER_PROVIDER", "bedrock").lower()
    if provider_name == "mock":
        provider = MockWasteClassifier()
    elif provider_name == "bedrock":
        provider = BedrockWasteClassifier(bedrock, MODEL_ID)
    else:
        raise RuntimeError(f"Unsupported waste classifier provider: {provider_name}")
    provider_result = provider.classify(media_type=media_type, image_bytes=image_bytes)
    analysis: WasteAnalysis = normalize_analysis(provider_result)
    result = analysis.as_dict()
    result["riskAssessment"] = WasteRiskEngine().evaluate(provider_result)
    pathway_mapping = {
        "ORIGINAL_PRODUCER": "ORIGINAL_PRODUCER",
        "RECYCLER": "RECYCLER",
        "REUSE_PARTNER": "REUSE_PARTNER",
        "VERIFIED_UPCYCLER": "VERIFIED_UPCYCLER",
        "SPECIALIZED_TREATMENT": "SPECIALIZED_TREATMENT",
        "RESIDUAL": "RESIDUAL",
    }
    result["recoveryOptions"] = [pathway_mapping[analysis.recommendedPathway]]
    result["disposal_instructions"] = verified_guidance(analysis.hazardLevel)
    result["classifierProvider"] = provider.name
    return result


def analyze(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "CITIZEN", "FARMER", "ADMIN")
    image_data = body.get("imageData")
    if not isinstance(image_data, str):
        raise ValueError("imageData is required")
    media_type, image_bytes = media_from_data_url(image_data)
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    duplicate = table.get_item(
        Key={"PK": f"IMAGE#{actor}#{image_hash}", "SK": "DETAILS"}
    ).get("Item")
    if duplicate:
        return {"scan": get_scan(duplicate["scanId"]), "message": "This image was already submitted."}
    classification = classify_image(media_type, image_bytes)
    scan_id, created_at = str(uuid.uuid4()), now()
    media_key = f"scans/{scan_id}.{media_type}"
    s3.put_object(Bucket=os.environ["BUCKET_NAME"], Key=media_key, Body=image_bytes, ContentType=f"image/{media_type}", ServerSideEncryption="AES256")
    item = {
        "PK": f"SCAN#{scan_id}", "SK": "DETAILS", "entityType": "SCAN", "scanId": scan_id,
        "citizenId": actor, "status": "PENDING", "createdAt": created_at, "category": str(classification["category"]),
        "materialType": classification["materialType"], "hazardLevel": classification["hazardLevel"],
        "disposal_instructions": classification["disposal_instructions"], "mediaKey": media_key,
        "productName": classification.get("productName"), "manufacturer": classification.get("manufacturer"),
        "labelText": classification.get("labelText"), "confidence": Decimal(str(classification.get("confidence", 0))),
        "recoveryOptions": classification["recoveryOptions"], "riskAssessment": classification["riskAssessment"],
        "imageHash": image_hash,
        "workflowStatus": "PENDING_VERIFICATION",
    }
    try:
        table.put_item(
            Item={
                "PK": f"IMAGE#{actor}#{image_hash}",
                "SK": "DETAILS",
                "entityType": "IMAGE_SUBMISSION",
                "scanId": scan_id,
                "createdAt": created_at,
            },
            ConditionExpression="attribute_not_exists(PK)",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            duplicate = table.get_item(
                Key={"PK": f"IMAGE#{actor}#{image_hash}", "SK": "DETAILS"}
            ).get("Item")
            if duplicate:
                return {"scan": get_scan(duplicate["scanId"]), "message": "This image was already submitted."}
        raise
    table.put_item(Item=item)
    publish_notification("WASTE_SUBMISSION", user_id=actor, data={"scanId": scan_id})
    if item["hazardLevel"] in {"HIGH", "CRITICAL"}:
        sns.publish(TopicArn=os.environ["TOPIC_ARN"], Subject=f"KasaMukti critical hazard: {scan_id}", Message=json.dumps({"scanId": scan_id, "actor": actor, "category": item["category"], "materialType": item["materialType"]}))
        publish_notification("HAZARDOUS_WASTE_ALERT", roles=["MUNICIPAL_OFFICER", "ADMIN"], data={"scanId": scan_id})
    audit(actor, role, "ANALYZE", scan_id, "PENDING")
    return {"scan": item, "message": "Scan recorded. A human deposit verification is required before rewards or routing."}


def get_scan(scan_id: str) -> dict[str, Any]:
    item = table.get_item(Key={"PK": f"SCAN#{scan_id}", "SK": "DETAILS"}).get("Item")
    if not item:
        raise ValueError("Scan not found")
    return item


def record_green_point_transaction(
    *,
    user_id: str,
    action: str,
    points: int,
    reference_id: str,
    verified_by: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist an idempotent transaction and update the user's balance."""
    transaction_id = f"{user_id}#{reference_id}"
    existing = table.get_item(
        Key={"PK": f"GREENPOINT_TX#{transaction_id}", "SK": "DETAILS"}
    ).get("Item")
    if existing:
        return existing
    created_at = now()
    transaction = {
        "PK": f"GREENPOINT_TX#{transaction_id}",
        "SK": "DETAILS",
        "entityType": "GREENPOINT_TRANSACTION",
        "transactionId": transaction_id,
        "userId": user_id,
        "action": action,
        "points": points,
        "referenceId": reference_id,
        "verifiedBy": verified_by,
        "createdAt": created_at,
        "metadata": metadata or {},
    }
    try:
        table.put_item(
            Item=transaction,
            ConditionExpression="attribute_not_exists(PK)",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            existing = table.get_item(
                Key={"PK": f"GREENPOINT_TX#{transaction_id}", "SK": "DETAILS"}
            ).get("Item")
            if existing:
                return existing
        raise
    table.update_item(
        Key={"PK": f"WALLET#{user_id}", "SK": "PROFILE"},
        UpdateExpression=(
            "SET citizenId=:citizen, entityType=:entity, updatedAt=:at "
            "ADD greenPoints :points"
        ),
        ExpressionAttributeValues={
            ":citizen": user_id,
            ":entity": "WALLET",
            ":at": created_at,
            ":points": points,
        },
    )
    return transaction


def award_verified_scan(scan_id: str, weight: Decimal, actor: str, role: str, event_id: str, category: str | None = None) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "ADMIN")
    scan = get_scan(scan_id)
    if category and category.upper() != scan["materialType"]:
        raise ValueError("Verified category does not match the AI material type")
    action = action_for_verified_deposit(
        hazard_level=str(scan.get("hazardLevel", "LOW")),
        category=str(scan.get("category", "unknown")),
    )
    points = calculate_points(action, verified_weight_kg=float(weight), verified=True, rules=configured_reward_rules())
    try:
        updated = table.update_item(
            Key={"PK": f"SCAN#{scan_id}", "SK": "DETAILS"},
            UpdateExpression="SET #status=:verified, verifiedWeight=:weight, verifiedAt=:at, verifiedBy=:worker, greenPoints=:points, workflowStatus=:workflow",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":verified": "VERIFIED", ":pending": "PENDING", ":weight": weight, ":at": now(), ":worker": actor, ":points": points, ":workflow": "VERIFIED"},
            ConditionExpression="#status=:pending",
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ValueError("This scan has already been verified") from exc
        raise
    citizen_id = scan["citizenId"]
    transaction = record_green_point_transaction(
        user_id=citizen_id,
        action=action,
        points=points,
        reference_id=scan_id,
        verified_by=actor,
        metadata={"weightKg": weight, "eventId": event_id, "category": scan.get("category")},
    )
    table.update_item(
        Key={"PK": f"WALLET#{citizen_id}", "SK": "PROFILE"},
        UpdateExpression="SET citizenId=:citizen, entityType=:entity, updatedAt=:at ADD lifetimeVerifiedKg :weight",
        ExpressionAttributeValues={":citizen": citizen_id, ":entity": "WALLET", ":at": now(), ":weight": weight},
    )
    audit(actor, role, "VERIFY_DEPOSIT", scan_id, "VERIFIED")
    publish_notification("COLLECTION_VERIFIED", user_id=citizen_id, data={"greenPoints": transaction["points"], "scanId": scan_id})
    publish_notification("GREENPOINTS_EARNED", user_id=citizen_id, data={"greenPoints": transaction["points"]})
    return {"scan": updated, "eventId": event_id, "greenPointsAwarded": transaction["points"], "greenPointTransaction": transaction}


def verify(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    try:
        weight = Decimal(str(body.get("verifiedWeight")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("verifiedWeight must be a positive number") from exc
    if weight <= 0 or weight > 10000:
        raise ValueError("verifiedWeight must be greater than 0 and no more than 10000 kg")
    scan_id = str(body.get("scanId") or "").strip()
    if not scan_id:
        raise ValueError("scanId is required")
    return award_verified_scan(scan_id, weight, actor, role, str(uuid.uuid4()), body.get("materialType"))


def collection_event(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "ADMIN")
    scan_id = str(body.get("scanId") or "").strip()
    center_id = str(body.get("centerId") or body.get("collectionCenterId") or "").strip()
    try:
        weight = Decimal(str(body.get("verifiedWeight") or body.get("weightKg")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("verifiedWeight is required") from exc
    if not scan_id or not center_id or weight <= 0:
        raise ValueError("scanId, centerId, and positive verifiedWeight are required")
    event_id = str(body.get("idempotencyKey") or hashlib.sha256(
        f"{scan_id}|{center_id}|{weight}".encode("utf-8")
    ).hexdigest())
    existing = table.get_item(Key={"PK": f"COLLECTION#{event_id}", "SK": "DETAILS"}).get("Item")
    if existing:
        return {"event": existing, "verification": {"message": "Existing idempotent collection event returned"}}
    event = {"PK": f"COLLECTION#{event_id}", "SK": "DETAILS", "entityType": "COLLECTION_EVENT", "eventId": event_id, "scanId": scan_id, "centerId": center_id, "verifiedWeight": weight, "verifiedBy": actor, "createdAt": now(), "status": "VERIFIED"}
    table.put_item(Item=event)
    verification = award_verified_scan(scan_id, weight, actor, role, event_id, body.get("materialType"))
    return {"event": event, "verification": verification}


def reward_action(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "ADMIN")
    user_id = str(body.get("userId") or "").strip()
    action = str(body.get("action") or "").strip().upper()
    reference_id = str(body.get("referenceId") or "").strip()
    if not user_id or not action or not reference_id:
        raise ValueError("userId, action, and referenceId are required")
    event = table.get_item(Key={"PK": f"COLLECTION#{reference_id}", "SK": "DETAILS"}).get("Item")
    if not event or event.get("status") != "VERIFIED":
        raise ValueError("GreenPoints require a verified collection event")
    try:
        weight = float(body.get("verifiedWeightKg") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("verifiedWeightKg must be numeric") from exc
    points = calculate_points(action, verified_weight_kg=weight, verified=True, rules=configured_reward_rules())
    transaction = record_green_point_transaction(
        user_id=user_id,
        action=action,
        points=points,
        reference_id=reference_id,
        verified_by=actor,
        metadata={"weightKg": weight},
    )
    audit(actor, role, "AWARD_GREENPOINTS", transaction["transactionId"], action)
    return {"transaction": transaction}


def list_items(entity_type: str) -> list[dict[str, Any]]:
    result = table.scan(FilterExpression="entityType = :entity", ExpressionAttributeValues={":entity": entity_type})
    items = result.get("Items", [])
    while result.get("LastEvaluatedKey"):
        result = table.scan(ExclusiveStartKey=result["LastEvaluatedKey"], FilterExpression="entityType = :entity", ExpressionAttributeValues={":entity": entity_type})
        items.extend(result.get("Items", []))
    return items


def inventory(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    filters = filters or {}
    scans, batches = list_items("SCAN"), list_items("MATERIAL_BATCH")
    for key in ("materialType", "mrfId", "ward", "workflowStatus", "qualityStatus", "contaminationStatus"):
        if filters.get(key):
            batches = [item for item in batches if str(item.get(key) or item.get("centerId") or "").upper() == str(filters[key]).upper()]
    pending = [item for item in scans if item.get("status") == "PENDING"]
    aggregate: dict[str, dict[str, Any]] = {}
    for item in batches:
        material = item["materialType"]
        bucket = aggregate.setdefault(material, {"materialType": material, "batchCount": 0, "weightKg": Decimal("0")})
        bucket["batchCount"] += 1
        bucket["weightKg"] += Decimal(str(item.get("weightKg", 0)))
    return {"scans": scans, "pending": pending, "inventory": list(aggregate.values()), "batches": batches, "totalScans": len(scans)}


def create_batch(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "ADMIN")
    scan_ids = body.get("scanIds")
    if not isinstance(scan_ids, list) or not scan_ids:
        raise ValueError("scanIds must contain at least one verified scan")
    scans = [get_scan(str(scan_id)) for scan_id in scan_ids]
    if any(scan.get("status") != "VERIFIED" for scan in scans):
        raise ValueError("Only verified scans can be aggregated")
    material = str(body.get("materialType") or scans[0]["materialType"]).upper()
    if any(scan["materialType"] != material for scan in scans):
        raise ValueError("All scans in a batch must have the same material type")
    if any(scan["hazardLevel"] in {"HIGH", "CRITICAL"} and body.get("publicUpcycling") for scan in scans):
        raise ValueError("Critical material cannot be routed to public upcycling")
    quantity = body.get("quantity", len(scan_ids))
    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError("quantity must be a positive integer") from exc
    if quantity <= 0:
        raise ValueError("quantity must be a positive integer")
    requested_status = str(body.get("status") or "AGGREGATING").upper()
    if requested_status not in BATCH_STATUSES:
        raise ValueError(f"Unsupported batch status: {requested_status}")
    if requested_status in {"READY_FOR_RECOVERY", "PARTNER_REQUESTED", "PICKUP_SCHEDULED", "RECOVERED"} and body.get("qualityStatus") not in {"PASSED", "ACCEPTABLE"}:
        raise ValueError("A passed quality check is required before recovery routing")
    risk_levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    hazard_level = max((scan["hazardLevel"] for scan in scans), key=lambda level: risk_levels.get(level, 3))
    source_centers = sorted({str(body.get("centerId") or scan.get("centerId") or "UNSPECIFIED") for scan in scans})
    batch_id = str(uuid.uuid4())
    batch = {
        "PK": f"BATCH#{batch_id}", "SK": "DETAILS", "entityType": "MATERIAL_BATCH",
        "batchId": batch_id, "scanIds": scan_ids, "materialType": material,
        "quantity": quantity,
        "weightKg": sum((Decimal(str(scan["verifiedWeight"])) for scan in scans), Decimal("0")),
        "sourceCollectionCenters": source_centers, "hazardLevel": hazard_level,
        "riskStatus": "SPECIAL_HANDLING" if hazard_level in {"HIGH", "CRITICAL"} else "STANDARD",
        "qualityStatus": str(body.get("qualityStatus") or "PENDING").upper(),
        "contaminationStatus": str(body.get("contaminationStatus") or "UNKNOWN").upper(),
        "recoveryOptions": sorted({option for scan in scans for option in scan.get("recoveryOptions", [])}),
        "eligibleRecoveryPathways": sorted({option for scan in scans for option in scan.get("recoveryOptions", [])}),
        "workflowStatus": requested_status, "createdAt": now(), "createdBy": actor,
    }
    table.put_item(Item=batch)
    for scan_id in scan_ids:
        table.update_item(Key={"PK": f"SCAN#{scan_id}", "SK": "DETAILS"}, UpdateExpression="SET workflowStatus=:status, batchId=:batch", ExpressionAttributeValues={":status": "BATCHED", ":batch": batch_id})
    audit(actor, role, "CREATE_BATCH", batch_id, "AVAILABLE")
    return {"batch": batch}


def update_batch(batch_id: str, body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "ADMIN")
    batch_id = str(batch_id).strip()
    if not batch_id:
        raise ValueError("batchId is required")
    existing = table.get_item(Key={"PK": f"BATCH#{batch_id}", "SK": "DETAILS"}).get("Item")
    if not existing:
        raise ValueError("Material batch not found")
    status = str(body.get("status") or "").upper()
    if status not in BATCH_STATUSES:
        raise ValueError("Unsupported batch status")
    quality = str(body.get("qualityStatus") or existing.get("qualityStatus", "PENDING")).upper()
    contamination = str(body.get("contaminationStatus") or existing.get("contaminationStatus", "UNKNOWN")).upper()
    previous_status = str(existing.get("workflowStatus") or "COLLECTING")
    if previous_status in RECOVERY_STATUSES and status in RECOVERY_STATUSES:
        validate_transition(previous_status, status)
    if status in {"READY_FOR_RECOVERY", "PARTNER_REQUESTED", "PICKUP_SCHEDULED", "RECOVERED"} and quality not in {"PASSED", "ACCEPTABLE"}:
        raise ValueError("A passed quality check is required before recovery routing")
    updated = table.update_item(
        Key={"PK": f"BATCH#{batch_id}", "SK": "DETAILS"},
        UpdateExpression="SET workflowStatus=:status, qualityStatus=:quality, contaminationStatus=:contamination, updatedAt=:at, updatedBy=:actor",
        ExpressionAttributeValues={":status": status, ":quality": quality, ":contamination": contamination, ":at": now(), ":actor": actor},
        ReturnValues="ALL_NEW",
    )["Attributes"]
    audit(actor, role, "UPDATE_BATCH_STATUS", batch_id, status)
    if status in {"READY_FOR_RECOVERY", "READY_FOR_AGGREGATION"}:
        publish_notification("RECOVERY_READY_BATCH", roles=["MUNICIPAL_OFFICER", "ADMIN"], data={"batchId": batch_id})
    return {"batch": updated}


def create_project(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_OFFICER", "ADMIN")
    name = str(body.get("name") or "").strip()
    description = str(body.get("description") or "").strip()
    requirements = body.get("materialRequirements")
    if not name or not description or not isinstance(requirements, list) or not requirements:
        raise ValueError("name, description, and materialRequirements are required")
    status = "PENDING_APPROVAL"
    project_id, qr_token = str(uuid.uuid4()), str(uuid.uuid4())
    normalized_requirements = []
    for requirement in requirements:
        try:
            quantity = int(requirement["estimatedQuantity"])
            weight = float(requirement.get("estimatedWeightKg", 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Each material requirement needs quantity and weight") from exc
        if quantity <= 0 or weight < 0:
            raise ValueError("Material requirements must be positive")
        normalized_requirements.append({
            "materialType": str(requirement["materialType"]).upper(),
            "estimatedQuantity": quantity,
            "estimatedWeightKg": weight,
        })
    material_eligibility = project_requirements_eligibility(normalized_requirements)
    project = {
        "PK": f"PROJECT#{project_id}", "SK": "DETAILS", "entityType": "CIRCULAR_PROJECT",
        "projectId": project_id, "name": name, "projectType": str(body.get("projectType") or "PUBLIC_INSTALLATION"),
        "description": description, "location": body.get("location") or {},
        "materialRequirements": normalized_requirements,
        "participatingCommunity": body.get("participatingCommunity") or [],
        "impactMetrics": {"estimatedWeightKg": sum(item["estimatedWeightKg"] for item in normalized_requirements), "amountDivertedKg": 0},
        "materialEligibility": material_eligibility,
        "status": status, "approvalStatus": "PENDING", "qrToken": qr_token,
        "createdAt": now(), "createdBy": actor,
    }
    table.put_item(Item=project)
    audit(actor, role, "CREATE_CIRCULAR_PROJECT", project_id, status)
    return {"project": project}


def approve_project(project_id: str, body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_OFFICER", "ADMIN")
    project = table.get_item(Key={"PK": f"PROJECT#{project_id}", "SK": "DETAILS"}).get("Item")
    if not project:
        raise ValueError("Circular project not found")
    decision = str(body.get("decision") or "").upper()
    if decision not in {"APPROVED", "REJECTED"}:
        raise ValueError("decision must be APPROVED or REJECTED")
    if decision == "APPROVED" and not project.get("materialEligibility", {}).get("eligible", False):
        raise ValueError("Project contains material that is not eligible for public installation")
    updated = table.update_item(
        Key={"PK": f"PROJECT#{project_id}", "SK": "DETAILS"},
        UpdateExpression="SET approvalStatus=:approval, #status=:status, approvedBy=:actor, approvedAt=:at, approvalNote=:note",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":approval": decision, ":status": decision, ":actor": actor, ":at": now(), ":note": str(body.get("note") or "")},
        ReturnValues="ALL_NEW",
    )["Attributes"]
    audit(actor, role, "PROJECT_APPROVAL", project_id, decision)
    return {"project": updated}


def allocate_project_material(project_id: str, body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_OFFICER", "ADMIN")
    project = table.get_item(Key={"PK": f"PROJECT#{project_id}", "SK": "DETAILS"}).get("Item")
    if not project or project.get("approvalStatus") != "APPROVED":
        raise ValueError("Only approved projects can receive material")
    batch_ids = body.get("batchIds")
    if not isinstance(batch_ids, list) or not batch_ids:
        raise ValueError("batchIds is required")
    batches = [table.get_item(Key={"PK": f"BATCH#{str(batch_id)}", "SK": "DETAILS"}).get("Item") for batch_id in batch_ids]
    if any(not batch for batch in batches):
        raise ValueError("Material batch not found")
    eligibility = [public_material_eligibility(batch) for batch in batches if batch]
    if any(not item["eligible"] for item in eligibility):
        raise ValueError("One or more batches are not eligible for public installation")
    diverted = sum(float(batch.get("weightKg", 0)) for batch in batches if batch)
    updated = table.update_item(
        Key={"PK": f"PROJECT#{project_id}", "SK": "DETAILS"},
        UpdateExpression="SET batchIds=:batches, #status=:status, materialEligibility=:eligibility, impactMetrics=:impact, updatedAt=:at",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":batches": batch_ids, ":status": "MATERIAL_ALLOCATED", ":eligibility": {"eligible": True, "reasons": ["All allocated batches passed the public-installation safety gate"]}, ":impact": {"estimatedWeightKg": project.get("impactMetrics", {}).get("estimatedWeightKg", 0), "amountDivertedKg": diverted}, ":at": now()},
        ReturnValues="ALL_NEW",
    )["Attributes"]
    return {"project": updated}


def update_project_status(project_id: str, body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_OFFICER", "ADMIN")
    project = table.get_item(Key={"PK": f"PROJECT#{project_id}", "SK": "DETAILS"}).get("Item")
    if not project:
        raise ValueError("Circular project not found")
    status = str(body.get("status") or "").upper()
    if status not in PROJECT_STATUSES:
        raise ValueError("Unsupported project status")
    if status in {"MATERIAL_ALLOCATED", "IN_PROGRESS", "COMPLETED"} and project.get("approvalStatus") != "APPROVED":
        raise ValueError("Project must be approved before work begins")
    if status == "COMPLETED" and not project.get("batchIds"):
        raise ValueError("Completed project must have allocated material")
    updated = table.update_item(
        Key={"PK": f"PROJECT#{project_id}", "SK": "DETAILS"},
        UpdateExpression="SET #status=:status, updatedAt=:at, updatedBy=:actor, projectImpact=:impact",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": status, ":at": now(), ":actor": actor, ":impact": body.get("impactMetrics", project.get("impactMetrics", {}))},
        ReturnValues="ALL_NEW",
    )["Attributes"]
    audit(actor, role, "UPDATE_CIRCULAR_PROJECT", project_id, status)
    return {"project": updated}


def list_projects() -> dict[str, Any]:
    return {"projects": list_items("CIRCULAR_PROJECT")}


def public_project(qr_token: str) -> dict[str, Any]:
    projects = [item for item in list_items("CIRCULAR_PROJECT") if item.get("qrToken") == qr_token and item.get("status") == "COMPLETED"]
    if not projects:
        raise ValueError("Completed project not found")
    project = projects[0]
    return {"project": {"projectId": project["projectId"], "name": project["name"], "description": project["description"], "materialRequirements": project["materialRequirements"], "impactMetrics": project.get("impactMetrics", {}), "participatingCommunity": project.get("participatingCommunity", []), "status": project["status"]}}


def partner(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "RECOVERY_PARTNER", "ADMIN")
    accepted = body.get("acceptedMaterials")
    if not isinstance(accepted, list) or not accepted:
        raise ValueError("acceptedMaterials must contain at least one material")
    partner_type = str(body.get("partnerType") or "RECYCLER").upper()
    if partner_type not in {"ORIGINAL_PRODUCER", "RECYCLER", "REUSE_PARTNER", "UPCYCLER", "COMMUNITY_PROJECT", "SPECIALIZED_TREATMENT"}:
        raise ValueError("Unsupported partner type")
    verification_status = str(body.get("verificationStatus") or "PENDING").upper()
    if role != "ADMIN":
        verification_status = "PENDING"
    item = {"PK": f"PARTNER#{actor}", "SK": "PROFILE", "entityType": "RECOVERY_PARTNER", "partnerId": actor, "name": str(body.get("name") or actor), "partnerType": partner_type, "acceptedMaterials": [str(value).upper() for value in accepted], "minimumQuantity": float(body.get("minimumQuantity", 0) or 0), "qualityRequirements": body.get("qualityRequirements", {}), "contaminationLimit": body.get("contaminationLimit"), "serviceRadiusKm": body.get("serviceRadiusKm"), "location": body.get("location"), "acceptedHazardLevels": body.get("acceptedHazardLevels", ["LOW", "MEDIUM"]), "verificationStatus": verification_status, "updatedAt": now()}
    table.put_item(Item=item)
    return {"partner": item}


def verify_partner(partner_id: str, body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_OFFICER", "ADMIN")
    partner_id = str(partner_id).strip()
    if not partner_id:
        raise ValueError("partnerId is required")
    decision = str(body.get("verificationStatus") or "").upper()
    if decision not in {"VERIFIED", "SUSPENDED", "PENDING"}:
        raise ValueError("verificationStatus must be VERIFIED, SUSPENDED, or PENDING")
    existing = table.get_item(Key={"PK": f"PARTNER#{partner_id}", "SK": "PROFILE"}).get("Item")
    if not existing:
        raise ValueError("Recovery partner not found")
    updated = table.update_item(
        Key={"PK": f"PARTNER#{partner_id}", "SK": "PROFILE"},
        UpdateExpression="SET verificationStatus=:status, verifiedBy=:actor, verifiedAt=:at",
        ExpressionAttributeValues={":status": decision, ":actor": actor, ":at": now()},
        ReturnValues="ALL_NEW",
    )["Attributes"]
    audit(actor, role, "VERIFY_RECOVERY_PARTNER", partner_id, decision)
    return {"partner": updated}


def matches(body: dict[str, Any], actor: str, role: str, match_id: str | None = None) -> dict[str, Any]:
    if match_id:
        require_role(role, "RECOVERY_PARTNER", "MUNICIPAL_OFFICER", "ADMIN")
        parts = match_id.split("#", 1)
        if len(parts) != 2:
            raise ValueError("Match must contain batch and partner")
        batch_id, partner_id = parts
        if role == "RECOVERY_PARTNER" and partner_id != actor:
            raise PermissionError("A partner can only accept its own match")
        return recovery_request({"batchId": batch_id, "partnerId": partner_id}, actor, role)
    batches, partners = list_items("MATERIAL_BATCH"), list_items("RECOVERY_PARTNER")
    eligible = []
    for batch in batches:
        if batch.get("workflowStatus") not in {"READY_FOR_RECOVERY", "PARTNER_REQUESTED"}:
            continue
        for item in match_batch(batch, partners):
            item.update({"matchId": f"{batch['batchId']}#{item['partnerId']}", "batchId": batch["batchId"], "route": item["pathway"]})
            eligible.append(item)
    return {"matches": eligible}


def centers() -> dict[str, Any]:
    return {"centers": list_items("COLLECTION_CENTER")}


def campaigns(body: dict[str, Any], actor: str, role: str, create: bool = False) -> dict[str, Any]:
    if not create:
        return {"campaigns": list_items("CAMPAIGN")}
    require_role(role, "MUNICIPAL_OFFICER", "ADMIN")
    require_fields(body, "name", "startAt", "endAt")
    campaign_id = str(uuid.uuid4())
    item = {
        "PK": f"CAMPAIGN#{campaign_id}",
        "SK": "DETAILS",
        "entityType": "CAMPAIGN",
        "campaignId": campaign_id,
        "name": str(body["name"]).strip(),
        "description": str(body.get("description") or "").strip(),
        "startAt": str(body["startAt"]),
        "endAt": str(body["endAt"]),
        "targetWard": str(body.get("targetWard") or "").strip(),
        "status": "PLANNED",
        "createdBy": actor,
        "createdAt": now(),
    }
    table.put_item(Item=item)
    audit(actor, role, "CREATE_CAMPAIGN", campaign_id, "PLANNED")
    return {"campaign": item}


def create_center(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_OFFICER", "ADMIN")
    name = str(body.get("name") or "").strip()
    if not name:
        raise ValueError("Collection center name is required")
    center_id = str(body.get("centerId") or uuid.uuid4())
    center = {"PK": f"CENTER#{center_id}", "SK": "PROFILE", "entityType": "COLLECTION_CENTER", "centerId": center_id, "name": name, "address": str(body.get("address") or ""), "acceptedMaterials": [str(value).upper() for value in body.get("acceptedMaterials", [])], "openingHours": str(body.get("openingHours") or ""), "createdBy": actor, "createdAt": now()}
    table.put_item(Item=center)
    audit(actor, role, "CREATE_CENTER", center_id, "AVAILABLE")
    return {"center": center}


def profile(actor: str, role: str) -> dict[str, Any]:
    scans = [item for item in list_items("SCAN") if item.get("citizenId") == actor]
    wallet = table.get_item(Key={"PK": f"WALLET#{actor}", "SK": "PROFILE"}).get("Item", {"greenPoints": 0, "lifetimeVerifiedKg": 0})
    verified = [item for item in scans if item.get("status") == "VERIFIED"]
    transactions = [item for item in list_items("GREENPOINT_TRANSACTION") if item.get("userId") == actor]
    special_returns = sum(
        1 for item in transactions
        if item.get("action") in {"VERIFIED_SPECIAL_WASTE_DEPOSIT", "VERIFIED_AGRICULTURAL_CONTAINER_RETURN"}
    )
    badges = badges_for(
        transaction_count=len(transactions),
        verified_deposits=len(verified),
        points=int(wallet.get("greenPoints", 0)),
        special_returns=special_returns,
    )
    wallets = list_items("WALLET")
    leaderboard = calculate_leaderboard(wallets)[:10]
    ward_leaderboard = calculate_leaderboard(wallets, ward=wallet.get("ward"))[:10] if wallet.get("ward") else []
    return {
        "wallet": wallet,
        "transactions": transactions[-20:],
        "badges": badges,
        "leaderboard": leaderboard,
        "wardLeaderboard": ward_leaderboard,
        "impact": {"verifiedDeposits": len(verified), "verifiedWeightKg": wallet.get("lifetimeVerifiedKg", 0)},
        "role": role,
    }


def analytics(actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_OFFICER", "ADMIN")
    scans, batches = list_items("SCAN"), list_items("MATERIAL_BATCH")
    verified = [item for item in scans if item.get("status") == "VERIFIED"]
    recovered = [item for item in batches if item.get("workflowStatus") in {"RECOVERED", "CLOSED"}]
    material_weights: dict[str, Decimal] = {}
    for item in verified:
        material = str(item.get("materialType") or "unknown").upper()
        material_weights[material] = material_weights.get(material, Decimal("0")) + Decimal(str(item.get("verifiedWeight", 0)))
    total_verified = sum(material_weights.values(), Decimal("0"))
    recovered_weight = sum((Decimal(str(item.get("recoveredWeightKg", item.get("weightKg", 0)))) for item in recovered), Decimal("0"))
    wallets = list_items("WALLET")
    partners = [item for item in list_items("RECOVERY_PARTNER") if item.get("verificationStatus") == "VERIFIED"]
    return {
        "totalWasteCollectedKg": sum((Decimal(str(item.get("weightKg", 0))) for item in scans), Decimal("0")),
        "totalVerifiedMaterialKg": total_verified,
        "totalWasteDivertedKg": total_verified,
        "materialWeightsKg": material_weights,
        "petKg": material_weights.get("PET", Decimal("0")),
        "hdpeKg": material_weights.get("HDPE", Decimal("0")),
        "ppKg": material_weights.get("PP", Decimal("0")),
        "glassKg": material_weights.get("GLASS", Decimal("0")),
        "aluminiumKg": material_weights.get("ALUMINUM", material_weights.get("ALUMINIUM", Decimal("0"))),
        "hazardousWasteKg": sum((Decimal(str(item.get("verifiedWeight", 0))) for item in verified if item.get("hazardLevel") in {"HIGH", "CRITICAL"}), Decimal("0")),
        "readyForRecoveryKg": sum((Decimal(str(item.get("weightKg", 0))) for item in batches if item.get("workflowStatus") in {"READY_FOR_RECOVERY", "READY_FOR_AGGREGATION"}), Decimal("0")),
        "recoveredMaterialKg": recovered_weight,
        "recoveryRate": (recovered_weight / total_verified if total_verified else Decimal("0")),
        "citizenParticipation": len({item.get("citizenId") for item in verified if item.get("citizenId")}),
        "greenPointsIssued": sum((int(item.get("greenPoints", 0)) for item in wallets), 0),
        "agriculturalContainersReturned": sum(1 for item in verified if item.get("category") == "agricultural-container"),
        "activeRecoveryPartners": len(partners),
        "completedRecoveryBatches": len(recovered),
        "totalScans": len(scans),
        "verifiedDeposits": len(verified),
        "hazardousIncidents": sum(1 for item in scans if item.get("hazardLevel") in {"HIGH", "CRITICAL"}),
        "inventoryByMaterial": inventory()["inventory"],
        "availableBatches": sum(1 for item in batches if item.get("workflowStatus") in {"READY_FOR_RECOVERY", "PARTNER_REQUESTED"}),
    }


def recovery_request(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "RECOVERY_PARTNER", "ADMIN")
    batch_id, partner_id = str(body.get("batchId") or "").strip(), str(body.get("partnerId") or "").strip()
    if not batch_id or not partner_id:
        raise ValueError("batchId and partnerId are required")
    batch = table.get_item(Key={"PK": f"BATCH#{batch_id}", "SK": "DETAILS"}).get("Item")
    if not batch:
        raise ValueError("Material batch not found")
    if batch.get("workflowStatus") not in {"READY_FOR_RECOVERY", "PARTNER_REQUESTED"}:
        raise ValueError("Batch is not ready for recovery")
    request_id = str(uuid.uuid4())
    request = {"PK": f"RECOVERY_REQUEST#{request_id}", "SK": "DETAILS", "entityType": "RECOVERY_REQUEST", "requestId": request_id, "batchId": batch_id, "partnerId": partner_id, "status": "REQUESTED", "actorId": actor, "createdAt": now()}
    table.put_item(Item=request)
    table.update_item(Key={"PK": f"BATCH#{batch_id}", "SK": "DETAILS"}, UpdateExpression="SET workflowStatus=:status, recoveryRequestId=:request, updatedAt=:at", ExpressionAttributeValues={":status": "PARTNER_REQUESTED", ":request": request_id, ":at": now()})
    audit(actor, role, "CREATE_RECOVERY_REQUEST", request_id, "REQUESTED")
    publish_notification("RECOVERY_REQUEST", user_id=partner_id, roles=["MUNICIPAL_OFFICER", "ADMIN"], data={"requestId": request_id, "batchId": batch_id})
    return {"request": request}


def update_recovery_request(request_id: str, body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "RECOVERY_PARTNER", "ADMIN")
    request = table.get_item(Key={"PK": f"RECOVERY_REQUEST#{request_id}", "SK": "DETAILS"}).get("Item")
    if not request:
        raise ValueError("Recovery request not found")
    if role == "RECOVERY_PARTNER" and request.get("partnerId") != actor:
        raise PermissionError("Partner can only update its own recovery request")
    status = str(body.get("status") or "").upper()
    if status not in {"REQUESTED", "ACCEPTED", "REJECTED", "CANCELLED"}:
        raise ValueError("Unsupported recovery request status")
    updated = table.update_item(Key={"PK": f"RECOVERY_REQUEST#{request_id}", "SK": "DETAILS"}, UpdateExpression="SET #status=:status, updatedAt=:at, updatedBy=:actor", ExpressionAttributeNames={"#status": "status"}, ExpressionAttributeValues={":status": status, ":at": now(), ":actor": actor}, ReturnValues="ALL_NEW")["Attributes"]
    if status == "ACCEPTED":
        table.update_item(Key={"PK": f"BATCH#{request['batchId']}", "SK": "DETAILS"}, UpdateExpression="SET workflowStatus=:status, updatedAt=:at", ExpressionAttributeValues={":status": "RESERVED", ":at": now()})
    audit(actor, role, "UPDATE_RECOVERY_REQUEST", request_id, status)
    publish_notification("RECOVERY_REQUEST_STATUS", user_id=request.get("partnerId"), data={"requestId": request_id, "status": status})
    return {"request": updated}


def schedule_pickup(request_id: str, body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "RECOVERY_PARTNER", "ADMIN")
    request = table.get_item(Key={"PK": f"RECOVERY_REQUEST#{request_id}", "SK": "DETAILS"}).get("Item")
    if not request or request.get("status") != "ACCEPTED":
        raise ValueError("An accepted recovery request is required")
    pickup_id = str(uuid.uuid4())
    pickup = {"PK": f"PICKUP#{pickup_id}", "SK": "DETAILS", "entityType": "PICKUP", "pickupId": pickup_id, "requestId": request_id, "batchId": request["batchId"], "partnerId": request["partnerId"], "scheduledAt": str(body.get("scheduledAt") or "").strip(), "carrier": str(body.get("carrier") or "").strip(), "status": "SCHEDULED", "createdAt": now(), "createdBy": actor}
    if not pickup["scheduledAt"]:
        raise ValueError("scheduledAt is required")
    table.put_item(Item=pickup)
    table.update_item(Key={"PK": f"RECOVERY_REQUEST#{request_id}", "SK": "DETAILS"}, UpdateExpression="SET pickupId=:pickup, status=:status, updatedAt=:at", ExpressionAttributeValues={":pickup": pickup_id, ":status": "PICKUP_SCHEDULED", ":at": now()})
    table.update_item(Key={"PK": f"BATCH#{request['batchId']}", "SK": "DETAILS"}, UpdateExpression="SET workflowStatus=:status, pickupId=:pickup, updatedAt=:at", ExpressionAttributeValues={":status": "PICKUP_SCHEDULED", ":pickup": pickup_id, ":at": now()})
    audit(actor, role, "SCHEDULE_PICKUP", pickup_id, "SCHEDULED")
    publish_notification("PICKUP_SCHEDULED", user_id=request["partnerId"], data={"batchId": request["batchId"], "scheduledAt": pickup["scheduledAt"]})
    return {"pickup": pickup}


def recovery_status(batch_id: str, body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "RECOVERY_PARTNER", "ADMIN")
    batch = table.get_item(Key={"PK": f"BATCH#{batch_id}", "SK": "DETAILS"}).get("Item")
    if not batch:
        raise ValueError("Material batch not found")
    previous, status = str(batch.get("workflowStatus") or "COLLECTING"), str(body.get("status") or "").upper()
    validate_transition(previous, status)
    timestamp = now()
    transition = {"actor": actor, "timestamp": timestamp, "previousStatus": previous, "newStatus": status, "reason": str(body.get("reason") or ""), "metadata": body.get("metadata") or {}}
    updated = table.update_item(Key={"PK": f"BATCH#{batch_id}", "SK": "DETAILS"}, UpdateExpression="SET workflowStatus=:status, updatedAt=:at, updatedBy=:actor, transitionHistory=list_append(if_not_exists(transitionHistory,:empty),:transition)", ExpressionAttributeValues={":status": status, ":at": timestamp, ":actor": actor, ":empty": [], ":transition": [transition]}, ReturnValues="ALL_NEW")["Attributes"]
    audit(actor, role, "RECOVERY_STATUS_TRANSITION", batch_id, status)
    if status == "RECEIVED":
        publish_notification("MATERIAL_RECEIVED", user_id=batch.get("partnerId"), data={"batchId": batch_id})
    return {"batch": updated, "transition": transition}


def recovery_result(batch_id: str, body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "RECOVERY_PARTNER", "ADMIN")
    batch = table.get_item(Key={"PK": f"BATCH#{batch_id}", "SK": "DETAILS"}).get("Item")
    if not batch or batch.get("workflowStatus") != "PROCESSING":
        raise ValueError("Batch must be PROCESSING before completion")
    metrics = completion_metrics(Decimal(str(body.get("inputWeightKg", batch.get("weightKg", 0)))), Decimal(str(body.get("recoveredWeightKg", 0))), Decimal(str(body.get("rejectedWeightKg", 0))))
    result = {"PK": f"RECOVERY_RESULT#{batch_id}", "SK": "DETAILS", "entityType": "RECOVERY_RESULT", "batchId": batch_id, **metrics, "recoveryMethod": str(body.get("recoveryMethod") or "").strip(), "completedAt": now(), "completedBy": actor}
    if not result["recoveryMethod"]:
        raise ValueError("recoveryMethod is required")
    table.put_item(Item=result)
    table.update_item(Key={"PK": f"BATCH#{batch_id}", "SK": "DETAILS"}, UpdateExpression="SET workflowStatus=:status, recoveryResultId=:result, recoveredWeightKg=:weight, updatedAt=:at", ExpressionAttributeValues={":status": "RECOVERED", ":result": batch_id, ":weight": metrics["recoveredWeightKg"], ":at": now()})
    audit(actor, role, "COMPLETE_RECOVERY", batch_id, "RECOVERED")
    publish_notification("RECOVERY_COMPLETED", user_id=batch.get("partnerId"), data={"batchId": batch_id})
    return {"result": result}


def aggregate_opportunity(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "ADMIN")
    batch_ids = [str(item).strip() for item in body.get("sourceBatchIds", []) if str(item).strip()]
    if not batch_ids:
        raise ValueError("sourceBatchIds is required")
    batches = [table.get_item(Key={"PK": f"BATCH#{item}", "SK": "DETAILS"}).get("Item") for item in batch_ids]
    if any(not item for item in batches):
        raise ValueError("All source batches must exist")
    materials = {str(item.get("materialType", "")).upper() for item in batches}
    if len(materials) != 1:
        raise ValueError("All source batches must use the same material")
    opportunity_id = str(uuid.uuid4())
    opportunity = {"PK": f"AGGREGATION#{opportunity_id}", "SK": "DETAILS", "entityType": "AGGREGATED_RECOVERY_OPPORTUNITY", "opportunityId": opportunity_id, "sourceBatchIds": batch_ids, "sourceMRFIds": sorted({str(item.get("mrfId") or item.get("centerId") or "UNSPECIFIED") for item in batches}), "sourceWards": sorted({str(item.get("ward") or "UNSPECIFIED") for item in batches}), "totalWeightKg": sum((Decimal(str(item.get("weightKg", 0))) for item in batches), Decimal("0")), "materialType": next(iter(materials)), "quality": str(body.get("quality") or "PENDING").upper(), "contamination": str(body.get("contamination") or "UNKNOWN").upper(), "status": "AVAILABLE", "createdAt": now(), "createdBy": actor, "physicalConsolidation": False}
    table.put_item(Item=opportunity)
    audit(actor, role, "CREATE_AGGREGATED_OPPORTUNITY", opportunity_id, "AVAILABLE")
    return {"opportunity": opportunity}


def copilot_tool_data(actor: str, role: str, name: str) -> dict[str, Any]:
    providers = {
        "getMaterialInventory": lambda: inventory(),
        "getWardStatistics": lambda: {"wards": analytics(actor, role).get("inventoryByMaterial", [])},
        "getHazardStatistics": lambda: {"hazardousIncidents": analytics(actor, role).get("hazardousIncidents", 0), "hazardousWasteKg": analytics(actor, role).get("hazardousWasteKg", 0)},
        "getRecoveryBatches": lambda: {"batches": [item for item in list_items("MATERIAL_BATCH") if item.get("workflowStatus") in {"READY_FOR_RECOVERY", "RESERVED", "PROCESSING"}]},
        "getRecoveryPartners": lambda: {"partners": [item for item in list_items("RECOVERY_PARTNER") if item.get("verificationStatus") == "VERIFIED"]},
        "getRecoveryMatches": lambda: matches({}, actor, role),
        "getGreenPointStatistics": lambda: {"wallets": list_items("WALLET"), "transactions": list_items("GREENPOINT_TRANSACTION")},
        "getCollectionTrends": lambda: {"scans": list_items("SCAN")},
        "getRecoveryImpact": lambda: analytics(actor, role),
    }
    return run_tool(name, role, providers)


def chat_history(actor: str, conversation_id: str) -> list[dict[str, str]]:
    messages = [
        item for item in list_items("CHAT_MESSAGE")
        if item.get("actorId") == actor and item.get("conversationId") == conversation_id
    ]
    messages.sort(key=lambda item: item.get("createdAt", ""))
    return [
        {"role": item.get("messageRole", "user"), "content": str(item.get("content", ""))}
        for item in messages[-12:]
    ]


def chat(body: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    question = str(body.get("message") or "").strip()
    if not question and not body.get("imageData"):
        raise ValueError("message or imageData is required")
    conversation_id = str(body.get("conversationId") or uuid.uuid4()).strip()
    language = str(body.get("language") or "en").lower()
    if language not in {"en", "te", "hi", "ta", "kn"}:
        language = "en"
    if len(conversation_id) > 128:
        raise ValueError("conversationId is too long")
    live = inventory()
    image_context = ""
    if body.get("imageData"):
        media_type, image_bytes = media_from_data_url(str(body["imageData"]))
        image_context = json.dumps(classify_image(media_type, image_bytes), default=str)
    sources = [
        {"type": "verified-knowledge", "id": "HAZARD_GUIDANCE", "version": "2026-10-05"},
        {"type": "live-api", "id": "GET /inventory", "recordCount": live.get("totalScans", 0)},
    ]
    knowledge_context = retrieve_verified_knowledge(question, role)
    if knowledge_context["citations"]:
        sources.extend(knowledge_context["citations"])
    if role in {"CITIZEN", "FARMER"}:
        live["centers"] = centers()["centers"]
        live["profile"] = profile(actor, role)
        sources.extend([
            {"type": "live-api", "id": "GET /centers", "recordCount": len(live["centers"])},
            {"type": "live-api", "id": "GET /profile"},
        ])
    elif role == "MUNICIPAL_OFFICER":
        live["analytics"] = analytics(actor, role)
        sources.append({"type": "live-api", "id": "GET /analytics"})
    elif role == "RECOVERY_PARTNER":
        live["matches"] = matches({}, actor, role)["matches"]
        sources.append({"type": "live-api", "id": "GET /matches", "recordCount": len(live["matches"])})
    history = chat_history(actor, conversation_id)
    provider = (
        LocalAssistantProvider()
        if os.environ.get("BEDROCK_DISABLED", "false").lower() == "true"
        else BedrockAssistantProvider(bedrock, MODEL_ID)
    )
    result = assistant_answer(
        provider,
        role=role,
        question=question,
        live_context=live,
        history=history,
        image_context=image_context,
        verified_context={
            "guidanceVersion": "2026-10-05",
            "roleScope": role,
            "hazardGuidance": HAZARD_GUIDANCE,
            "knowledgeBaseContext": knowledge_context["text"],
        },
        language=language,
    )
    created_at = now()
    table.put_item(Item={"PK": f"CHAT#{conversation_id}", "SK": f"{created_at}#user", "entityType": "CHAT_MESSAGE", "conversationId": conversation_id, "actorId": actor, "messageRole": "user", "content": question or "[image question]", "createdAt": created_at})
    table.put_item(Item={"PK": f"CHAT#{conversation_id}", "SK": f"{created_at}#assistant", "entityType": "CHAT_MESSAGE", "conversationId": conversation_id, "actorId": actor, "messageRole": "assistant", "content": result["answer"], "createdAt": now()})
    return {
        **result,
        "conversationId": conversation_id,
        "role": role,
        "language": language,
        "provider": provider.name,
        "sources": sources,
        "contextMetadata": {"liveContextAt": now(), "historyMessagesUsed": len(history), "imageAnalyzed": bool(image_context), "verifiedGuidanceVersion": "2026-10-05"},
    }


def retrieve_verified_knowledge(question: str, role: str) -> dict[str, Any]:
    """Retrieve approved policy text without making the KB authoritative for hazards."""
    knowledge_base_id = os.environ.get("KNOWLEDGE_BASE_ID", "").strip()
    if not knowledge_base_id:
        return {"text": "", "citations": []}
    result = bedrock_agent_runtime.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": f"Role: {role}. {question}"},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
    )
    text_parts = []
    citations = []
    for item in result.get("retrievalResults", []):
        text = str(item.get("content", {}).get("text") or "").strip()
        location = item.get("location", {})
        uri = location.get("s3Location", {}).get("uri") or location.get("webLocation", {}).get("url")
        if text:
            text_parts.append(text)
        if uri:
            citations.append({"type": "bedrock-knowledge-base", "id": uri})
    return {"text": "\n\n".join(text_parts), "citations": citations}


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    method = event.get("requestContext", {}).get("http", {}).get("method", "").upper()
    path = event.get("rawPath") or event.get("path") or ""
    request_id = str(event.get("requestContext", {}).get("requestId") or uuid.uuid4())
    versioned = path.startswith("/api/v1")
    versioned_route = path.removeprefix("/api/v1") if versioned else ""
    if versioned:
        path = path.removeprefix("/api/v1")
        if path.startswith("/qr/"):
            path = "/public-projects/" + path.split("/qr/", 1)[1]
        if path.startswith("/batches/") and path.endswith("/status"):
            path = path.removesuffix("/status") + "/recovery-status"
        elif path.startswith("/recovery/") and path.endswith("/status"):
            path = "/batches/" + path.split("/recovery/", 1)[1].removesuffix("/status") + "/recovery-status"
        path = {
            "/waste/analyze": "/analyze",
            "/waste/events": "/collection-events",
            "/collections": "/collection-events",
            "/greenpoints/award": "/greenpoints/reward",
            "/material-bank": "/inventory",
            "/aggregation/opportunities": "/aggregation-opportunities",
            "/matching": "/matches",
            "/recovery/requests": "/recovery-requests",
            "/analytics/municipal": "/analytics",
            "/copilot/query": "/chat",
            "/chat": "/chat",
            "/impact": "/analytics",
            "/reports": "/analytics",
            "/projects": "/projects",
            "/qr": "/public-projects",
        }.get(path, path)
    if method == "OPTIONS":
        return response(204, {}, request_id=request_id, versioned=versioned)
    if method == "GET" and "/public-projects/" in path:
        try:
            return response(200, public_project(path.split("/public-projects/", 1)[1]), request_id=request_id, versioned=versioned)
        except ValueError as exc:
            return error_response(404, "NOT_FOUND", str(exc), request_id, versioned)
    body = parse_body(event) if method in {"POST", "PUT", "PATCH"} else {}
    try:
        actor, role = identity(event, body)
        if method == "POST" and path.endswith("/analyze"):
            require_fields(body, "imageData")
            return response(200, analyze(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and path.endswith("/verify"):
            return response(200, verify(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and path.endswith("/collection-events"):
            return response(200, collection_event(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and path.endswith("/greenpoints/reward"):
            return response(200, reward_action(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "GET" and path.endswith("/inventory"):
            require_role(role, "MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "RECOVERY_PARTNER", "ADMIN")
            return response(200, inventory(event.get("queryStringParameters") or {}), request_id=request_id, versioned=versioned)
        if method == "POST" and path.endswith("/recovery-requests"):
            return response(201, recovery_request(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "PATCH" and "/recovery-requests/" in path:
            return response(200, update_recovery_request(path.split("/recovery-requests/", 1)[1], body, actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and "/recovery-requests/" in path and path.endswith("/pickup"):
            return response(201, schedule_pickup(path.split("/recovery-requests/", 1)[1].removesuffix("/pickup"), body, actor, role), request_id=request_id, versioned=versioned)
        if method in {"POST", "PATCH"} and "/batches/" in path and path.endswith("/recovery-status"):
            return response(200, recovery_status(path.split("/batches/", 1)[1].removesuffix("/recovery-status"), body, actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and "/batches/" in path and path.endswith("/recovery-result"):
            return response(200, recovery_result(path.split("/batches/", 1)[1].removesuffix("/recovery-result"), body, actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and path.endswith("/aggregation-opportunities"):
            return response(201, aggregate_opportunity(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "GET" and path.endswith("/copilot/tools"):
            return response(200, copilot_tool_data(actor, role, str((event.get("queryStringParameters") or {}).get("name") or "")), request_id=request_id, versioned=versioned)
        if method == "GET" and path.endswith("/analytics"):
            return response(200, analytics(actor, role), request_id=request_id, versioned=versioned)
        if method == "GET" and path.endswith("/reports"):
            return response(200, analytics(actor, role), request_id=request_id, versioned=versioned)
        if method == "GET" and path.endswith("/campaigns"):
            return response(200, campaigns({}, actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and path.endswith("/campaigns"):
            return response(201, campaigns(body, actor, role, create=True), request_id=request_id, versioned=versioned)
        if method == "POST" and path.endswith("/batches"):
            return response(201, create_batch(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and path.endswith("/projects"):
            return response(201, create_project(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "GET" and path.endswith("/projects"):
            require_role(role, "MUNICIPAL_OFFICER", "ADMIN")
            return response(200, list_projects(), request_id=request_id, versioned=versioned)
        if method == "POST" and "/projects/" in path and path.endswith("/approval"):
            return response(200, approve_project(path.split("/projects/", 1)[1].removesuffix("/approval"), body, actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and "/projects/" in path and path.endswith("/allocate"):
            return response(200, allocate_project_material(path.split("/projects/", 1)[1].removesuffix("/allocate"), body, actor, role), request_id=request_id, versioned=versioned)
        if method == "PATCH" and "/projects/" in path:
            return response(200, update_project_status(path.split("/projects/", 1)[1], body, actor, role), request_id=request_id, versioned=versioned)
        if method in {"PATCH", "PUT"} and "/batches/" in path:
            return response(200, update_batch(path.split("/batches/", 1)[1], body, actor, role), request_id=request_id, versioned=versioned)
        if method == "GET" and path.endswith("/matches"):
            return response(200, matches(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and "/matches/" in path and path.endswith("/accept"):
            return response(200, matches(body, actor, role, path.split("/matches/", 1)[1].removesuffix("/accept")), request_id=request_id, versioned=versioned)
        if method == "PUT" and path.endswith("/partners/me"):
            return response(200, partner(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "PATCH" and "/partners/" in path and path.endswith("/verification"):
            return response(200, verify_partner(path.split("/partners/", 1)[1].removesuffix("/verification"), body, actor, role), request_id=request_id, versioned=versioned)
        if method == "GET" and path.endswith("/centers"):
            return response(200, centers(), request_id=request_id, versioned=versioned)
        if method == "GET" and (path.endswith("/collection-centers") or path.endswith("/collection-centers/nearby")):
            return response(200, centers(), request_id=request_id, versioned=versioned)
        if method == "POST" and path.endswith("/centers"):
            return response(201, create_center(body, actor, role), request_id=request_id, versioned=versioned)
        if method == "GET" and path.endswith("/profile"):
            return response(200, profile(actor, role), request_id=request_id, versioned=versioned)
        if method == "POST" and path.endswith("/chat"):
            if versioned and versioned_route == "/copilot/query":
                require_role(role, "MUNICIPAL_OFFICER", "ADMIN")
            return response(200, chat(body, actor, role), request_id=request_id, versioned=versioned)
        return error_response(404, "NOT_FOUND", "Route not found", request_id, versioned)
    except PermissionError as exc:
        return error_response(403, "FORBIDDEN", str(exc), request_id, versioned)
    except (ValueError, RuntimeError) as exc:
        return error_response(400, "VALIDATION_ERROR", str(exc), request_id, versioned)
    except ClientError:
        return error_response(502, "AWS_SERVICE_ERROR", "AWS service request failed", request_id, versioned)
    except (KeyError, TypeError) as exc:
        return error_response(500, "INTERNAL_ERROR", f"Malformed AWS response: {exc}", request_id, versioned)
