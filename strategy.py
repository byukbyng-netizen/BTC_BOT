"""Deterministic EMA/ATR strategy used by paper trading."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Signal:
    action: str = "hold"
    entry_price: float | None = None
    stop_price: float | None = None
    take_profit_price: float | None = None
    reason: str = "insufficient_data"
    fast_ema: float | None = None
    slow_ema: float | None = None
    atr: float | None = None


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append((value * alpha) + (result[-1] * (1 - alpha)))
    return result


def _atr(rows: list[dict[str, Any]], period: int) -> float:
    if len(rows) < 2:
        return 0.0
    true_ranges = []
    for previous, current in zip(rows, rows[1:]):
        high, low = float(current["high"]), float(current["low"])
        previous_close = float(previous["close"])
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    window = true_ranges[-period:]
    return sum(window) / len(window) if window else 0.0


def enrich_candles(rows: list[dict[str, Any]], strategy: "EmaAtrStrategy" | None = None) -> list[dict[str, Any]]:
    """Return candle rows with EMA/ATR diagnostics and signal markers."""
    strategy = strategy or EmaAtrStrategy()
    closes = [float(row["close"]) for row in rows]
    fast = _ema(closes, strategy.fast_period)
    slow = _ema(closes, strategy.slow_period)
    result = []
    for index, row in enumerate(rows):
        window = rows[: index + 1]
        signal = strategy.evaluate(window) if len(window) >= max(strategy.slow_period, strategy.atr_period) + 1 else Signal()
        item = dict(row)
        item.update({
            "ema_fast": fast[index] if index < len(fast) else None,
            "ema_slow": slow[index] if index < len(slow) else None,
            "atr": _atr(window, strategy.atr_period) if len(window) > 1 else 0.0,
            "signal": signal.action if signal.action != "hold" else None,
        })
        result.append(item)
    return result


class EmaAtrStrategy:
    def __init__(self, fast_period: int = 20, slow_period: int = 80, atr_period: int = 14, stop_atr: float = 2.0, take_profit_atr: float = 3.0):
        self.fast_period, self.slow_period, self.atr_period = fast_period, slow_period, atr_period
        self.stop_atr, self.take_profit_atr = stop_atr, take_profit_atr

    def evaluate(self, rows: list[dict[str, Any]]) -> Signal:
        minimum = max(self.slow_period, self.atr_period) + 1
        if len(rows) < minimum:
            return Signal(reason="insufficient_data")
        closes = [float(row["close"]) for row in rows]
        fast, slow = _ema(closes, self.fast_period), _ema(closes, self.slow_period)
        atr = _atr(rows, self.atr_period)
        entry = closes[-1]
        crossed_up = fast[-2] <= slow[-2] and fast[-1] > slow[-1]
        crossed_down = fast[-2] >= slow[-2] and fast[-1] < slow[-1]
        if crossed_up:
            return Signal("buy", entry, entry - (atr * self.stop_atr), entry + (atr * self.take_profit_atr), "ema_cross_up", fast[-1], slow[-1], atr)
        if crossed_down:
            return Signal("sell", entry, reason="ema_cross_down", fast_ema=fast[-1], slow_ema=slow[-1], atr=atr)
        return Signal(reason="hold", fast_ema=fast[-1], slow_ema=slow[-1], atr=atr)
