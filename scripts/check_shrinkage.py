"""Shrinkage page: loads for both roles, filters work, save logic works on a throwaway database."""
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from streamlit.testing.v1 import AppTest
from app.views import shrinkage

failed = False


def report(name, ok, extra=""):
    global failed
    print(("PASS  " if ok else "FAIL  ") + name)
    if extra:
        print("      " + extra)
    failed = failed or not ok


for role, user in [("Admin", "admin@demo.io"), ("Cashier", "cashier@demo.io")]:
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
    at.session_state["user"] = {"username": user, "role": role}
    at.session_state["nav"] = "Shrinkage detection"
    at.run()
    errs = [e.value for e in at.exception]
    has_kpi = any("Flagged days" in m.value for m in at.markdown)
    buttons = [b.label for b in at.button]
    if role == "Admin":
        ok = not errs and has_kpi and "Save review" in buttons
    else:
        ok = not errs and has_kpi and "Save review" not in buttons
    report(f"{role}: page loads, save button {'shown' if role == 'Admin' else 'hidden'}", ok, "; ".join(errs))

    for label, value in [("sh_window", "All flagged days"), ("sh_status_filter", "All"), ("sh_window", "Last 90 days")]:
        at.selectbox(key=label).set_value(value).run()
    errs = [e.value for e in at.exception]
    report(f"{role}: filters change without errors", not errs, "; ".join(errs))

con = sqlite3.connect(":memory:")
con.executescript("""
CREATE TABLE investigations (item_id TEXT NOT NULL, date TEXT NOT NULL, status TEXT, note TEXT, updated_at TEXT, PRIMARY KEY (item_id, date));
CREATE TABLE audit_log (created_at TEXT NOT NULL, username TEXT, action TEXT, detail TEXT);
""")
shrinkage.save_review(con, "admin@demo.io", "X_1", "2016-01-08", "investigated", "checked shelf")
row = con.execute("select status, note from investigations").fetchone()
report("save: investigated with note is stored", row == ("investigated", "checked shelf"))
shrinkage.save_review(con, "admin@demo.io", "X_1", "2016-01-08", "dismissed", "")
report("save: changing status updates the same row", con.execute("select count(*), max(status) from investigations").fetchone() == (1, "dismissed"))
shrinkage.save_review(con, "admin@demo.io", "X_1", "2016-01-08", "open", "")
report("save: reopening removes the review", con.execute("select count(*) from investigations").fetchone()[0] == 0)
report("save: every change is in the audit log", con.execute("select count(*) from audit_log where action='shrinkage_review'").fetchone()[0] == 3)

sys.exit(1 if failed else 0)