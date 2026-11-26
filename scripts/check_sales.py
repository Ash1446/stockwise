"""Sales analysis checks on a throwaway COPY of the database, plus the sidebar fix and page loads."""
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from stockwise import analysis, auth, billing, catalog

failed = False


def chk(name, ok, extra=""):
    global failed
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + str(extra)) if (extra and not ok) else ""))
    failed = failed or not ok


tmp = Path(tempfile.mkdtemp()) / "copy.db"
shutil.copy(ROOT / "data" / "stockwise.db", tmp)
con = sqlite3.connect(tmp)
con.execute("DELETE FROM transaction_items")
con.execute("DELETE FROM transactions")
con.commit()
A, B = "FOODS_3_050", "FOODS_2_267"
pA, pB = catalog.CATALOG[A]["price"], catalog.CATALOG[B]["price"]
grpA, grpB = catalog.CATALOG[A]["group"], catalog.CATALOG[B]["group"]
nth = {}


def bill(day, cashier, mode, lines):
    nth[day] = nth.get(day, 0) + 1
    txn = f"X{day.replace('-', '')}-{nth[day]:04d}"
    total = sum(catalog.CATALOG[i]["price"] * q for i, q in lines)
    con.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?)", (txn, f"{day}T10:00:00+00:00", day, cashier, mode, total))
    con.executemany("INSERT INTO transaction_items VALUES (?,?,?,?)", [(txn, i, q, catalog.CATALOG[i]["price"]) for i, q in lines])


bill("2016-05-30", "cashier@demo.io", "Cash", [(B, 2)])
bill("2016-06-02", "cashier@demo.io", "UPI", [(B, 1)])
bill("2016-06-04", "cashier@demo.io", "Cash", [(A, 2)])
bill("2016-06-08", "cashier@demo.io", "UPI", [(A, 1), (B, 3)])
bill("2016-06-10", "cashier@demo.io", "Cash", [(B, 1)])
bill("2016-06-10", "cashier2@demo.io", "Card", [(A, 4)])
con.commit()

chk("the anchor is the latest day with bills", analysis.anchor_day(con) == "2016-06-10")
chk("today", analysis.bounds("Today", "2016-06-10") == ("2016-06-10", "2016-06-10"))
chk("this week is the last 7 days", analysis.bounds("This week", "2016-06-10") == ("2016-06-04", "2016-06-10"))
chk("this month starts on the 1st", analysis.bounds("This month", "2016-06-10") == ("2016-06-01", "2016-06-10"))
chk("a custom range works in either order", analysis.bounds("Custom", "2016-06-10", ("2016-06-10", "2016-06-04")) == ("2016-06-04", "2016-06-10"))
chk("the previous 7 days", analysis.previous("2016-06-04", "2016-06-10") == ("2016-05-28", "2016-06-03"))
chk("the previous single day", analysis.previous("2016-06-10", "2016-06-10") == ("2016-06-09", "2016-06-09"))

s = analysis.summary(analysis.lines(con, "2016-06-10", "2016-06-10"))
chk("today: bills, units, revenue", (s["bills"], s["units"], s["revenue"]) == (2, 5, pB + 4 * pA), s)
chk("today: average bill", abs(s["average"] - (pB + 4 * pA) / 2) < 1e-9)
wk = analysis.lines(con, "2016-06-04", "2016-06-10")
s = analysis.summary(wk)
chk("this week", (s["bills"], s["units"], s["revenue"]) == (4, 11, 7 * pA + 4 * pB), s)
mo = analysis.summary(analysis.lines(con, "2016-06-01", "2016-06-10"))
chk("this month includes the earlier June bill", (mo["bills"], mo["revenue"]) == (5, 7 * pA + 5 * pB), mo)
pv = analysis.summary(analysis.lines(con, "2016-05-28", "2016-06-03"))
chk("the previous week", (pv["bills"], pv["revenue"]) == (2, 3 * pB), pv)
chk("percentage change", abs(analysis.pct_change(110, 100) - 10) < 1e-9 and analysis.pct_change(5, 0) is None)

d = analysis.daily(wk, "2016-06-04", "2016-06-10")
chk("the daily series has one row per day", len(d) == 7, len(d))
chk("days with no bills are zero", d.loc[d["day"] == "2016-06-05", "revenue"].iloc[0] == 0)
chk("daily revenue adds up to the week", d["revenue"].sum() == 7 * pA + 4 * pB)
pay = analysis.by_payment(wk)
chk("payment split adds up and includes unused modes", pay["amount"].sum() == 7 * pA + 4 * pB and set(pay.index) == set(billing.PAYMENT_MODES))
grp = analysis.by_group(wk)
chk("department split adds up", grp["amount"].sum() == 7 * pA + 4 * pB)
top = analysis.top_items(wk, 8)
chk("top item is the one sold most", top.iloc[0]["item_id"] == A and top.iloc[0]["units"] == 7, top.head(2).to_dict("records"))
cashiers = analysis.by_cashier(wk)
chk("cashier split", set(cashiers.index) == {"cashier@demo.io", "cashier2@demo.io"} and cashiers["amount"].sum() == 7 * pA + 4 * pB)
chk("an empty period summarises to zero", analysis.summary(analysis.lines(con, "2015-01-01", "2015-01-02"))["bills"] == 0)
con.close()

chk("cashier has no access to Sales analysis", not auth.can_access("Cashier", "Sales analysis"))
chk("admin has access to Sales analysis", auth.can_access("Admin", "Sales analysis"))
chk("Upload data is gone from every role", all("Upload data" not in p for p in auth.PAGES.values()))

from app import htmlpage
page = htmlpage.build("dashboard", "Admin")
chk("the HTML sidebar is hidden in its own style block", ".side{display:none!important}" in page and page.count("<style>") == 2, page.count("<style>"))

from streamlit.testing.v1 import AppTest
at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
at.session_state["user"] = {"username": "admin@demo.io", "role": "Admin"}
at.session_state["nav"] = "Sales analysis"
at.run()
errs = [e.value for e in at.exception]
chk("Admin: Sales analysis opens", not errs, errs)
pick = [r for r in at.radio if r.key == "sa_period"]
if pick:
    for p in analysis.PERIODS:
        pick[0].set_value(p).run()
        errs = [e.value for e in at.exception]
        chk(f"Admin: Sales analysis opens for {p}", not errs, errs)
else:
    print("INFO  no bills in the real database yet, so the period picker is not shown (run make_demo_bills.py or make a bill)")
at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
at.session_state["user"] = {"username": "admin@demo.io", "role": "Admin"}
at.run()
radios = [r for r in at.sidebar.radio]
chk("Admin sidebar has no Upload data page", radios and "Upload data" not in list(radios[0].options), list(radios[0].options) if radios else "")
sys.exit(1 if failed else 0)