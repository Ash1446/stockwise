"""Damaged and expired entry (manager only). Shelf stock reduces stock; an item from a bill is only recorded."""
from __future__ import annotations

from datetime import datetime, timezone

from stockwise import billing, catalog

REASONS = ["Damaged", "Expired"]


class WriteOffError(Exception):
    pass


def _require_admin(con, username):
    row = con.execute("SELECT role FROM users WHERE username=?", (str(username or "").strip().lower(),)).fetchone()
    if row is None or row[0] != "Admin":
        raise WriteOffError("Only the manager can record damaged or expired items.")


def written_off_for_bill(con, txn_id, item_id):
    return con.execute("SELECT COALESCE(SUM(qty), 0) FROM write_offs WHERE txn_id=? AND item_id=?",
                       (txn_id, item_id)).fetchone()[0]


def record_write_off(con, username, item_id, qty, reason, note="", txn_id=None):
    """Saves one write-off atomically and returns its ID. With txn_id it is linked to a bill and does not change stock."""
    _require_admin(con, username)
    if reason not in REASONS:
        raise WriteOffError("Choose Damaged or Expired.")
    if item_id not in catalog.CATALOG:
        raise WriteOffError("Choose an item.")
    if qty is None or qty <= 0 or int(qty) != qty:
        raise WriteOffError("Quantity must be a whole number above zero.")
    qty = int(qty)
    name = catalog.CATALOG[item_id]["name"]
    con.execute("BEGIN IMMEDIATE")
    try:
        if txn_id:
            if con.execute("SELECT 1 FROM transactions WHERE txn_id=?", (txn_id,)).fetchone() is None:
                raise WriteOffError("That bill does not exist.")
            row = con.execute("SELECT qty FROM transaction_items WHERE txn_id=? AND item_id=?", (txn_id, item_id)).fetchone()
            if row is None:
                raise WriteOffError(f"{name} is not on bill {txn_id}.")
            left = row[0] - written_off_for_bill(con, txn_id, item_id)
            if qty > left:
                raise WriteOffError(f"Only {left:.0f} of {name} on bill {txn_id} can still be marked.")
        else:
            have = billing.stock_now(con).get(item_id)
            if have is None:
                raise WriteOffError(f"{name} has no stock count yet.")
            if qty > have:
                raise WriteOffError(f"Only {have:.0f} of {name} in stock.")
        day = billing.store_day(con)
        n = con.execute("SELECT COUNT(*) FROM write_offs WHERE date=?", (day,)).fetchone()[0] + 1
        wid = f"W{day.replace('-', '')}-{n:04d}"
        who = str(username).strip().lower()
        now = datetime.now(timezone.utc).isoformat()
        con.execute("INSERT INTO write_offs (write_off_id, item_id, date, qty, reason, txn_id, note, entered_by, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)", (wid, item_id, day, qty, reason, txn_id or None, note or "", who, now))
        con.execute("INSERT INTO audit_log (created_at, username, action, detail) VALUES (?,?,?,?)",
                    (now, who, "write_off", f"{wid} {item_id} x{qty} {reason}" + (f" bill {txn_id}" if txn_id else " shelf")))
        con.commit()
    except Exception:
        con.rollback()
        raise
    return wid


def recent(con, n=15):
    return con.execute("SELECT write_off_id, date, item_id, qty, reason, txn_id, note, entered_by FROM write_offs "
                       "ORDER BY created_at DESC LIMIT ?", (n,)).fetchall()


def day_totals(con, day):
    rows = con.execute("SELECT item_id, qty FROM write_offs WHERE date=?", (day,)).fetchall()
    return {"entries": len(rows), "units": sum(q for _, q in rows),
            "value": sum(catalog.CATALOG[i]["price"] * q for i, q in rows if i in catalog.CATALOG)}