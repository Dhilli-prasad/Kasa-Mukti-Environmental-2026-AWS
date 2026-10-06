"""Seed a small, realistic KasaMukti demonstration dataset into DynamoDB.

This script is opt-in and writes only fixed demo keys. It does not clear a table.
Use it against a dedicated hackathon table, never a production table.
"""

import os
from decimal import Decimal

import boto3


TABLE_NAME = os.environ.get("TABLE_NAME", "KasaMuktiCore")
table = boto3.resource("dynamodb").Table(TABLE_NAME)


ITEMS = [
    {
        "PK": "CENTER#WARD12-CENTER",
        "SK": "PROFILE",
        "entityType": "COLLECTION_CENTER",
        "centerId": "WARD12-CENTER",
        "name": "Ward 12 Safe Recovery Hub",
        "address": "Kothapet Community Hall · 1.8 km",
        "acceptedMaterials": ["HDPE", "HAZARDOUS"],
        "acceptsHazardous": True,
        "openingHours": "Today · 08:00–18:00",
        "createdAt": "2026-10-05T08:00:00+05:30",
    },
    {
        "PK": "SCAN#KM-SCAN-042",
        "SK": "DETAILS",
        "entityType": "SCAN",
        "scanId": "KM-SCAN-042",
        "citizenId": "demo-citizen",
        "status": "VERIFIED",
        "workflowStatus": "BATCHED",
        "category": "agricultural-container",
        "materialType": "HDPE",
        "manufacturer": "AgroShield",
        "productName": "CropGuard 50 EC",
        "hazardLevel": "CRITICAL",
        "confidence": Decimal("0.94"),
        "verifiedWeight": Decimal("1.2"),
        "greenPoints": 120,
        "verifiedAt": "2026-10-05T09:18:00+05:30",
        "createdAt": "2026-10-05T08:42:00+05:30",
    },
    {
        "PK": "BATCH#KM-BATCH-042",
        "SK": "DETAILS",
        "entityType": "MATERIAL_BATCH",
        "batchId": "KM-BATCH-042",
        "materialType": "HDPE",
        "quantity": 1,
        "weightKg": Decimal("1.2"),
        "hazardLevel": "CRITICAL",
        "riskStatus": "SPECIAL_HANDLING",
        "qualityStatus": "PASSED",
        "contaminationStatus": "CLEAR",
        "workflowStatus": "READY_FOR_RECOVERY",
        "sourceCollectionCenters": ["WARD12-CENTER"],
        "eligibleRecoveryPathways": ["SPECIALIZED_TREATMENT"],
        "createdAt": "2026-10-05T09:23:00+05:30",
    },
    {
        "PK": "WALLET#demo-citizen",
        "SK": "PROFILE",
        "entityType": "WALLET",
        "citizenId": "demo-citizen",
        "greenPoints": 120,
        "lifetimeVerifiedKg": Decimal("1.2"),
        "updatedAt": "2026-10-05T09:18:00+05:30",
    },
]


def main() -> None:
    with table.batch_writer() as batch:
        for item in ITEMS:
            batch.put_item(Item=item)
    print(f"Seeded {len(ITEMS)} demo records into {TABLE_NAME}.")


if __name__ == "__main__":
    main()
