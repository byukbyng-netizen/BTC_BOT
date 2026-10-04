"""Local dashboard server. Bind to localhost until authentication is added."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bot_core import ConfigStore, DashboardState, can_start_live
from preflight import run_preflight
from upbit_client import UpbitRestClient
from market_data import CandleCollector, CandleStore
from strategy import enrich_candles
from paper_runtime import PaperRuntime
from event_store import EventStore
from scheduler import PaperScheduler
from backtest import run_backtest

ROOT = Path(__file__).parent


def load_local_env():
    """Load simple KEY=VALUE entries without adding a dotenv dependency."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_local_env()
store = ConfigStore(ROOT / "data" / "config.json")
event_store = EventStore(ROOT / "data" / "events.sqlite3")
client = UpbitRestClient(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
state = DashboardState(client, market="USDT-BTC", event_store=event_store)
collector = CandleCollector(client, CandleStore(ROOT / "data" / "market.sqlite3"))
paper_runtime = PaperRuntime(collector, event_store=event_store)

def run_paper_cycle():
    state.record_event("15분봉 수집 및 EMA/ATR 계산 시작")
    snapshot = paper_runtime.cycle("USDT-BTC", unit=15)
    state.set_paper_snapshot(snapshot)
    state.record_event(f"계산 완료: 신호={snapshot['signal']}, 실현손익={snapshot['realized_pnl']}")
    return snapshot

scheduler = PaperScheduler(lambda: run_paper_cycle() if state.status()["mode"] == "paper" else None, int(os.getenv("PAPER_INTERVAL_SECONDS", "900")), int(os.getenv("PAPER_DURATION_SECONDS", "0")) or None, lambda: state.control("stop"))


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: object, content_type: str = "application/json"):
        body = payload if isinstance(payload, bytes) else (
            json.dumps(payload, ensure_ascii=False).encode("utf-8") if content_type == "application/json" else str(payload).encode("utf-8")
        )
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, (ROOT / "static" / "index.html").read_bytes(), "text/html")
        elif path == "/static/time.js":
            self._send(200, (ROOT / "static" / "time.js").read_bytes(), "application/javascript")
        elif path == "/api/status":
            state.refresh_market()
            self._send(200, {"status": state.status(), "config": store.load(), "scheduler": scheduler.status(), "performance": paper_runtime.performance(), "connectivity": state.connectivity()})
        elif path == "/api/config":
            self._send(200, store.load())
        elif path == "/api/account":
            self._send(200, {"accounts": client.get_accounts()})
        elif path == "/api/orders":
            self._send(200, {"orders": client.orders("USDT-BTC")})
        elif path == "/api/portfolio":
            accounts = client.get_accounts()
            self._send(200, {"accounts": accounts, "market": "USDT-BTC", "paper": paper_runtime.engine.snapshot(state.status().get("price") or 0)})
        elif path == "/api/candles":
            query = parse_qs(urlparse(self.path).query)
            market = query.get("market", ["USDT-BTC"])[0]
            unit = int(query.get("unit", [15])[0])
            count = min(int(query.get("count", [120])[0]), 200)
            raw = client.candles(market, unit=unit, count=count)
            rows = [{"timestamp": r.get("candle_date_time_utc"), "open": r["opening_price"], "high": r["high_price"], "low": r["low_price"], "close": r["trade_price"], "volume": r.get("candle_acc_trade_volume", 0)} for r in reversed(raw)]
            self._send(200, {"market": market, "unit": unit, "candles": enrich_candles(rows)})
        elif path == "/api/preflight":
            self._send(200, run_preflight(client, "USDT-BTC"))
        elif path == "/api/events":
            self._send(200, {"events": event_store.recent(100)})
        elif path in {"/api/performance", "/api/report", "/api/trades", "/api/equity"}:
            query = parse_qs(urlparse(self.path).query)
            report = paper_runtime.performance(query.get("start", [None])[0], query.get("end", [None])[0])
            if path == "/api/trades":
                self._send(200, {"trades": report["trades"] if query.get("start", [None])[0] or query.get("end", [None])[0] else (event_store.trades() or report["trades"])})
            elif path == "/api/equity":
                self._send(200, {"equity_curve": event_store.equity_curve() or report["equity_curve"], "drawdown_curve": report["drawdown_curve"]})
            else:
                self._send(200, report)
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/config":
                self._send(200, store.update(payload))
            elif path == "/api/backtest":
                rows = collector.collect("USDT-BTC", unit=15, count=min(int(payload.get("count", 200)), 200))
                result = run_backtest(rows)
                state.record_event(f"백테스트 완료: 수익률={result['total_return_pct']}%, 거래={result['trade_count']}")
                self._send(200, result)
            elif path == "/api/control":
                action = payload.get("action", "")
                config = store.load()
                if action == "start" and not can_start_live(config, os.getenv("BTC_BOT_LIVE_CONFIRM")):
                    raise ValueError("실거래 시작은 BTC_BOT_LIVE_CONFIRM 확인값이 필요합니다.")
                result = state.control(action)
                if action == "start": scheduler.start()
                if action == "stop": scheduler.stop()
                self._send(200, result)
            elif path == "/api/paper/cycle":
                if state.status()["mode"] != "paper":
                    raise ValueError("먼저 페이퍼 트레이딩을 시작하세요.")
                snapshot = run_paper_cycle()
                self._send(200, snapshot)
            else:
                self._send(404, {"error": "not found"})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # keep error details out of production responses later
            self._send(500, {"error": str(exc)})

    def log_message(self, *_args):
        return


if __name__ == "__main__":
    host = os.getenv("BTC_BOT_HOST", "127.0.0.1")
    port = int(os.getenv("BTC_BOT_PORT", "8765"))
    print(f"BTC bot dashboard: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
