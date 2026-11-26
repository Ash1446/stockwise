"""Write-off checks on a throwaway COPY of the database (your real data is not touched), plus page loads."""
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from stockwise import auth, billing, catalog, writeoffs

failed = False


def chk(name, ok, extra=""):
    global failed
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + str(extra)) if (extra and not ok) else ""))
    failed = failed or not ok


def refused(fn):
    try:
        fn()
    except writeoffs.WriteOffError as e:
        return str(e)
    return None


tmp = Path(tempfile.mkdtemp()) / "copy.db"
shutil.copy(ROOT / "data" / "stockwise.db", tmp)
con = sqlite3.connect(tmp)
ADMIN, CASH = "admin@demo.io", "cashier@demo.io"
A, B = "FOODS_3_050", "FOODS_1_141"


def n(table):
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


d = con.execute("SELECT MAX(date) FROM stock_counts WHERE item_id=?", (A,)).fetchone()[0]
con.execute("UPDATE stock_counts SET counted_stock=50 WHERE item_id=? AND date=?", (A, d))
con.commit()
day = billing.store_day(con)

t, _ = billing.record_sale(con, CASH, "Cash", [(A, 4)])
chk("stock after a 4-unit bill is 46", billing.stock_now(con)[A] == 46)

w1 = writeoffs.record_write_off(con, ADMIN, A, 3, "Damaged", "dropped")
chk("a shelf write-off reduces stock", billing.stock_now(con)[A] == 43)
chk("write-off IDs follow the store day", w1 == f"W{day.replace('-', '')}-0001", w1)
w2 = writeoffs.record_write_off(con, ADMIN, A, 2, "Expired")
chk("a second entry gets the next ID", w2.endswith("-0002"), w2)
chk("stock is 41 after both shelf write-offs", billing.stock_now(con)[A] == 41)

w3 = writeoffs.record_write_off(con, ADMIN, A, 1, "Damaged", "customer returned it", t)
chk("an item from a bill does not change stock", billing.stock_now(con)[A] == 41)
row = con.execute("select txn_id, reason, entered_by from write_offs where write_off_id=?", (w3,)).fetchone()
chk("it is linked to the bill and the manager", row == (t, "Damaged", ADMIN), row)
writeoffs.record_write_off(con, ADMIN, A, 3, "Damaged", "", t)
chk("all 4 units on the bill can be marked, no more", refused(lambda: writeoffs.record_write_off(con, ADMIN, A, 1, "Damaged", "", t)) is not None)
chk("stock adjustments are bills plus shelf write-offs only", billing.stock_adjustments(con)[A] == -9, billing.stock_adjustments(con)[A])

before = (n("write_offs"), n("audit_log"))
bad = {
    "a cashier cannot record a write-off": lambda: writeoffs.record_write_off(con, CASH, A, 1, "Damaged"),
    "an unknown user cannot record a write-off": lambda: writeoffs.record_write_off(con, "nobody@x.io", A, 1, "Damaged"),
    "a bad reason is refused": lambda: writeoffs.record_write_off(con, ADMIN, A, 1, "Lost"),
    "a zero quantity is refused": lambda: writeoffs.record_write_off(con, ADMIN, A, 0, "Damaged"),
    "a fractional quantity is refused": lambda: writeoffs.record_write_off(con, ADMIN, A, 1.5, "Damaged"),
    "more than the stock is refused": lambda: writeoffs.record_write_off(con, ADMIN, A, 999, "Damaged"),
    "an item that is not on the bill is refused": lambda: writeoffs.record_write_off(con, ADMIN, B, 1, "Damaged", "", t),
    "an unknown bill is refused": lambda: writeoffs.record_write_off(con, ADMIN, A, 1, "Damaged", "", "T00000000-9999"),
    "an unknown item is refused": lambda: writeoffs.record_write_off(con, ADMIN, "NOPE_1_001", 1, "Damaged"),
}
for name, fn in bad.items():
    chk(name, refused(fn) is not None, "was accepted")
chk("refused entries wrote nothing", (n("write_offs"), n("audit_log")) == before)
chk("stock is unchanged by refused entries", billing.stock_now(con)[A] == 41)
chk("every saved entry is in the audit log", con.execute("select count(*) from audit_log where action='write_off'").fetchone()[0] == 4)

tot = writeoffs.day_totals(con, day)
chk("today's totals add up", tot["entries"] == 4 and tot["units"] == 9
    and tot["value"] == 9 * catalog.CATALOG[A]["price"], tot)
chk("recent list returns newest first", writeoffs.recent(con, 3)[0][0] == f"W{day.replace('-', '')}-0004")
chk("cashier has no access to the Write-offs page", not auth.can_access("Cashier", "Write-offs"))
chk("admin has access to the Write-offs page", auth.can_access("Admin", "Write-offs"))
con.close()

from streamlit.testing.v1 import AppTest
at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=180)
at.session_state["user"] = {"username": ADMIN, "role": "Admin"}
at.session_state["nav"] = "Write-offs"
at.run()
errs = [e.value for e in at.exception]
chk("Admin: the Write-offs page opens with a Save button", not errs and "Save write-off" in [b.label for b in at.button], errs)
sys.exit(1 if failed else 0)