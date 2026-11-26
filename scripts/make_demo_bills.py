r"""OPTIONAL. Creates about a month of generated demo bills on past store days so Sales analysis has something
to show. They are dated before every item's last stock count, so they cannot change any stock figure or
shrinkage flag. They are generated demo data, not real sales. scripts\reset_demo_bills.py removes them."""
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stockwise import billing, catalog

DAYS = 30
IST = timezone(timedelta(hours=5, minutes=30))
rng = random.Random(42)
con = sqlite3.connect(ROOT / "data" / "stockwise.db")

last_counts = [str(r[0])[:10] for r in con.execute("SELECT MAX(date) FROM stock_counts GROUP BY item_id")]
end = date.fromisoformat(min(last_counts)) - timedelta(days=1)
weights = {r[0]: max(float(r[1] or 0), 0.05) for r in con.execute("SELECT item_id, mean_daily_units FROM items")
           if r[0] in catalog.CATALOG}
ids = sorted(weights)
limits = billing.limits(con)
cashier = "cashier@demo.io"
if con.execute("SELECT 1 FROM users WHERE username=?", (cashier,)).fetchone() is None:
    sys.exit("The demo cashier account does not exist. Run scripts\\create_demo_users.py first.")

made = 0
for k in range(DAYS):
    day = (end - timedelta(days=DAYS - 1 - k)).isoformat()
    if con.execute("SELECT 1 FROM transactions WHERE day=?", (day,)).fetchone():
        continue
    n_bills = rng.randint(6, 14) + (4 if date.fromisoformat(day).weekday() >= 5 else 0)
    for n in range(1, n_bills + 1):
        picked = set(rng.choices(ids, weights=[weights[i] for i in ids], k=rng.randint(1, 4)))
        lines = []
        for item in sorted(picked):
            q = rng.randint(1, 3)
            if item in limits:
                q = min(q, int(limits[item]))
            lines.append((item, q))
        mode = rng.choices(billing.PAYMENT_MODES, weights=[40, 40, 20])[0]
        total = sum(catalog.CATALOG[i]["price"] * q for i, q in lines)
        when = datetime(int(day[:4]), int(day[5:7]), int(day[8:]), rng.randint(9, 20), rng.randint(0, 59), tzinfo=IST)
        txn = f"T{day.replace('-', '')}-{n:04d}"
        now = when.astimezone(timezone.utc).isoformat()
        con.execute("INSERT INTO transactions (txn_id, created_at, day, cashier, payment_mode, total) VALUES (?,?,?,?,?,?)",
                    (txn, now, day, cashier, mode, total))
        con.executemany("INSERT INTO transaction_items (txn_id, item_id, qty, unit_price) VALUES (?,?,?,?)",
                        [(txn, i, q, catalog.CATALOG[i]["price"]) for i, q in lines])
        con.execute("INSERT INTO audit_log (created_at, username, action, detail) VALUES (?,?,?,?)",
                    (now, cashier, "sale", f"{txn} {mode} total {total}"))
        made += 1
con.commit()
print(f"created {made} generated demo bills up to {end} (before every item's last stock count)")
print(r"remove them any time with: scripts\reset_demo_bills.py")