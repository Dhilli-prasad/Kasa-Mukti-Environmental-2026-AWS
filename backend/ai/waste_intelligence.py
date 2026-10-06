"""Provider-neutral waste image analysis contract.

Providers return untrusted model output. ``normalize_analysis`` is the trust
boundary that validates enums, caps uncertain confidence, and derives manual
verification requirements before persistence.
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol

from ai.risk_engine import WasteRiskEngine

CATEGORIES = {
    "organic", "paper", "cardboard", "plastic", "glass", "metal", "e-waste",
    "battery", "sanitary", "agricultural-container", "mixed", "unknown",
}
MATERIAL_TYPES = {
    "PET", "HDPE", "LDPE", "PP", "PVC", "glass", "aluminum", "steel",
    "paper", "cardboard", "electronic", "unknown",
}
HAZARD_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
PATHWAYS = {
    "ORIGINAL_PRODUCER", "RECYCLER", "REUSE_PARTNER", "VERIFIED_UPCYCLER",
    "SPECIALIZED_TREATMENT", "RESIDUAL",
}


class WasteClassifier(Protocol):
    name: str

    def classify(self, *, media_type: str, image_bytes: bytes) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class WasteAnalysis:
    category: str
    materialType: str
    manufacturer: str | None
    productName: str | None
    hazardLevel: str
    confidence: float
    recommendedPathway: str
    requiresManualVerification: bool
    explanation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "materialType": self.materialType,
            "manufacturer": self.manufacturer,
            "productName": self.productName,
            "hazardLevel": self.hazardLevel,
            "confidence": self.confidence,
            "recommendedPathway": self.recommendedPathway,
            "requiresManualVerification": self.requiresManualVerification,
            "explanation": self.explanation,
        }


@dataclass
class BedrockWasteClassifier:
    client: Any
    model_id: str
    name: str = "amazon-bedrock"

    def classify(self, *, media_type: str, image_bytes: bytes) -> dict[str, Any]:
        import base64

        request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 800,
            "temperature": 0,
            "system": """You are a waste intelligence classifier. Return ONLY JSON.
Use exactly these keys: category, materialType, manufacturer, productName, hazardLevel,
confidence, recommendedPathway, explanation.
category must be one of organic, paper, cardboard, plastic, glass, metal, e-waste,
battery, sanitary, agricultural-container, mixed, unknown.
materialType must be one of PET, HDPE, LDPE, PP, PVC, glass, aluminum, steel, paper,
cardboard, electronic, unknown.
hazardLevel must be LOW, MEDIUM, HIGH, or CRITICAL.
recommendedPathway must be one of ORIGINAL_PRODUCER, RECYCLER, REUSE_PARTNER,
VERIFIED_UPCYCLER, SPECIALIZED_TREATMENT, RESIDUAL.
Never guess a manufacturer or product. Use null when unreadable. Confidence must be
between 0 and 1 and must reflect visual evidence. Use unknown/LOW confidence when uncertain.
Treat pesticide/agricultural chemical containers, batteries, medical/sanitary risk,
fuel/pressurised containers, and unknown hazardous containers as HIGH or CRITICAL.""",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": f"image/{media_type}", "data": base64.b64encode(image_bytes).decode("ascii")}},
                    {"type": "text", "text": "Analyze this waste image."},
                ],
            }],
        }
        result = self.client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request),
        )
        payload = json.loads(result["body"].read())
        text = payload.get("content", [{}])[0].get("text", "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Waste classifier returned invalid JSON") from exc


@dataclass
class MockWasteClassifier:
    """Deterministic local provider for development and contract tests."""

    name: str = "mock"

    def classify(self, *, media_type: str, image_bytes: bytes) -> dict[str, Any]:
        return {
            "category": "unknown",
            "materialType": "unknown",
            "manufacturer": None,
            "productName": None,
            "hazardLevel": "LOW",
            "confidence": 0.0,
            "recommendedPathway": "RESIDUAL",
            "explanation": "The local mock provider does not identify real materials. Manual review is required.",
        }


def _text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def normalize_analysis(raw: dict[str, Any]) -> WasteAnalysis:
    if not isinstance(raw, dict):
        raise RuntimeError("Waste classifier returned a non-object")
    category = str(raw.get("category") or "unknown").strip().lower()
    material_type = str(raw.get("materialType") or "unknown").strip()
    material_type = material_type if material_type in MATERIAL_TYPES else "unknown"
    hazard = str(raw.get("hazardLevel") or "HIGH").strip().upper()
    legacy_hazards = {"NONE": "LOW", "MODERATE": "MEDIUM", "CRITICAL": "CRITICAL"}
    hazard = legacy_hazards.get(hazard, hazard)
    if category not in CATEGORIES:
        category = "unknown"
    if hazard not in HAZARD_LEVELS:
        hazard = "HIGH"
    try:
        confidence = float(raw.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    if category == "unknown" or material_type == "unknown":
        confidence = min(confidence, 0.59)
    pathway = str(raw.get("recommendedPathway") or "RESIDUAL").strip().upper()
    if pathway not in PATHWAYS:
        pathway = "SPECIALIZED_TREATMENT" if hazard in {"HIGH", "CRITICAL"} else "RESIDUAL"
    risk = WasteRiskEngine().evaluate(raw)
    if risk["riskLevel"] in {"HIGH", "CRITICAL"}:
        hazard = risk["riskLevel"]
    requires_manual = bool(raw.get("requiresManualVerification", False))
    requires_manual = requires_manual or risk["requiresManualVerification"] or confidence < 0.6 or category == "unknown"
    explanation = _text(raw.get("explanation")) or "The material could not be identified with sufficient certainty."
    return WasteAnalysis(
        category=category,
        materialType=material_type,
        manufacturer=_text(raw.get("manufacturer")),
        productName=_text(raw.get("productName")),
        hazardLevel=hazard,
        confidence=confidence,
        recommendedPathway=pathway,
        requiresManualVerification=requires_manual,
        explanation=explanation,
    )
