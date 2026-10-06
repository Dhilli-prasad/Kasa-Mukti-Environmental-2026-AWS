"""Deterministic recovery-pathway matching.

Partner records and batch records are treated as untrusted data. No model is
needed to decide eligibility; an optional AI layer may explain these results.
"""

from math import asin, cos, radians, sin, sqrt
from typing import Any


PARTNER_TYPES = {
    "ORIGINAL_PRODUCER", "RECYCLER", "REUSE_PARTNER", "UPCYCLER",
    "COMMUNITY_PROJECT", "SPECIALIZED_TREATMENT",
}
PATHWAY_PRIORITY = {
    "REUSE_PARTNER": 1,
    "RECYCLER": 2,
    "ORIGINAL_PRODUCER": 3,
    "UPCYCLER": 4,
    "COMMUNITY_PROJECT": 5,
    "SPECIALIZED_TREATMENT": 6,
}
HAZARDOUS_LEVELS = {"HIGH", "CRITICAL"}


def distance_km(origin: dict[str, Any] | None, destination: dict[str, Any] | None) -> float | None:
    if not origin or not destination:
        return None
    try:
        lat1, lon1 = float(origin["lat"]), float(origin["lng"])
        lat2, lon2 = float(destination["lat"]), float(destination["lng"])
    except (KeyError, TypeError, ValueError):
        return None
    radius = 6371.0
    delta_lat, delta_lon = radians(lat2 - lat1), radians(lon2 - lon1)
    value = sin(delta_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(delta_lon / 2) ** 2
    return round(2 * radius * asin(sqrt(value)), 2)


def _quality_ok(batch: dict[str, Any], partner: dict[str, Any]) -> bool:
    requirements = partner.get("qualityRequirements") or {}
    required = {str(value).upper() for value in requirements.get("acceptedStatuses", ["PASSED", "ACCEPTABLE"])}
    return str(batch.get("qualityStatus", "PENDING")).upper() in required


def _contamination_ok(batch: dict[str, Any], partner: dict[str, Any]) -> bool:
    limit = partner.get("contaminationLimit", partner.get("qualityRequirements", {}).get("maxContamination"))
    if limit is None:
        return str(batch.get("contaminationStatus", "UNKNOWN")).upper() != "CONTAMINATED"
    try:
        return float(batch.get("contaminationPercent", 0)) <= float(limit)
    except (TypeError, ValueError):
        return False


def match_batch(batch: dict[str, Any], partners: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only eligible partner pathways, ranked deterministically."""
    material = str(batch.get("materialType", "")).upper()
    quantity = float(batch.get("quantity", 0) or 0)
    hazard = str(batch.get("hazardLevel", "LOW")).upper()
    origin = batch.get("location") or batch.get("sourceLocation")
    results: list[dict[str, Any]] = []
    for partner in partners:
        partner_type = str(partner.get("partnerType") or "RECYCLER").upper()
        accepted = {str(value).upper() for value in partner.get("acceptedMaterials", [])}
        if partner_type not in PARTNER_TYPES or material not in accepted:
            continue
        if str(partner.get("verificationStatus", "")).upper() != "VERIFIED":
            continue
        if hazard in HAZARDOUS_LEVELS and partner_type not in {"SPECIALIZED_TREATMENT", "RECYCLER"}:
            continue
        accepted_hazards = {str(value).upper() for value in partner.get("acceptedHazardLevels", ["LOW", "MEDIUM"])}
        if hazard not in accepted_hazards and partner_type != "SPECIALIZED_TREATMENT":
            continue
        minimum = float(partner.get("minimumQuantity", 0) or 0)
        if quantity < minimum:
            continue
        if not _quality_ok(batch, partner) or not _contamination_ok(batch, partner):
            continue
        distance = distance_km(origin, partner.get("location"))
        radius = partner.get("serviceRadiusKm")
        if radius is not None and distance is not None and distance > float(radius):
            continue
        reason = (
            f"Verified {partner_type.lower().replace('_', ' ')} accepts {material}, "
            f"meets quantity and quality requirements"
        )
        if distance is not None:
            reason += f", {distance:g} km away"
        results.append({
            "partnerId": partner.get("partnerId"),
            "partnerName": partner.get("name"),
            "pathway": partner_type,
            "materialType": material,
            "quantity": quantity,
            "weightKg": batch.get("weightKg", 0),
            "distanceKm": distance,
            "priority": PATHWAY_PRIORITY[partner_type],
            "reason": reason,
        })
    return sorted(
        results,
        key=lambda item: (
            item["priority"],
            item["distanceKm"] if item["distanceKm"] is not None else float("inf"),
            str(item["partnerId"]),
        ),
    )
