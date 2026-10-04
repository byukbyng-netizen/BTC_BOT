"""Safe, exchange-agnostic state and configuration layer for the dashboard."""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "market": "BTC/USDT",
    "timeframe": "15m",
    "risk_per_trade_pct": 0.5,
    "daily_loss_limit_pct": 2.0,
    "max_position_pct": 25.0,
    "paper_trading": True,
    "strategy_enabled": False,
}
ALLOWED_TIMEFRAMES = {"1m", "5m", "15m", "1h", "4h", "1d"}


def can_start_live(config: dict[str, Any], confirmation: str | None) -> bool:
    """Require an explicit out-of-band confirmation before live mode."""
    return bool(config.get("paper_trading", True)) or confirmation == "I_UNDERSTAND_LIVE_TRADING"


def validate_config(values: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    timeframe = values.get("timeframe", DEFAULT_CONFIG["timeframe"])
    if timeframe not in ALLOWED_TIMEFRAMES:
        errors["timeframe"] = "지원하지 않는 타임프레임입니다."
    numeric_limits = {
        "risk_per_trade_pct": (0.01, 2.0),
        "daily_loss_limit_pct": (0.1, 20.0),
        "max_position_pct": (1.0, 100.0),
    }
    for key, (low, high) in numeric_limits.items():
        if key not in values:
            continue
        try:
            number = float(values[key])
        except (TypeError, ValueError):
            errors[key] = "숫자여야 합니다."
            continue
        if not low <= number <= high:
            errors[key] = f"{low} 이상 {high} 이하만 허용됩니다."
    if float(values.get("daily_loss_limit_pct", DEFAULT_CONFIG["daily_loss_limit_pct"])) < float(
        values.get("risk_per_trade_pct", DEFAULT_CONFIG["risk_per_trade_pct"])
    ):
        errors["daily_loss_limit_pct"] = "일일 손실 한도는 거래당 리스크 이상이어야 합니다."
    return errors


class ConfigStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = Lock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return copy.deepcopy(DEFAULT_CONFIG)
            return {**DEFAULT_CONFIG, **json.loads(self.path.read_text(encoding="utf-8"))}

    def update(self, values: dict[str, Any]) -> dict[str, Any]:
        candidate = {**self.load(), **values}
        errors = validate_config(candidate)
        if errors:
            raise ValueError(json.dumps(errors, ensure_ascii=False))
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
        return candidate


class DashboardState:
    def __init__(self, market_client=None, market: str = "USDT-BTC", event_store=None):
        self._mode = "stopped"
        self._market_client = market_client
        self._market = market
        self._live = {}
        self._paper = None
        self._events: list[dict[str, Any]] = []
        self._event_store = event_store
        self._lock = Lock()

    def refresh_market(self):
        if self._market_client is None:
            return
        try:
            row = self._market_client.ticker(self._market)[0]
            with self._lock:
                source_ms = row.get("timestamp")
                delay_ms = max(0.0, time.time() * 1000 - float(source_ms)) if source_ms else None
                self._live = {"price": row.get("trade_price"), "volume_24h": row.get("acc_trade_volume_24h"), "error": None, "latency_ms": round(delay_ms, 2) if delay_ms is not None else None}
                self._live["last_success_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            with self._lock:
                self._live = {"price": None, "volume_24h": None, "error": str(exc)}

    def set_paper_snapshot(self, snapshot: dict[str, Any]):
        with self._lock:
            self._paper = snapshot

    def record_event(self, message: str, level: str = "info"):
        if self._event_store:
            self._event_store.add(message, level=level)
        with self._lock:
            self._events.append({"time": datetime.now(timezone.utc).isoformat(), "level": level, "message": message})
            self._events = self._events[-50:]

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self._mode,
                "exchange": "upbit",
                "market": self._market,
                "price": self._live.get("price"),
                "volume_24h": self._live.get("volume_24h"),
                "position": self._paper.get("position") if self._paper else None,
                "pnl_today_pct": self._paper.get("total_return_pct", 0.0) if self._paper else 0.0,
                "last_event": self._live.get("error") or "실시간 시세 연결됨",
                "adapter": "rest",
                "paper": self._paper,
                "adapter_mode": "paper",
                "events": list(reversed(self._events[-20:])) if self._events else (self._event_store.recent(20) if self._event_store else []),
            }

    def connectivity(self):
        return {"api": {"ok": self._live.get("error") is None and self._live.get("price") is not None, "last_success_at": self._live.get("last_success_at"), "error": self._live.get("error")}, "market_data": {"ok": self._live.get("price") is not None, "last_success_at": self._live.get("last_success_at"), "latency_ms": self._live.get("latency_ms"), "error": self._live.get("error")}, "running": self._mode == "paper"}

    def control(self, action: str) -> dict[str, Any]:
        if action not in {"start", "pause", "stop"}:
            raise ValueError("지원하지 않는 제어 명령입니다.")
        with self._lock:
            self._mode = {"start": "paper", "pause": "paused", "stop": "stopped"}[action]
        self.record_event({"start": "페이퍼 엔진 시작", "pause": "페이퍼 엔진 일시정지", "stop": "봇 정지"}[action])
        return self.status()
