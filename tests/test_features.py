import tempfile
import unittest
from pathlib import Path

from backtest import run_backtest
from event_store import EventStore
from paper_engine import PaperEngine
from strategy import EmaAtrStrategy, enrich_candles


class PaperPortfolioAndPersistenceTests(unittest.TestCase):
    def test_paper_portfolio_isolated_and_trade_fields_are_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            events = EventStore(Path(tmp) / "events.sqlite3")
            engine = PaperEngine(initial_quote=1000, fee_rate=0.001, event_store=events)
            engine.execute("buy", 100, risk_amount=10, stop_price=90, take_profit_price=120,
                           reason="ema_cross_up", timestamp="2026-01-01T00:00:00Z", indicators={"ema_fast": 101, "ema_slow": 99, "atr": 4})
            engine.snapshot(105, timestamp="2026-01-01T00:15:00Z")
            engine.execute("sell", 110, reason="take_profit", timestamp="2026-01-01T00:30:00Z", indicators={"ema_fast": 106, "ema_slow": 100, "atr": 4})
            trades = events.trades()
            self.assertEqual(len(trades), 2)
            self.assertEqual(trades[0]["timestamp"], "2026-01-01T00:30:00Z")
            self.assertIn("cumulative_pnl", trades[0])
            self.assertEqual(engine.snapshot(110)["quote_balance"] > 0, True)
            self.assertIn("equity_curve", engine.performance(110))

    def test_performance_has_average_win_loss(self):
        engine = PaperEngine(initial_quote=1000)
        engine.execute("buy", 100, risk_amount=10, stop_price=90)
        engine.execute("sell", 110, reason="take_profit")
        report = engine.performance(110)
        self.assertIn("average_win", report)
        self.assertIn("average_loss", report)


class ChartAndBacktestTests(unittest.TestCase):
    def test_enrich_candles_provides_ema_and_signal_fields(self):
        rows = [{"timestamp": str(i), "open": i + 1, "high": i + 3, "low": i - 1, "close": i + 1, "volume": 1} for i in range(1, 100)]
        enriched = enrich_candles(rows, EmaAtrStrategy(fast_period=3, slow_period=5, atr_period=3))
        self.assertIn("ema_fast", enriched[-1])
        self.assertIn("ema_slow", enriched[-1])
        self.assertIn("signal", enriched[-1])

    def test_backtest_has_detailed_period_and_curve(self):
        rows = [{"timestamp": f"2026-01-01T00:{i:02d}:00Z", "open": 100+i, "high": 102+i, "low": 98+i, "close": 100+i, "volume": 1} for i in range(100)]
        result = run_backtest(rows)
        for key in ("period", "final_equity", "average_win", "average_loss", "equity_curve", "drawdown_curve", "trades"):
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
