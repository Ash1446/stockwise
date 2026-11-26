"""Loads the whole app as each role and fails if any page raises an exception."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from streamlit.testing.v1 import AppTest

failed = False
for role, user in [("Admin", "admin@demo.io"), ("Cashier", "cashier@demo.io")]:
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
    at.session_state["user"] = {"username": user, "role": role}
    at.run()
    errs = [e.value for e in at.exception]
    labels = [r.label for r in at.sidebar.radio] if len(at.sidebar.radio) else []
    options = list(at.sidebar.radio[0].options) if len(at.sidebar.radio) else []
    ok = not errs
    if role == "Admin":
        ok = ok and any("sw-kpi" in m.value for m in at.markdown)
    print(("PASS  " if ok else "FAIL  ") + f"{role}: app loads, pages = {options}")
    for e in errs:
        print("      error:", e)
    failed = failed or not ok

sys.exit(1 if failed else 0)