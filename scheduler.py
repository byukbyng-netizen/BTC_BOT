"""Background paper-cycle scheduler."""
from __future__ import annotations
import threading
from datetime import datetime, timezone, timedelta

class PaperScheduler:
    def __init__(self, cycle, interval_seconds=900, duration_seconds=None, on_complete=None):
        self.cycle=cycle; self.interval_seconds=interval_seconds; self._stop=threading.Event(); self._thread=None
        self.duration_seconds=duration_seconds; self.on_complete=on_complete; self.started_at=None
        self.last_run_at=None; self.next_run_at=None; self.last_error=None; self.run_count=0
    def start(self):
        if self._thread and self._thread.is_alive(): return False
        self._stop.clear(); self.started_at=datetime.now(timezone.utc); self._thread=threading.Thread(target=self._run, name='paper-scheduler', daemon=True); self._thread.start(); return True
    def stop(self):
        self._stop.set()
        self.next_run_at = None
    def status(self):
        return {"running": bool(self._thread and self._thread.is_alive() and not self._stop.is_set()), "interval_seconds": self.interval_seconds, "duration_seconds": self.duration_seconds, "started_at": self.started_at.isoformat() if self.started_at else None, "last_run_at": self.last_run_at, "next_run_at": self.next_run_at, "last_error": self.last_error, "run_count": self.run_count}
    def _run(self):
        while not self._stop.is_set():
            if self.duration_seconds and self.started_at and (datetime.now(timezone.utc)-self.started_at).total_seconds() >= self.duration_seconds:
                self._stop.set()
                if self.on_complete: self.on_complete()
                break
            self.last_run_at = datetime.now(timezone.utc).isoformat()
            try:
                self.cycle(); self.last_error = None; self.run_count += 1
            except Exception as exc:
                self.last_error = str(exc)
            self.next_run_at = (datetime.now(timezone.utc) + timedelta(seconds=self.interval_seconds)).isoformat()
            self._stop.wait(self.interval_seconds)
