"""Small event publisher used by domain operations, not by the frontend."""

import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3

sns = boto3.client("sns")


def publish_notification(event_type: str, *, user_id: str | None = None, user_ids: list[str] | None = None, roles: list[str] | None = None, data: dict[str, Any] | None = None) -> None:
    if os.environ.get("NOTIFICATIONS_ENABLED", "false").lower() != "true":
        return
    recipients = [value for value in ([user_id] if user_id else []) + (user_ids or []) if value]
    if not recipients and not roles:
        return
    topic_arn = os.environ.get("NOTIFICATION_TOPIC_ARN", "").strip()
    if not topic_arn:
        raise RuntimeError("NOTIFICATION_TOPIC_ARN is required when notifications are enabled")
    sns.publish(
        TopicArn=topic_arn,
        Subject=f"KasaMukti event: {event_type}",
        Message=json.dumps({
            "eventType": event_type,
            "userIds": sorted(set(recipients)),
            "roles": sorted(set(roles or [])),
            "data": data or {},
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }, default=str),
    )
