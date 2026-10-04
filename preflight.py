"""Non-trading readiness checks for the live transition."""
from __future__ import annotations

from typing import Any


def run_preflight(client: Any, market: str = "USDT-BTC") -> dict[str, Any]:
    checks: dict[str, Any] = {"market": market, "ready": False, "checks": {}}
    try:
        markets = client.market_all()
        client.validate_market(market, markets)
        checks["checks"]["market"] = {"ok": True, "value": market}
    except Exception as exc:
        checks["checks"]["market"] = {"ok": False, "error": str(exc)}
        return checks
    try:
        chance = client.order_chance(market)
        accounts = client.get_accounts()
        checks["checks"]["private_api"] = {"ok": True, "accounts": len(accounts), "has_order_policy": bool(chance)}
    except Exception as exc:
        checks["checks"]["private_api"] = {"ok": False, "error": str(exc)}
        return checks
    checks["ready"] = True
    return checks
