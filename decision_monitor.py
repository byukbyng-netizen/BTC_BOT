import json, time
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request

URL = 'http://127.0.0.1:8765/api/status'
last_count = None
while True:
    try:
        with urlopen(Request(URL), timeout=15) as r:
            d = json.load(r)
        sched = d.get('scheduler', {})
        count = sched.get('run_count')
        if last_count is None:
            last_count = count
        elif count != last_count:
            last_count = count
            p = d.get('status', {}).get('paper', {})
            now = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
            print('PAPER_DECISION: %s KST | run=%s | signal=%s | position_qty=%s | equity=%s | realized_pnl=%s | error=%s' % (
                now.strftime('%Y-%m-%d %H:%M:%S'), count, p.get('signal'),
                p.get('position', {}).get('quantity'), p.get('equity'),
                p.get('realized_pnl'), sched.get('last_error')), flush=True)
        if not sched.get('running') and last_count is not None:
            print('PAPER_DECISION: monitor stopped; scheduler is no longer running', flush=True)
            break
    except Exception as exc:
        print('PAPER_MONITOR_ERROR: %s' % exc, flush=True)
    time.sleep(10)
