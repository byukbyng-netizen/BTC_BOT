#!/usr/bin/env python3
"""Read-only report client for the local BTC bot dashboard.

Only GET requests to an allowlist of paper-trading endpoints are made, and only
to a loopback host. This script never places orders, changes config, or
touches exchange credentials.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

ALLOWED_ENDPOINTS = {
    "status": "/api/status",
    "performance": "/api/performance",
    "trades": "/api/trades",
    "equity": "/api/equity",
    "events": "/api/events",
    "candles": "/api/candles",
}
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
SECRET_KEYS = {"access_key", "secret_key", "webhook", "webhook_url", "token", "api_key"}


def base_url() -> str:
    url = os.getenv("BTC_BOT_URL", "http://127.0.0.1:8765").rstrip("/")
    if urlparse(url).hostname not in LOOPBACK_HOSTS:
        raise SystemExit(f"refusing non-loopback BTC_BOT_URL: {url}")
    return url


def redact(value):
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in SECRET_KEYS else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def fetch(name: str, params: dict[str, str] | None = None, timeout: float = 10.0) -> dict:
    if name not in ALLOWED_ENDPOINTS:
        raise SystemExit(f"endpoint not allowed: {name}")
    query = f"?{urlencode(params)}" if params else ""
    with urlopen(f"{base_url()}{ALLOWED_ENDPOINTS[name]}{query}", timeout=timeout) as response:
        return redact(json.loads(response.read().decode("utf-8")))


def summary(start: str | None, end: str | None, event_limit: int) -> dict:
    params = {k: v for k, v in {"start": start, "end": end}.items() if v}
    status = fetch("status")
    performance = fetch("performance", params)
    events = fetch("events").get("events", [])[:event_limit]
    trades = performance.get("trades", [])
    for key in ("trades", "equity_curve", "drawdown_curve"):
        performance.pop(key, None)
    return {
        "status": status.get("status"),
        "scheduler": status.get("scheduler"),
        "connectivity": status.get("connectivity"),
        "paper_trading": (status.get("config") or {}).get("paper_trading"),
        "performance": performance,
        "recent_trades": trades[-10:],
        "recent_events": events,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["summary", *ALLOWED_ENDPOINTS])
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--events", type=int, default=20)
    parser.add_argument("--count", type=int, default=120, help="candles only")
    args = parser.parse_args(argv)
    try:
        if args.command == "summary":
            data = summary(args.start, args.end, args.events)
        elif args.command == "candles":
            data = fetch("candles", {"count": str(min(args.count, 200))})
        elif args.command in {"performance", "trades"}:
            data = fetch(args.command, {k: v for k, v in {"start": args.start, "end": args.end}.items() if v})
        else:
            data = fetch(args.command)
    except URLError as exc:
        print(json.dumps({"error": "bot_unreachable", "detail": str(exc.reason)}))
        return 2
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
