"""Deterministic, verified waste-risk decisions.

This module is deliberately independent of any model provider. Model output is
treated as evidence only; matching a configured rule always wins over a
benign material classification.
"""

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class RiskRule:
    name: str
    keywords: frozenset[str]
    risk_level: str
    handling_category: str
    requires_special_handling: bool
    allowed_recovery_paths: tuple[str, ...]
    prohibited_paths: tuple[str, ...]


DEFAULT_RISK_RULES: tuple[RiskRule, ...] = (
    RiskRule(
        "pesticide-agricultural-chemical",
        frozenset({"pesticide", "agricultural chemical", "herbicide", "insecticide", "fungicide", "agrochemical"}),
        "CRITICAL", "AGRICULTURAL_CHEMICAL_CONTAINER", True,
        ("SPECIALIZED_TREATMENT", "ORIGINAL_PRODUCER"),
        ("RECYCLER", "REUSE_PARTNER", "VERIFIED_UPCYCLER", "PUBLIC_UPCYCLING", "RESIDUAL"),
    ),
    RiskRule(
        "chemical-container",
        frozenset({"chemical container", "corrosive", "solvent", "acid container", "caustic"}),
        "CRITICAL", "CHEMICAL_CONTAINER", True,
        ("SPECIALIZED_TREATMENT", "ORIGINAL_PRODUCER"),
        ("RECYCLER", "REUSE_PARTNER", "VERIFIED_UPCYCLER", "PUBLIC_UPCYCLING", "RESIDUAL"),
    ),
    RiskRule(
        "medical-sharps",
        frozenset({"medical", "sharps", "needle", "syringe", "biohazard", "clinical waste"}),
        "CRITICAL", "MEDICAL_SHARPS", True,
        ("SPECIALIZED_TREATMENT",),
        ("RECYCLER", "REUSE_PARTNER", "VERIFIED_UPCYCLER", "PUBLIC_UPCYCLING", "RESIDUAL"),
    ),
    RiskRule(
        "battery",
        frozenset({"battery", "lithium-ion", "lithium ion", "button cell", "lead-acid"}),
        "HIGH", "BATTERY_RETURN", True,
        ("SPECIALIZED_TREATMENT", "RECYCLER"),
        ("REUSE_PARTNER", "VERIFIED_UPCYCLER", "PUBLIC_UPCYCLING", "RESIDUAL"),
    ),
    RiskRule(
        "e-waste",
        frozenset({"e-waste", "electronic", "circuit board", "phone", "computer", "charger"}),
        "HIGH", "E_WASTE", True,
        ("RECYCLER", "SPECIALIZED_TREATMENT", "ORIGINAL_PRODUCER"),
        ("PUBLIC_UPCYCLING", "RESIDUAL"),
    ),
    RiskRule(
        "contaminated-container",
        frozenset({"contaminated", "residue", "chemical residue", "unwashed container", "unknown residue"}),
        "HIGH", "CONTAMINATED_CONTAINER", True,
        ("SPECIALIZED_TREATMENT",),
        ("RECYCLER", "REUSE_PARTNER", "VERIFIED_UPCYCLER", "PUBLIC_UPCYCLING", "RESIDUAL"),
    ),
    RiskRule(
        "unknown-hazardous-object",
        frozenset({"unknown hazardous", "hazardous object", "unknown container", "dangerous object"}),
        "HIGH", "UNKNOWN_HAZARDOUS_OBJECT", True,
        ("SPECIALIZED_TREATMENT",),
        ("RECYCLER", "REUSE_PARTNER", "VERIFIED_UPCYCLER", "PUBLIC_UPCYCLING", "RESIDUAL"),
    ),
)


class WasteRiskEngine:
    def __init__(self, rules: Iterable[RiskRule] = DEFAULT_RISK_RULES):
        self.rules = tuple(rules)

    def evaluate(self, evidence: dict[str, Any]) -> dict[str, Any]:
        haystack = " ".join(
            str(evidence.get(key, "")).lower()
            for key in ("category", "materialType", "manufacturer", "productName", "labelText", "explanation")
        )
        matched = next((rule for rule in self.rules if any(term in haystack for term in rule.keywords)), None)
        if matched:
            return self._result(matched)

        declared_hazard = str(evidence.get("hazardLevel", "")).upper()
        if declared_hazard in {"HIGH", "CRITICAL"}:
            fallback = RiskRule(
                "declared-hazard", frozenset(), declared_hazard, "UNKNOWN_HAZARDOUS_OBJECT", True,
                ("SPECIALIZED_TREATMENT",),
                ("RECYCLER", "REUSE_PARTNER", "VERIFIED_UPCYCLER", "PUBLIC_UPCYCLING", "RESIDUAL"),
            )
            return self._result(fallback)

        return {
            "riskLevel": "LOW" if declared_hazard != "MEDIUM" else "MEDIUM",
            "handlingCategory": "STANDARD_MATERIAL",
            "requiresSpecialHandling": False,
            "requiresManualVerification": declared_hazard == "MEDIUM",
            "allowedRecoveryPaths": ("RECYCLER", "REUSE_PARTNER", "VERIFIED_UPCYCLER"),
            "prohibitedPaths": ("OPEN_DUMPING", "BURNING"),
        }

    @staticmethod
    def _result(rule: RiskRule) -> dict[str, Any]:
        return {
            "riskLevel": rule.risk_level,
            "handlingCategory": rule.handling_category,
            "requiresSpecialHandling": rule.requires_special_handling,
            "requiresManualVerification": True,
            "allowedRecoveryPaths": rule.allowed_recovery_paths,
            "prohibitedPaths": rule.prohibited_paths,
        }
