"""Assign newly confirmed users to the safe default citizen group."""

import boto3
from notification_events import publish_notification


client = boto3.client("cognito-idp")


def handler(event, _context):
    client.admin_add_user_to_group(
        UserPoolId=event["userPoolId"],
        Username=event["userName"],
        GroupName="CITIZEN",
    )
    publish_notification("ACCOUNT_WELCOME", user_id=event["userName"], data={})
    return event
