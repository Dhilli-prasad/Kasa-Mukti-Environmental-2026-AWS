"""Safety gate and policy helpers for approved public-space projects."""

from dataclasses import dataclass
from typing import Any


PROHIBITED_CATEGORIES = {
    "battery", "e-waste", "sanitary", "agricultural-container",
    "chemical", "hazardous", "unknown",
}
PROHIBITED_MATERIALS = {"BATTERY", "ELECTRONIC", "E-WASTE", "HAZARDOUS", "CHEMICAL"}
PROJECT_STATUSES = {
    "PROPOSED", "PENDING_APPROVAL", "APPROVED", "MATERIAL_ALLOCATED",
    "IN_PROGRESS", "COMPLETED", "REJECTED",
}


@dataclass(frozen=True)
class MaterialRequirement:
    materialType: str
    estimatedQuantity: int
    estimatedWeightKg: float


@dataclass(frozen=True)
class CircularProject:
    projectId: str
    name: str
    description: str
    status: str
    approvalStatus: str


@dataclass(frozen=True)
class ProjectApproval:
    projectId: str
    decision: str
    approvedBy: str


@dataclass(frozen=True)
class ProjectImpact:
    projectId: str
    amountDivertedKg: float
    participatingCommunity: tuple[str, ...] = ()


def public_material_eligibility(batch: dict[str, Any]) -> dict[str, Any]:
    category = str(batch.get("category", "")).lower()
    material = str(batch.get("materialType", "")).upper()
    hazard = str(batch.get("hazardLevel", "LOW")).upper()
    contamination = str(batch.get("contaminationStatus", "UNKNOWN")).upper()
    quality = str(batch.get("qualityStatus", "PENDING")).upper()
    reasons: list[str] = []
    if hazard in {"MEDIUM", "HIGH", "CRITICAL"}:
        reasons.append("Material risk level is not approved for public installation")
    if category in PROHIBITED_CATEGORIES:
        reasons.append(f"Category '{category}' is prohibited")
    if material in PROHIBITED_MATERIALS:
        reasons.append(f"Material type '{material}' is prohibited")
    if contamination in {"CONTAMINATED", "UNKNOWN"}:
        reasons.append("Contamination status is not clear")
    if quality not in {"PASSED", "ACCEPTABLE"}:
        reasons.append("Material has not passed quality inspection")
    return {
        "eligible": not reasons,
        "reasons": reasons or ["Non-hazardous, quality-cleared material with clear contamination status"],
    }


def project_requirements_eligibility(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = []
    for requirement in requirements:
        material = str(requirement.get("materialType", "")).lower()
        if material in {"battery", "electronic", "e-waste", "sanitary", "hazardous", "chemical"}:
            reasons.append(f"Material type '{material}' is prohibited in public installations")
    return {"eligible": not reasons, "reasons": reasons or ["Requested material types are not inherently prohibited"]}
