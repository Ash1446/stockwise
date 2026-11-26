"""Opens the Demand forecast page as each role, for several items, and fails on any exception."""
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from streamlit.testing.v1 import AppTest

con = sqlite3.connect(ROOT / "data" / "stockwise.db")
ids = [r[0] for r in con.execute("select item_id from items order by item_id")]
sample = [ids[0], ids[len(ids) // 3], ids[2 * len(ids) // 3], ids[-1]]

failed = False
for role, user in [("Admin", "admin@demo.io"), ("Cashier", "cashier@demo.io")]:
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
    at.session_state["user"] = {"username": user, "role": role}
    at.session_state["nav"] = "Demand forecast"
    at.run()
    for item in sample:
        at.selectbox(key="fc_item").set_value(item).run()
        errs = [e.value for e in at.exception]
        shown = any("Projected units" in m.value for m in at.markdown)
        ok = not errs and shown
        print(("PASS  " if ok else "FAIL  ") + f"{role}: {item}")
        for e in errs:
            print("      error:", e)
        failed = failed or not ok
sys.exit(1 if failed else 0)