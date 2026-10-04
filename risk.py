"""Risk limits for paper and future live execution."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class RiskGuard:
    daily_loss_limit_pct: float = 2.0
    max_position_pct: float = 25.0
    starting_equity: float = 1000.0
    daily_realized_pnl: float = 0.0
    halted: bool = False

    def check_entry(self, equity: float, notional: float) -> tuple[bool, str]:
        if self.halted:
            return False, "risk_halted"
        if equity <= 0 or notional > equity * (self.max_position_pct / 100):
            return False, "max_position_limit"
        if self.daily_realized_pnl <= -(self.starting_equity * self.daily_loss_limit_pct / 100):
            self.halted = True
            return False, "daily_loss_limit"
        return True, "ok"

    def record_pnl(self, pnl: float):
        self.daily_realized_pnl += float(pnl)
        if self.daily_realized_pnl <= -(self.starting_equity * self.daily_loss_limit_pct / 100):
            self.halted = True
