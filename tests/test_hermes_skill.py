import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".hermes/skills/btc-bot-monitor/scripts/btc_report.py"
spec = importlib.util.spec_from_file_location("btc_report", SCRIPT)
btc_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(btc_report)


def test_rejects_non_loopback_url(monkeypatch):
    monkeypatch.setenv("BTC_BOT_URL", "http://example.com:8765")
    with pytest.raises(SystemExit):
        btc_report.base_url()


def test_rejects_unlisted_endpoint():
    with pytest.raises(SystemExit):
        btc_report.fetch("control")


def test_allowlist_is_read_only():
    blocked = {"/api/control", "/api/config", "/api/paper/cycle", "/api/backtest", "/api/account", "/api/orders"}
    assert not blocked & set(btc_report.ALLOWED_ENDPOINTS.values())


def test_redacts_secrets():
    data = {"config": {"webhook_url": "https://hook", "paper_trading": True}, "items": [{"token": "x"}]}
    assert btc_report.redact(data) == {"config": {"webhook_url": "***", "paper_trading": True}, "items": [{"token": "***"}]}
