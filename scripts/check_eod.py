"""End-of-day checks on a throwaway COPY of the database (your real data is not touched), plus page loads."""
import csv
import io
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from stockwise import auth, billing, catalog, eod, writeoffs

failed = False


def chk(name, ok, extra=""):
    global failed
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + str(extra)) if (extra and not ok) else ""))
    failed = failed or not ok


def refused(fn):
    try:
        fn()
    except eod.EodError as e:
        return str(e)
    return None


tmp = Path(tempfile.mkdtemp()) / "copy.db"
shutil.copy(ROOT / "data" / "stockwise.db", tmp)
con = sqlite3.connect(tmp)
ADMIN, CASH = "admin@demo.io", "cashier@demo.io"
A, B = "FOODS_3_050", "FOODS_2_267"
pA, pB = catalog.CATALOG[A]["price"], catalog.CATALOG[B]["price"]
for item in (A, B):
    d = con.execute("SELECT MAX(date) FROM stock_counts WHERE item_id=?", (item,)).fetchone()[0]
    con.execute("UPDATE stock_counts SET counted_stock=50 WHERE item_id=? AND date=?", (item, d))
con.commit()
day = billing.store_day(con)

chk("a day with no bills cannot be closed", "no bills" in (refused(lambda: eod.close_day(con, ADMIN, day)) or ""))
s0 = eod.summary(con, day)
chk("an empty day reports zeros", s0["bills"] == 0 and s0["units"] == 0 and s0["revenue"] == 0 and s0["top"] == [])

t1, _ = billing.record_sale(con, CASH, "Cash", [(A, 3), (B, 1)])
t2, _ = billing.record_sale(con, CASH, "UPI", [(A, 2)])
writeoffs.record_write_off(con, ADMIN, A, 2, "Damaged", "dropped")
writeoffs.record_write_off(con, ADMIN, A, 1, "Expired", "returned", t1)

s = eod.summary(con, day)
chk("bills, units and revenue add up", (s["bills"], s["units"], s["revenue"]) == (2, 6, 5 * pA + pB), s)
chk("payment split matches the bills", s["modes"]["Cash"] == (1, 3 * pA + pB) and s["modes"]["UPI"] == (1, 2 * pA)
    and s["modes"]["Card"] == (0, 0.0), s["modes"])
chk("payment modes add up to revenue", sum(a for _, a in s["modes"].values()) == s["revenue"])
chk("top item is the one sold most", s["top"][0][0] == A and s["top"][0][1] == 5, s["top"])
chk("write-offs are counted by reason and kind",
    (s["wo_entries"], s["damaged"], s["expired"], s["shelf_units"], s["bill_units"]) == (2, 2, 1, 2, 1), s)
chk("write-off value is price x units", s["wo_value"] == 3 * pA, s["wo_value"])
chk("net stock change is received - sold - shelf write-offs", s["net_change"] == s["received"] - 6 - 2, s["net_change"])

rows = list(csv.reader(io.StringIO(eod.bills_csv(con, day))))
chk("CSV has a header and one row per item sold", len(rows) == 4 and rows[0][0] == "bill", len(rows))
chk("CSV amounts add up to revenue", sum(float(r[9]) for r in rows[1:]) == s["revenue"])

before = con.execute("select count(*) from day_close").fetchone()[0]
chk("a cashier cannot close the day", refused(lambda: eod.close_day(con, CASH, day)) == "Only the manager can close the day.")
chk("an unknown user cannot close the day", refused(lambda: eod.close_day(con, "nobody@x.io", day)) is not None)
chk("a day other than the open one cannot be closed",
    "current store day" in (refused(lambda: eod.close_day(con, ADMIN, (date.fromisoformat(day) + timedelta(days=5)).isoformat())) or ""))
chk("refused closes saved nothing", con.execute("select count(*) from day_close").fetchone()[0] == before)

eod.close_day(con, ADMIN, day, "all matches")
info = eod.closed_info(con, day)
chk("closing saves who and the note", info and info[0] == ADMIN and info[2] == "all matches", info)
chk("closing the same day again is refused", "already closed" in (refused(lambda: eod.close_day(con, ADMIN, day)) or ""))
nxt = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
chk("the open store day moves forward", billing.store_day(con) == nxt, billing.store_day(con))
t3, _ = billing.record_sale(con, CASH, "Card", [(B, 1)])
chk("the next bill starts a new day at number 1", t3 == f"T{nxt.replace('-', '')}-0001", t3)
chk("the closed day's totals did not change", eod.summary(con, day)["bills"] == 2)
chk("the close is in the audit log", con.execute("select count(*) from audit_log where action='day_close'").fetchone()[0] == 1)
chk("cashier has no access to End of day", not auth.can_access("Cashier", "End of day"))
chk("admin has access to End of day", auth.can_access("Admin", "End of day"))
con.close()

from streamlit.testing.v1 import AppTest
at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
at.session_state["user"] = {"username": ADMIN, "role": "Admin"}
at.session_state["nav"] = "End of day"
at.run()
errs = [e.value for e in at.exception]
chk("Admin: the End of day page opens with a Close button", not errs and "Close the day" in [b.label for b in at.button], errs)
sys.exit(1 if failed else 0)