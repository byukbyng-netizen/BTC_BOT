"""Optional Upbit WebSocket market-data adapter.

Install `websocket-client` to enable live streaming. The dashboard can still use
REST polling when the optional dependency is absent.
"""
from __future__ import annotations

import json
import threading
import uuid
from typing import Callable, Any

WS_URL = "wss://api.upbit.com/websocket/v1"


class UpbitWebSocket:
    def __init__(self, market: str, on_event: Callable[[dict[str, Any]], None], url: str = WS_URL):
        self.market, self.on_event, self.url = market, on_event, url
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        try:
            import websocket
        except ImportError as exc:
            raise RuntimeError("WebSocket 사용에는 websocket-client 설치가 필요합니다.") from exc
        self._thread = threading.Thread(target=self._run, name="upbit-ws", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        import websocket
        ws = websocket.create_connection(self.url, timeout=10)
        try:
            ws.send(json.dumps([
                {"ticket": str(uuid.uuid4())},
                {"type": "ticker", "codes": [self.market], "isOnlyRealtime": True},
                {"format": "DEFAULT"},
            ]))
            while not self._stop.is_set():
                ws.settimeout(2)
                try:
                    message = ws.recv()
                except Exception:
                    continue
                if message:
                    if isinstance(message, bytes):
                        message = message.decode("utf-8")
                    self.on_event(json.loads(message))
        finally:
            ws.close()
