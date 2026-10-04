import unittest

from paper_engine import PaperEngine
from strategy import EmaAtrStrategy


def candles(closes):
    rows=[]
    for i, close in enumerate(closes):
        rows.append({"timestamp": i, "open": close, "high": close + 2, "low": close - 2, "close": close, "volume": 10})
    return rows


class StrategyTests(unittest.TestCase):
    def test_returns_no_signal_until_enough_history(self):
        strategy = EmaAtrStrategy(fast_period=3, slow_period=5, atr_period=3)
        result = strategy.evaluate(candles([1, 2, 3]))
        self.assertEqual(result.action, "hold")

    def test_upward_cross_emits_buy_with_stop(self):
        strategy = EmaAtrStrategy(fast_period=3, slow_period=5, atr_period=3)
        result = strategy.evaluate(candles([100, 103, 106, 105, 100, 101, 98, 99, 94, 95, 92, 97, 98]))
        self.assertEqual(result.action, "buy")
        self.assertGreater(result.stop_price, 0)
        self.assertGreater(result.take_profit_price, result.entry_price)


class PaperEngineTests(unittest.TestCase):
    def test_buy_then_stop_closes_position_and_records_pnl(self):
        engine = PaperEngine(initial_quote=1000, fee_rate=0.001)
        opened = engine.execute("buy", price=100, risk_amount=10, stop_price=90)
        self.assertTrue(opened.accepted)
        self.assertIsNotNone(engine.position)
        closed = engine.execute("sell", price=110, reason="take_profit")
        self.assertTrue(closed.accepted)
        self.assertIsNone(engine.position)
        self.assertGreater(engine.snapshot(110)["realized_pnl"], 0)

    def test_rejects_second_entry_while_position_open(self):
        engine = PaperEngine(initial_quote=1000)
        self.assertTrue(engine.execute("buy", 100, risk_amount=10, stop_price=90).accepted)
        self.assertFalse(engine.execute("buy", 101, risk_amount=10, stop_price=90).accepted)

    def test_performance_reports_fee_return_win_rate_and_drawdown(self):
        engine = PaperEngine(initial_quote=1000, fee_rate=0.001)
        engine.execute("buy", 100, risk_amount=10, stop_price=90)
        engine.snapshot(100, "1")
        engine.execute("sell", 110, reason="take_profit")
        report = engine.performance(110)
        self.assertEqual(report["trade_count"], 1)
        self.assertEqual(report["win_rate_pct"], 100.0)
        self.assertGreater(report["fees_paid"], 0)
        self.assertGreater(report["total_return_pct"], 0)


if __name__ == "__main__":
    unittest.main()
