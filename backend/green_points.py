"""Verified GreenPoints domain rules and calculations.

The functions in this module are deterministic and do not depend on AWS, which
keeps reward policy testable and makes policy changes auditable.
"""

from dataclasses import dataclass
import json
import os
from typing import Any, Iterable


@dataclass(frozen=True)
class RewardRule:
    action: str
    base_points: int
    points_per_kg: int = 0
    max_points: int = 500
    requires_verification: bool = True


@dataclass(frozen=True)
class GreenPointTransaction:
    transactionId: str
    userId: str
    action: str
    points: int
    referenceId: str
    verifiedBy: str
    createdAt: str


@dataclass(frozen=True)
class UserGreenPointBalance:
    userId: str
    greenPoints: int
    lifetimeVerifiedKg: float = 0


@dataclass(frozen=True)
class Badge:
    id: str
    name: str


@dataclass(frozen=True)
class Leaderboard:
    entries: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class WardLeaderboard:
    ward: str
    entries: tuple[dict[str, Any], ...]


DEFAULT_REWARD_RULES: tuple[RewardRule, ...] = (
    RewardRule("VERIFIED_RECYCLABLE_DEPOSIT", 5, 10, 500),
    RewardRule("VERIFIED_SPECIAL_WASTE_DEPOSIT", 25, 25, 750),
    RewardRule("VERIFIED_AGRICULTURAL_CONTAINER_RETURN", 50, 0, 500),
    RewardRule("VERIFIED_COLLECTION_EVENT", 50, 0, 200),
    RewardRule("VERIFIED_ILLEGAL_DUMPING_REPORT", 100, 0, 100),
    RewardRule("APPROVED_ENVIRONMENTAL_CAMPAIGN", 75, 0, 150),
)


def configured_reward_rules() -> tuple[RewardRule, ...]:
    """Load an optional JSON policy, falling back to the reviewed defaults."""
    raw = os.environ.get("GREENPOINT_REWARD_RULES_JSON")
    if not raw:
        return DEFAULT_REWARD_RULES
    try:
        values = json.loads(raw)
        if not isinstance(values, list):
            raise ValueError
        rules = tuple(RewardRule(
            action=str(value["action"]),
            base_points=int(value["base_points"]),
            points_per_kg=int(value.get("points_per_kg", 0)),
            max_points=int(value.get("max_points", 500)),
            requires_verification=bool(value.get("requires_verification", True)),
        ) for value in values)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RewardError("GREENPOINT_REWARD_RULES_JSON is invalid") from exc
    return rules or DEFAULT_REWARD_RULES


class RewardError(ValueError):
    pass


def calculate_points(
    action: str,
    *,
    verified_weight_kg: float = 0,
    rules: Iterable[RewardRule] = DEFAULT_REWARD_RULES,
    verified: bool = True,
) -> int:
    rule = next((item for item in rules if item.action == action), None)
    if not rule:
        raise RewardError(f"Unknown reward action: {action}")
    if rule.requires_verification and not verified:
        raise RewardError("This environmental action requires verification")
    if verified_weight_kg < 0:
        raise RewardError("verified_weight_kg cannot be negative")
    points = rule.base_points + int(verified_weight_kg * rule.points_per_kg)
    return min(rule.max_points, max(0, points))


def action_for_verified_deposit(*, hazard_level: str, category: str) -> str:
    normalized_category = category.strip().lower()
    if normalized_category == "agricultural-container":
        return "VERIFIED_AGRICULTURAL_CONTAINER_RETURN"
    if hazard_level.upper() in {"HIGH", "CRITICAL"}:
        return "VERIFIED_SPECIAL_WASTE_DEPOSIT"
    return "VERIFIED_RECYCLABLE_DEPOSIT"


def leaderboard(wallets: Iterable[dict[str, Any]], *, ward: str | None = None) -> list[dict[str, Any]]:
    eligible = [wallet for wallet in wallets if ward is None or wallet.get("ward") == ward]
    ordered = sorted(
        eligible,
        key=lambda wallet: (-int(wallet.get("greenPoints", 0)), str(wallet.get("citizenId", ""))),
    )
    return [
        {
            "rank": index + 1,
            "userId": wallet.get("citizenId"),
            "greenPoints": int(wallet.get("greenPoints", 0)),
            **({"ward": wallet.get("ward")} if ward is None else {}),
        }
        for index, wallet in enumerate(ordered)
    ]


def badges_for(*, transaction_count: int, verified_deposits: int, points: int, special_returns: int) -> list[dict[str, str]]:
    badges: list[dict[str, str]] = []
    if verified_deposits >= 1:
        badges.append({"id": "first-deposit", "name": "First verified deposit"})
    if verified_deposits >= 5:
        badges.append({"id": "circular-champion", "name": "Circular champion"})
    if special_returns >= 1:
        badges.append({"id": "safe-return", "name": "Safe special-waste return"})
    if transaction_count >= 10 or points >= 1000:
        badges.append({"id": "green-guardian", "name": "Green guardian"})
    return badges
