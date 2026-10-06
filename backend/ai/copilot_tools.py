"""Read-only, authorized operational tools for the Municipal Copilot."""

MUNICIPAL_ROLES = {"MUNICIPAL_OFFICER", "ADMIN"}
TOOL_NAMES = {
    "getMaterialInventory", "getWardStatistics", "getHazardStatistics",
    "getRecoveryBatches", "getRecoveryPartners", "getRecoveryMatches",
    "getGreenPointStatistics", "getCollectionTrends", "getRecoveryImpact",
}


def authorize(role: str) -> None:
    if role not in MUNICIPAL_ROLES:
        raise PermissionError("Municipal Copilot tools require MUNICIPAL_OFFICER or ADMIN")


def run_tool(name: str, role: str, providers: dict):
    authorize(role)
    if name not in TOOL_NAMES or name not in providers:
        raise ValueError(f"Unsupported Copilot tool: {name}")
    return {"tool": name, "readOnly": True, "data": providers[name]()}
