"""Exchange-free paper execution engine."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Position:
    quantity: float
    entry_price: float
    stop_price: float
    cost: float
    take_profit_price: float | None = None


@dataclass(frozen=True)
class Execution:
    accepted: bool
    action: str
    quantity: float = 0.0
    reason: str = ""


class PaperEngine:
    def __init__(self, initial_quote: float = 1000.0, fee_rate: float = 0.0005, event_store=None):
        self.initial_quote = float(initial_quote)
        self.quote_balance = float(initial_quote)
        self.base_balance = 0.0
        self.fee_rate = float(fee_rate)
        self.position: Position | None = None
        self.realized_pnl = 0.0
        self.trades: list[dict[str, Any]] = []
        self.equity_curve: list[dict[str, float]] = []
        self.event_store = event_store

    def execute(self, action: str, price: float, risk_amount: float | None = None, stop_price: float | None = None, take_profit_price: float | None = None, reason: str = "", timestamp: str | None = None, indicators: dict | None = None) -> Execution:
        price = float(price)
        if price <= 0:
            return Execution(False, action, reason="invalid_price")
        if action == "buy":
            if self.position is not None:
                return Execution(False, action, reason="position_already_open")
            if stop_price is None or stop_price >= price:
                return Execution(False, action, reason="invalid_stop")
            risk = float(risk_amount or 0)
            distance = price - float(stop_price)
            quantity = min(risk / distance, self.quote_balance / (price * (1 + self.fee_rate)))
            if quantity <= 0:
                return Execution(False, action, reason="insufficient_quote")
            cost = quantity * price
            fee = cost * self.fee_rate
            self.quote_balance -= cost + fee
            self.position = Position(quantity, price, float(stop_price), cost, take_profit_price)
            self._record_trade({"action": "buy", "price": price, "quantity": quantity, "notional": cost, "fee": fee, "pnl": 0.0, "reason": reason}, timestamp, indicators)
            return Execution(True, action, quantity, "opened")
        if action == "sell":
            if self.position is None:
                return Execution(False, action, reason="no_position")
            position = self.position
            proceeds = position.quantity * price
            fee = proceeds * self.fee_rate
            self.quote_balance += proceeds - fee
            self.realized_pnl += (proceeds - fee) - position.cost - (position.cost * self.fee_rate)
            self.base_balance = 0.0
            self.position = None
            pnl = round((proceeds - fee) - position.cost - (position.cost * self.fee_rate), 8)
            self._record_trade({"action": "sell", "price": price, "quantity": position.quantity, "notional": proceeds, "fee": fee, "reason": reason, "entry_price": position.entry_price, "pnl": pnl}, timestamp, indicators)
            return Execution(True, action, position.quantity, "closed")
        return Execution(False, action, reason="unsupported_action")

    def _record_trade(self, trade, timestamp, indicators):
        trade = {**trade, "timestamp": timestamp or __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), "cumulative_pnl": round(self.realized_pnl, 8)}
        for key in ("ema_fast", "ema_slow", "atr"):
            trade[key] = (indicators or {}).get(key)
        self.trades.append(trade)
        if self.event_store:
            self.event_store.add_trade(trade)

    def snapshot(self, mark_price: float, timestamp: str | None = None) -> dict[str, Any]:
        mark_price = float(mark_price)
        unrealized = 0.0
        quantity = 0.0
        entry_price = None
        if self.position:
            quantity = self.position.quantity
            entry_price = self.position.entry_price
            unrealized = (mark_price - entry_price) * quantity
        equity = self.quote_balance + (quantity * mark_price)
        point = {"timestamp": timestamp or "", "equity": round(equity, 8), "mark_price": mark_price}
        if not self.equity_curve or self.equity_curve[-1] != point:
            self.equity_curve.append(point)
            if self.event_store:
                peak = max(float(p["equity"]) for p in self.equity_curve)
                self.event_store.add_equity({**point, "drawdown_pct": round((peak - equity) / peak * 100, 8) if peak else 0.0})
        return {
            "quote_balance": round(self.quote_balance, 8),
            "base_balance": round(quantity, 8),
            "equity": round(equity, 8),
            "realized_pnl": round(self.realized_pnl, 8),
            "unrealized_pnl": round(unrealized, 8),
            "position": {"quantity": quantity, "entry_price": entry_price, "stop_price": self.position.stop_price if self.position else None, "take_profit_price": self.position.take_profit_price if self.position else None},
            "trade_count": len(self.trades),
            "trades": list(reversed(self.trades[-50:])),
            "fees_paid": round(sum(float(t.get("fee", 0)) for t in self.trades), 8),
        }

    def performance(self, mark_price: float, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        """Return paper-only performance metrics for the requested candle period."""
        snapshot = self.snapshot(mark_price)
        curve = [p for p in self.equity_curve if (not start or p["timestamp"] >= start) and (not end or p["timestamp"] <= end)]
        if not curve:
            curve = [{"timestamp": "", "equity": self.initial_quote, "mark_price": mark_price}, {"timestamp": "", "equity": snapshot["equity"], "mark_price": mark_price}]
        peak = float(curve[0]["equity"])
        max_drawdown = 0.0
        for point in curve:
            peak = max(peak, float(point["equity"]))
            max_drawdown = max(max_drawdown, (peak - float(point["equity"])) / peak if peak else 0.0)
        filtered_trades = [t for t in self.trades if (not start or t.get("timestamp", "") >= start) and (not end or t.get("timestamp", "") <= end)]
        closed = [t for t in filtered_trades if t["action"] == "sell"]
        wins = [t for t in closed if float(t.get("pnl", 0)) > 0]
        losses = [t for t in closed if float(t.get("pnl", 0)) < 0]
        return {
            "period": {"start": start, "end": end},
            "initial_equity": round(self.initial_quote, 8),
            "equity": snapshot["equity"],
            "final_equity": snapshot["equity"],
            "total_return_pct": round((snapshot["equity"] / self.initial_quote - 1) * 100, 8),
            "realized_pnl": snapshot["realized_pnl"],
            "unrealized_pnl": snapshot["unrealized_pnl"],
            "fees_paid": snapshot["fees_paid"],
            "trade_count": len(closed),
            "win_rate_pct": round(len(wins) / len(closed) * 100, 8) if closed else 0.0,
            "average_win": round(sum(float(t.get("pnl", 0)) for t in wins) / len(wins), 8) if wins else 0.0,
            "average_loss": round(sum(float(t.get("pnl", 0)) for t in losses) / len(losses), 8) if losses else 0.0,
            "max_drawdown_pct": round(max_drawdown * 100, 8),
            "open_position": snapshot["position"],
            "trades": list(reversed(filtered_trades[-100:])),
            "equity_curve": list(self.equity_curve),
            "drawdown_curve": [{"timestamp": p["timestamp"], "drawdown_pct": round((max(float(x["equity"]) for x in self.equity_curve[:i+1]) - float(p["equity"])) / max(float(x["equity"]) for x in self.equity_curve[:i+1]) * 100, 8) if self.equity_curve[:i+1] else 0.0} for i, p in enumerate(self.equity_curve)],
        }
