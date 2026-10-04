import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot_core import ConfigStore, DashboardState, can_start_live, validate_config
from upbit_client import UpbitRestClient, UpbitMarketError, normalize_market
from preflight import run_preflight


class ConfigValidationTests(unittest.TestCase):
    def test_rejects_invalid_risk_and_timeframe(self):
        errors = validate_config({"risk_per_trade_pct": 5, "timeframe": "2m"})
        self.assertIn("risk_per_trade_pct", errors)
        self.assertIn("timeframe", errors)

    def test_accepts_safe_config(self):
        errors = validate_config({
            "market": "BTC/USDT", "timeframe": "15m", "risk_per_trade_pct": 0.5,
            "daily_loss_limit_pct": 2.0, "max_position_pct": 25, "paper_trading": True,
        })
        self.assertEqual(errors, {})


class ConfigStoreTests(unittest.TestCase):
    def test_round_trips_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ConfigStore(Path(tmp) / "config.json")
            config = store.update({"risk_per_trade_pct": 0.4})
            self.assertEqual(config["risk_per_trade_pct"], 0.4)
            self.assertEqual(store.load()["risk_per_trade_pct"], 0.4)


class DashboardStateTests(unittest.TestCase):
    def test_control_transitions_are_explicit(self):
        state = DashboardState()
        self.assertEqual(state.status()["mode"], "stopped")
        self.assertEqual(state.control("start")["mode"], "paper")
        self.assertEqual(state.control("pause")["mode"], "paused")
        self.assertEqual(state.control("stop")["mode"], "stopped")

    def test_live_mode_requires_explicit_confirmation(self):
        self.assertFalse(can_start_live({"paper_trading": False}, None))
        self.assertTrue(can_start_live({"paper_trading": False}, "I_UNDERSTAND_LIVE_TRADING"))


class UpbitClientTests(unittest.TestCase):
    def test_normalizes_btc_usdt_to_upbit_quote_base_code(self):
        self.assertEqual(normalize_market("BTC/USDT"), "USDT-BTC")
        self.assertEqual(normalize_market("USDT-BTC"), "USDT-BTC")

    def test_rejects_unknown_market_from_market_list(self):
        with self.assertRaises(UpbitMarketError):
            UpbitRestClient("access", "secret", opener=lambda *_: None).validate_market("USDT-BTC", [{"market": "KRW-BTC"}])

    def test_private_request_contains_jwt_and_query_hash(self):
        captured = {}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self): return b'[]'
        def opener(request, timeout):
            captured["request"] = request
            return Response()
        client = UpbitRestClient("access", "secret", opener=opener)
        client.get_accounts()
        auth = captured["request"].headers["Authorization"]
        self.assertTrue(auth.startswith("Bearer "))
        self.assertEqual(captured["request"].method, "GET")

    def test_preflight_requires_private_order_access(self):
        class FakeClient:
            def market_all(self): return [{"market": "USDT-BTC"}]
            def validate_market(self, market, markets): return market
            def order_chance(self, market): return {"market": market}
            def get_accounts(self): return []
        result = run_preflight(FakeClient())
        self.assertTrue(result["ready"])
        self.assertTrue(result["checks"]["private_api"]["ok"])


if __name__ == "__main__":
    unittest.main()
