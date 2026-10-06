"""Deterministic recovery lifecycle and completion calculations."""

from decimal import Decimal

RECOVERY_STATUSES = (
    "COLLECTING", "VERIFIED", "READY_FOR_AGGREGATION", "READY_FOR_RECOVERY",
    "RESERVED", "PICKUP_SCHEDULED", "IN_TRANSIT", "RECEIVED", "PROCESSING",
    "RECOVERED", "CLOSED", "REJECTED",
)

ALLOWED_TRANSITIONS = {
    "COLLECTING": {"VERIFIED", "REJECTED"},
    "VERIFIED": {"READY_FOR_AGGREGATION", "READY_FOR_RECOVERY", "REJECTED"},
    "READY_FOR_AGGREGATION": {"READY_FOR_RECOVERY", "REJECTED"},
    "READY_FOR_RECOVERY": {"RESERVED", "REJECTED"},
    "RESERVED": {"PICKUP_SCHEDULED", "REJECTED"},
    "PICKUP_SCHEDULED": {"IN_TRANSIT", "REJECTED"},
    "IN_TRANSIT": {"RECEIVED", "REJECTED"},
    "RECEIVED": {"PROCESSING", "REJECTED"},
    "PROCESSING": {"RECOVERED", "REJECTED"},
    "RECOVERED": {"CLOSED"},
    "CLOSED": set(),
    "REJECTED": set(),
}


def validate_transition(previous: str, new: str) -> None:
    if new not in RECOVERY_STATUSES:
        raise ValueError(f"Unsupported recovery status: {new}")
    if previous == new:
        raise ValueError("Recovery status is already set")
    if new not in ALLOWED_TRANSITIONS.get(previous, set()):
        raise ValueError(f"Invalid recovery transition: {previous} -> {new}")


def completion_metrics(input_weight: Decimal, recovered_weight: Decimal, rejected_weight: Decimal) -> dict[str, Decimal]:
    if input_weight < 0 or recovered_weight < 0 or rejected_weight < 0:
        raise ValueError("Recovery weights cannot be negative")
    process_loss = input_weight - recovered_weight - rejected_weight
    if process_loss < 0:
        raise ValueError("Recovered and rejected weight cannot exceed input weight")
    return {
        "inputWeightKg": input_weight,
        "recoveredWeightKg": recovered_weight,
        "rejectedWeightKg": rejected_weight,
        "processLossKg": process_loss,
    }
