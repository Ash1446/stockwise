"""Billing: record a sale, keep stock in step with it, and look items up by scanned code or name."""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from stockwise import catalog

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "stockwise.db"
PAYMENT_MODES = ["Cash", "Card", "UPI"]


class BillingError(Exception):
    pass


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def find_item(query):
    """Returns (item_id, "") when the code or name picks exactly one item, else (None, reason)."""
    q = _norm(query)
    if not q:
        return None, "Type or scan an item code or name."
    by_id = {_norm(i): i for i in catalog.CATALOG}
    if q in by_id:
        return by_id[q], ""
    names = {i: _norm(c["name"]) for i, c in catalog.CATALOG.items()}
    exact = [i for i, n in names.items() if n == q]
    if len(exact) == 1:
        return exact[0], ""
    part = [i for i, n in names.items() if q in n]
    if len(part) == 1:
        return part[0], ""
    if len(part) > 1:
        shown = ", ".join(catalog.CATALOG[i]["name"] for i in sorted(part)[:5])
        return None, f"Several items match: {shown}. Type more of the name or pick it from the list."
    return None, "No item matches that code or name."


_LAST_SQL = """
WITH last AS (SELECT item_id, MAX(date) AS d FROM stock_counts GROUP BY item_id)
SELECT l.item_id, c.counted_stock,
  COALESCE((SELECT SUM(x.units) FROM deliveries x WHERE x.item_id = l.item_id AND x.date > l.d), 0),
  COALESCE((SELECT SUM(ti.qty) FROM transaction_items ti JOIN transactions t ON t.txn_id = ti.txn_id
            WHERE ti.item_id = l.item_id AND t.day > l.d), 0)
  + COALESCE((SELECT SUM(w.qty) FROM write_offs w WHERE w.item_id = l.item_id AND w.txn_id IS NULL AND w.date > l.d), 0)
FROM last l JOIN stock_counts c ON c.item_id = l.item_id AND c.date = l.d
"""


def _state(con):
    return {r[0]: (r[1], r[2], r[3]) for r in con.execute(_LAST_SQL)}


def stock_now(con):
    """Units on hand: last physical count + deliveries after it - units billed after it."""
    return {i: (c or 0) + d - s for i, (c, d, s) in _state(con).items()}


def stock_adjustments(con=None):
    own = con is None
    if own:
        con = sqlite3.connect(DB_PATH)
    try:
        return {i: d - s for i, (c, d, s) in _state(con).items() if d or s}
    finally:
        if own:
            con.close()


def limits(con):
    return {r[0]: r[1] for r in con.execute(
        "SELECT item_id, purchase_limit FROM item_settings WHERE purchase_limit IS NOT NULL")}


def store_day(con):
    """The day bills are dated: the day after the latest data, skipping any day already closed."""
    row = con.execute("SELECT MAX(d) FROM (SELECT MAX(date) AS d FROM stock_counts UNION ALL "
                      "SELECT MAX(date) FROM deliveries UNION ALL SELECT MAX(date) FROM sales)").fetchone()
    d = date.fromisoformat(str(row[0])[:10]) + timedelta(days=1)
    closed = {r[0] for r in con.execute("SELECT day FROM day_close")}
    while d.isoformat() in closed:
        d += timedelta(days=1)
    return d.isoformat()


def record_sale(con, cashier, payment_mode, lines):
    """Saves one bill atomically. lines: [(item_id, qty), ...]. Returns (txn_id, total)."""
    if payment_mode not in PAYMENT_MODES:
        raise BillingError("Choose a payment mode.")
    who = str(cashier or "").strip().lower()
    role = con.execute("SELECT role FROM users WHERE username=?", (who,)).fetchone()
    if role is None or role[0] != "Cashier":
        raise BillingError("Only a cashier can create a bill.")
    agg = {}
    for item_id, qty in lines:
        if item_id not in catalog.CATALOG:
            raise BillingError(f"Unknown item {item_id}.")
        if qty <= 0 or int(qty) != qty:
            raise BillingError("Quantities must be whole numbers above zero.")
        agg[item_id] = agg.get(item_id, 0) + int(qty)
    if not agg:
        raise BillingError("The bill is empty.")

    con.execute("BEGIN IMMEDIATE")
    try:
        stock = stock_now(con)
        lim = limits(con)
        for item_id, qty in agg.items():
            name = catalog.CATALOG[item_id]["name"]
            have = stock.get(item_id)
            if have is None:
                raise BillingError(f"{name} has no stock count yet.")
            if have <= 0:
                raise BillingError(f"{name} is out of stock.")
            if qty > have:
                raise BillingError(f"Only {have:.0f} of {name} in stock.")
            if item_id in lim and qty > lim[item_id]:
                raise BillingError(f"{name}: purchase limit is {int(lim[item_id])} per bill.")
        day = store_day(con)
        n = con.execute("SELECT COUNT(*) FROM transactions WHERE day=?", (day,)).fetchone()[0] + 1
        txn_id = f"T{day.replace('-', '')}-{n:04d}"
        now = datetime.now(timezone.utc).isoformat()
        total = sum(catalog.CATALOG[i]["price"] * q for i, q in agg.items())
        con.execute("INSERT INTO transactions (txn_id, created_at, day, cashier, payment_mode, total) VALUES (?,?,?,?,?,?)",
                    (txn_id, now, day, cashier, payment_mode, total))
        con.executemany("INSERT INTO transaction_items (txn_id, item_id, qty, unit_price) VALUES (?,?,?,?)",
                        [(txn_id, i, q, catalog.CATALOG[i]["price"]) for i, q in agg.items()])
        con.execute("INSERT INTO audit_log (created_at, username, action, detail) VALUES (?,?,?,?)",
                    (now, cashier, "sale", f"{txn_id} {payment_mode} total {total}"))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return txn_id, total


def recent_bills(con, n=10):
    return con.execute(
        "SELECT t.txn_id, t.created_at, t.cashier, t.payment_mode, t.total, "
        "(SELECT SUM(qty) FROM transaction_items WHERE txn_id = t.txn_id) "
        "FROM transactions t ORDER BY t.created_at DESC LIMIT ?", (n,)).fetchall()

def bill_list(con, limit=500):
    return con.execute(
        "SELECT t.txn_id, t.created_at, t.day, t.cashier, t.payment_mode, t.total, "
        "(SELECT SUM(qty) FROM transaction_items WHERE txn_id = t.txn_id) "
        "FROM transactions t ORDER BY t.created_at DESC LIMIT ?", (limit,)).fetchall()


def bill_lines(con, txn_id):
    return con.execute("SELECT item_id, qty, unit_price FROM transaction_items WHERE txn_id=? ORDER BY item_id",
                       (txn_id,)).fetchall()