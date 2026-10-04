"""Coordinates candles, strategy and paper execution without exchange orders."""
from __future__ import annotations

from market_data import CandleCollector
from paper_engine import PaperEngine
from strategy import EmaAtrStrategy
from risk import RiskGuard


class PaperRuntime:
    def __init__(self, collector: CandleCollector, initial_quote: float = 1000.0, risk_per_trade_pct: float = 0.5, event_store=None):
        self.collector = collector
        self.engine = PaperEngine(initial_quote=initial_quote, event_store=event_store)
        self.strategy = EmaAtrStrategy()
        self.risk_per_trade_pct = risk_per_trade_pct
        self.risk = RiskGuard(starting_equity=initial_quote)
        self.last_signal = None
        self.last_candle = None

    def cycle(self, market: str = "USDT-BTC", unit: int = 15):
        rows = self.collector.collect(market, unit=unit)
        self.last_candle = rows[-1] if rows else None
        if not self.last_candle:
            return {"signal": "hold", "reason": "no_candles", **self.engine.snapshot(0)}
        if self.engine.position:
            candle_low = float(self.last_candle["low"])
            candle_high = float(self.last_candle["high"])
            stop = self.engine.position.stop_price
            target = self.engine.position.take_profit_price
            if candle_low <= stop:
                self.engine.execute("sell", stop, reason="stop_loss", timestamp=str(self.last_candle["timestamp"]))
            elif target is not None and candle_high >= target:
                self.engine.execute("sell", target, reason="take_profit", timestamp=str(self.last_candle["timestamp"]))
        signal = self.strategy.evaluate(rows)
        self.last_signal = signal
        price = signal.entry_price or float(self.last_candle["close"])
        if signal.action == "buy":
            notional = self.engine.initial_quote * (self.risk_per_trade_pct / 100)
            allowed, reason = self.risk.check_entry(self.engine.snapshot(price)["equity"], notional)
            if allowed:
                self.engine.execute("buy", price, risk_amount=notional, stop_price=signal.stop_price, take_profit_price=signal.take_profit_price, reason=signal.reason, timestamp=str(self.last_candle["timestamp"]), indicators={"ema_fast": signal.fast_ema, "ema_slow": signal.slow_ema, "atr": signal.atr})
            else:
                signal = signal.__class__(action="hold", reason=reason, fast_ema=signal.fast_ema, slow_ema=signal.slow_ema, atr=signal.atr)
        elif signal.action == "sell":
            before = self.engine.realized_pnl
            self.engine.execute("sell", price, reason=signal.reason, timestamp=str(self.last_candle["timestamp"]), indicators={"ema_fast": signal.fast_ema, "ema_slow": signal.slow_ema, "atr": signal.atr})
            self.risk.record_pnl(self.engine.realized_pnl - before)
        snapshot = self.engine.snapshot(price, timestamp=str(self.last_candle["timestamp"]))
        snapshot.update({"signal": signal.action, "signal_reason": signal.reason, "last_candle": self.last_candle["timestamp"], "diagnostics": {"fast_ema": signal.fast_ema, "slow_ema": signal.slow_ema, "atr": signal.atr, "stop_price": signal.stop_price, "take_profit_price": signal.take_profit_price}})
        return snapshot

    def performance(self, start=None, end=None):
        price = float(self.last_candle["close"]) if self.last_candle else 0.0
        return self.engine.performance(price, start=start, end=end)
