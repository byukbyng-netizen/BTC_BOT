"""Optional webhook notifications for important bot events."""
from __future__ import annotations
import json, os
from urllib.request import Request, urlopen

def notify(message: str):
    url=os.getenv('BTC_BOT_ALERT_WEBHOOK_URL')
    if not url: return False
    payload=json.dumps({'text': message}, ensure_ascii=False).encode()
    try:
        req=Request(url, data=payload, headers={'Content-Type':'application/json'}, method='POST')
        with urlopen(req, timeout=5): return True
    except Exception:
        return False
