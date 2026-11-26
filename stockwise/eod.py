"""End-of-day report and closing the day (manager only)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from stockwise import billing, catalog


class EodError(Exception):
    pass


def days_with_activity(con, open_day):
    q = "SELECT day FROM transactions UNION SELECT date FROM write_offs UNION SELECT day FROM day_close"
    return sorted({r[0] for r in con.execute(q)} | {open_day}, reverse=True)


def closed_info(con, day):
    return con.execute("SELECT closed_by, closed_at, note FROM day_close WHERE day=?", (day,)).fetchone()


def summary(con, day):
    n_bills, revenue = con.execute(
        "SELECT COUNT(*), COALESCE(SUM(total), 0) FROM transactions WHERE day=?", (day,)).fetchone()
    units = con.execute(
        "SELECT COALESCE(SUM(ti.qty), 0) FROM transaction_items ti JOIN transactions t ON t.txn_id = ti.txn_id "
        "WHERE t.day=?", (day,)).fetchone()[0]
    modes = {m: (0, 0.0) for m in billing.PAYMENT_MODES}
    for mode, c, amt in con.execute(
            "SELECT payment_mode, COUNT(*), COALESCE(SUM(total), 0) FROM transactions WHERE day=? GROUP BY payment_mode", (day,)):
        modes[mode or "Other"] = (c, amt)
    top = con.execute(
        "SELECT ti.item_id, SUM(ti.qty), SUM(ti.qty * ti.unit_price) FROM transaction_items ti "
        "JOIN transactions t ON t.txn_id = ti.txn_id WHERE t.day=? GROUP BY ti.item_id "
        "ORDER BY SUM(ti.qty) DESC, ti.item_id LIMIT 8", (day,)).fetchall()
    wo = con.execute("SELECT item_id, qty, reason, txn_id FROM write_offs WHERE date=?", (day,)).fetchall()
    received = con.execute("SELECT COALESCE(SUM(units), 0) FROM deliveries WHERE date=?", (day,)).fetchone()[0]
    shelf = sum(q for _, q, _, t in wo if not t)
    return {
        "bills": n_bills, "revenue": revenue, "units": units, "modes": modes, "top": top,
        "received": received, "shelf_units": shelf,
        "bill_units": sum(q for _, q, _, t in wo if t),
        "damaged": sum(q for _, q, r, _ in wo if r == "Damaged"),
        "expired": sum(q for _, q, r, _ in wo if r == "Expired"),
        "wo_entries": len(wo),
        "wo_value": sum(catalog.CATALOG[i]["price"] * q for i, q, _, _ in wo if i in catalog.CATALOG),
        "net_change": received - units - shelf,
    }


def bills_csv(con, day):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["bill", "store_day", "time_ist", "cashier", "payment_mode", "item", "item_id", "qty", "unit_price", "amount"])
    rows = con.execute(
        "SELECT t.txn_id, t.created_at, t.cashier, t.payment_mode, ti.item_id, ti.qty, ti.unit_price "
        "FROM transactions t JOIN transaction_items ti ON ti.txn_id = t.txn_id WHERE t.day=? "
        "ORDER BY t.created_at, t.txn_id, ti.item_id", (day,)).fetchall()
    for txn, created, cashier, mode, item_id, qty, price in rows:
        when = (datetime.fromisoformat(created) + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M")
        name = catalog.CATALOG[item_id]["name"] if item_id in catalog.CATALOG else item_id
        w.writerow([txn, day, when, cashier, mode, name, item_id, int(qty), price, price * qty])
    return out.getvalue()


def close_day(con, username, day, note=""):
    who = str(username or "").strip().lower()
    row = con.execute("SELECT role FROM users WHERE username=?", (who,)).fetchone()
    if row is None or row[0] != "Admin":
        raise EodError("Only the manager can close the day.")
    con.execute("BEGIN IMMEDIATE")
    try:
        if con.execute("SELECT 1 FROM day_close WHERE day=?", (day,)).fetchone():
            raise EodError("That day is already closed.")
        if day != billing.store_day(con):
            raise EodError("Only the current store day can be closed.")
        if con.execute("SELECT COUNT(*) FROM transactions WHERE day=?", (day,)).fetchone()[0] == 0:
            raise EodError("There are no bills on this day yet, so there is nothing to close.")
        now = datetime.now(timezone.utc).isoformat()
        con.execute("INSERT INTO day_close (day, closed_by, closed_at, note) VALUES (?,?,?,?)", (day, who, now, note or ""))
        con.execute("INSERT INTO audit_log (created_at, username, action, detail) VALUES (?,?,?,?)",
                    (now, who, "day_close", f"{day} closed"))
        con.commit()
    except Exception:
        con.rollback()
        raise