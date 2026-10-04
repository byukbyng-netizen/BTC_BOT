"""Upbit candle collection with a small SQLite cache."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class CandleStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS candles (market TEXT, timeframe TEXT, timestamp TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, PRIMARY KEY (market, timeframe, timestamp))")

    def save(self, market: str, timeframe: str, rows: list[dict[str, Any]]) -> int:
        with sqlite3.connect(self.path) as db:
            before = db.total_changes
            db.executemany("INSERT OR REPLACE INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
                (market, timeframe, row["timestamp"], row["open"], row["high"], row["low"], row["close"], row["volume"]) for row in rows
            ])
            return db.total_changes - before

    def recent(self, market: str, timeframe: str, limit: int = 200) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT timestamp, open, high, low, close, volume FROM candles WHERE market=? AND timeframe=? ORDER BY timestamp DESC LIMIT ?", (market, timeframe, limit)).fetchall()
        return [{"timestamp": row[0], "open": row[1], "high": row[2], "low": row[3], "close": row[4], "volume": row[5]} for row in reversed(rows)]


class CandleCollector:
    def __init__(self, client, store: CandleStore):
        self.client, self.store = client, store

    def collect(self, market: str = "USDT-BTC", unit: int = 15, count: int = 200) -> list[dict[str, Any]]:
        raw = self.client.candles(market, unit=unit, count=count)
        rows = [{
            "timestamp": row.get("candle_date_time_utc") or row.get("timestamp"),
            "open": float(row["opening_price"]), "high": float(row["high_price"]),
            "low": float(row["low_price"]), "close": float(row["trade_price"]),
            "volume": float(row.get("candle_acc_trade_volume", row.get("acc_trade_volume", 0))),
        } for row in raw]
        rows.sort(key=lambda row: row["timestamp"])
        self.store.save(market, f"{unit}m", rows)
        return self.store.recent(market, f"{unit}m", count)
