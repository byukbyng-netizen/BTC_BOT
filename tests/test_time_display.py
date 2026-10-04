import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class KSTDisplayTests(unittest.TestCase):
    def test_format_kst_handles_utc_date_boundary(self):
        script = """
const {formatKST} = require('./static/time.js');
process.stdout.write(JSON.stringify([
  formatKST('2026-01-01T15:30:45Z'),
  formatKST('2026-12-31T23:59:59Z'),
  formatKST(null)
]));
"""
        result = subprocess.run(
            ["node"], cwd=ROOT, input=script, text=True,
            capture_output=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout), [
            "2026-01-02 00:30:45 KST",
            "2027-01-01 08:59:59 KST",
            "-",
        ])

    def test_dashboard_formats_all_user_facing_timestamp_groups(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        for expression in (
            "formatKST(t.timestamp)",
            "formatKST(e.time)",
            "formatKST(co.api?.last_success_at)",
            "formatKST(co.market_data?.last_success_at)",
            "formatKST(sch.last_run_at)",
            "formatKST(sch.next_run_at)",
            "formatKST(d.period.start)",
            "formatKST(d.period.end)",
        ):
            self.assertIn(expression, html)
        self.assertNotIn("esc(t.timestamp)", html)
        self.assertNotIn("esc(e.time)", html)
        self.assertNotIn("d.period?.start||'-'", html)


if __name__ == "__main__":
    unittest.main()
