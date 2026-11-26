r"""Removes the demo bills, write-offs and day closes that the app created, so stock goes back to the last
physical count. Write-offs and day closes are found through the audit log, so no other data is touched."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
con = sqlite3.connect(ROOT / "data" / "stockwise.db")
bills = con.execute("select count(*) from transactions").fetchone()[0]
wo_ids = [d.split()[0] for (d,) in con.execute("select detail from audit_log where action='write_off'")]
days = [d.split()[0] for (d,) in con.execute("select detail from audit_log where action='day_close'")]
con.execute("delete from transaction_items")
con.execute("delete from transactions")
con.executemany("delete from write_offs where write_off_id=?", [(i,) for i in wo_ids])
con.executemany("delete from day_close where day=?", [(d,) for d in days])
con.execute("delete from audit_log where action in ('sale','write_off','day_close')")
con.commit()
print(f"removed {bills} bills, {len(wo_ids)} write-offs and {len(days)} day closes; stock is back to the last physical count")