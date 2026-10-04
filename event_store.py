"""Persistent execution/event log."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from notifier import notify

class EventStore:
    def __init__(self, path: Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, time TEXT, level TEXT, event_type TEXT, message TEXT, payload TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS paper_trades (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, action TEXT, price REAL, quantity REAL, notional REAL, fee REAL, pnl REAL, cumulative_pnl REAL, reason TEXT, ema_fast REAL, ema_slow REAL, atr REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS paper_equity (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, equity REAL, drawdown_pct REAL, mark_price REAL)")
    def add(self, message: str, level="info", event_type="system", payload=None):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO events(time,level,event_type,message,payload) VALUES(?,?,?,?,?)", (datetime.now(timezone.utc).isoformat(), level, event_type, message, json.dumps(payload or {}, ensure_ascii=False)))
        if level in {"warning", "error", "action"}:
            notify(message)
    def recent(self, limit=50):
        with sqlite3.connect(self.path) as db:
            rows=db.execute("SELECT time,level,event_type,message,payload FROM events ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
        return [{"time":r[0],"level":r[1],"event_type":r[2],"message":r[3],"payload":json.loads(r[4])} for r in rows]

    def add_trade(self, trade):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO paper_trades(timestamp,action,price,quantity,notional,fee,pnl,cumulative_pnl,reason,ema_fast,ema_slow,atr) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", tuple(trade.get(k) for k in ("timestamp", "action", "price", "quantity", "notional", "fee", "pnl", "cumulative_pnl", "reason", "ema_fast", "ema_slow", "atr")))

    def add_equity(self, point):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO paper_equity(timestamp,equity,drawdown_pct,mark_price) VALUES(?,?,?,?)", tuple(point.get(k) for k in ("timestamp", "equity", "drawdown_pct", "mark_price")))

    def trades(self, limit=200):
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT timestamp,action,price,quantity,notional,fee,pnl,cumulative_pnl,reason,ema_fast,ema_slow,atr FROM paper_trades ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        keys = ("timestamp", "action", "price", "quantity", "notional", "fee", "pnl", "cumulative_pnl", "reason", "ema_fast", "ema_slow", "atr")
        return [dict(zip(keys, row)) for row in rows]

    def equity_curve(self, limit=500):
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT timestamp,equity,drawdown_pct,mark_price FROM paper_equity ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"timestamp": r[0], "equity": r[1], "drawdown_pct": r[2], "mark_price": r[3]} for r in reversed(rows)]
