"""SNS-triggered transactional email worker."""

import json
import hashlib
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from notification_templates import render

table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
cognito = boto3.client("cognito-idp")
ses = boto3.client("sesv2")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def recipient_email(user_id: str) -> str:
    response = cognito.admin_get_user(UserPoolId=os.environ["USER_POOL_ID"], Username=user_id)
    for attribute in response.get("UserAttributes", []):
        if attribute.get("Name") == "email" and attribute.get("Value"):
            return attribute["Value"]
    raise ValueError("User does not have a verified email address")


def group_users(group_name: str) -> list[str]:
    users = []
    token = None
    while True:
        kwargs = {"UserPoolId": os.environ["USER_POOL_ID"], "GroupName": group_name}
        if token:
            kwargs["NextToken"] = token
        page = cognito.list_users_in_group(**kwargs)
        users.extend(item["Username"] for item in page.get("Users", []) if item.get("Enabled", True))
        token = page.get("NextToken")
        if not token:
            return users


def handler(event, _context):
    failed = False
    for record in event.get("Records", []):
        message = json.loads(record["Sns"]["Message"])
        event_type = str(message.get("eventType") or "UNKNOWN")
        data = message.get("data") or {}
        recipients = list(message.get("userIds", []))
        for role in message.get("roles", []):
            recipients.extend(group_users(str(role)))
        for user_id in sorted(set(recipients)):
            message_id = str(record["Sns"].get("MessageId") or "")
            notification_id = hashlib.sha256(f"{message_id}|{user_id}|{event_type}".encode("utf-8")).hexdigest()
            created_at = now()
            subject, text = render(event_type, data)
            item = {
                "PK": f"NOTIFICATION#{notification_id}",
                "SK": "DETAILS",
                "entityType": "NOTIFICATION",
                "notificationId": notification_id,
                "userId": user_id,
                "type": event_type,
                "channel": "EMAIL",
                "subject": subject,
                "status": "PENDING",
                "createdAt": created_at,
            }
            existing = table.get_item(Key={"PK": item["PK"], "SK": item["SK"]}).get("Item")
            if existing and existing.get("status") == "SENT":
                continue
            table.put_item(Item=item)
            if os.environ.get("SES_ENABLED", "false").lower() != "true":
                continue
            try:
                email = recipient_email(user_id)
                ses.send_email(
                    FromEmailAddress=os.environ["SES_SENDER_EMAIL"],
                    Destination={"ToAddresses": [email]},
                    Content={"Simple": {"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": {"Text": {"Data": text, "Charset": "UTF-8"}}}},
                )
                table.update_item(
                    Key={"PK": item["PK"], "SK": item["SK"]},
                    UpdateExpression="SET #status=:status, sentAt=:sentAt",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={":status": "SENT", ":sentAt": now()},
                )
            except (ClientError, ValueError, KeyError) as exc:
                failed = True
                table.update_item(
                    Key={"PK": item["PK"], "SK": item["SK"]},
                    UpdateExpression="SET #status=:status, failureReason=:reason",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={":status": "FAILED", ":reason": str(exc)[:500]},
                )
    if failed:
        raise RuntimeError("One or more notification deliveries failed; SNS will retry the event")
    return {"processed": True}
