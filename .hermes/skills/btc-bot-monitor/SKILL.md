---
name: btc-bot-monitor
description: Use when asked about the BTC bot's state, paper-trading performance, recent trades, signals, errors, or for a periodic report. Read-only — never trades or changes settings.
version: 1.0.0
platforms: [macos, linux]
metadata:
  hermes:
    tags: [btc, trading, upbit, paper-trading, report, monitoring]
    requires_toolsets: [terminal]
---

# BTC Bot Monitor (read-only)

The bot at `/Users/johan/Project/BTC-BOT` trades Upbit `USDT-BTC` with a deterministic
EMA(20/80) cross + ATR stop/take-profit strategy (`strategy.py`). **Signals and orders are
decided by that code, not by you.** Your job is to read its state and explain it.

## Hard rules

- Use only `scripts/btc_report.py`. Do not call the HTTP API with curl or any other tool.
- Never send POST requests (`/api/control`, `/api/config`, `/api/paper/cycle`, `/api/backtest`).
- Never read `.env`, `data/config.json` secrets, or print API keys / webhook URLs.
- Never recommend a specific buy/sell action as advice. Describe what the strategy did and why.
- If a parameter change seems worthwhile, propose it as a suggestion for the human to apply
  and back-test with `backtest.py`; do not apply it.

## Commands

Run from the project root (dashboard must be running: `python3 server.py`):

```bash
python3 .hermes/skills/btc-bot-monitor/scripts/btc_report.py summary
python3 .hermes/skills/btc-bot-monitor/scripts/btc_report.py summary --start 2026-10-01 --end 2026-10-04
python3 .hermes/skills/btc-bot-monitor/scripts/btc_report.py trades
python3 .hermes/skills/btc-bot-monitor/scripts/btc_report.py events
python3 .hermes/skills/btc-bot-monitor/scripts/btc_report.py candles --count 120
```

`summary` returns status, scheduler, connectivity, paper/live mode, performance metrics
(return, realized/unrealized PnL, win rate, trade count, max drawdown, fees), the last 10
trades, and recent events. Exit code 2 with `{"error": "bot_unreachable"}` means the
dashboard is not running — say so instead of guessing.

## Report format

1. One-line status: running/paused/stopped, paper or live, last successful data time.
2. Performance for the period: return %, PnL, win rate, trades, max drawdown, fees.
3. Notable trades: entry/exit, reason (`ema_cross_up`, `ema_cross_down`, stop, take-profit).
4. Problems: connectivity errors, repeated error events, stale data, scheduler not running.
5. Optional observations (e.g. many whipsaw losses → wider EMA gap worth back-testing),
   clearly labelled as suggestions.

Keep numbers as reported by the bot; do not recompute or estimate them.
