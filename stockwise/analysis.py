"""Sales analysis over the bills cashiers made: today, this week, this month or a custom range."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from stockwise import billing, catalog

PERIODS = ["Today", "This week", "This month", "Custom"]


def anchor_day(con):
    """The latest store day that has bills (or the open store day when there are none)."""
    row = con.execute("SELECT MAX(day) FROM transactions").fetchone()[0]
    return row if row else billing.store_day(con)


def bounds(kind, anchor, custom=None):
    a = date.fromisoformat(anchor)
    if kind == "Today":
        s = e = a
    elif kind == "This week":
        s, e = a - timedelta(days=6), a
    elif kind == "This month":
        s, e = a.replace(day=1), a
    else:
        s, e = (date.fromisoformat(str(x)[:10]) for x in custom)
        if s > e:
            s, e = e, s
    return s.isoformat(), e.isoformat()


def previous(start, end):
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    n = (e - s).days + 1
    return (s - timedelta(days=n)).isoformat(), (s - timedelta(days=1)).isoformat()


def lines(con, start, end):
    df = pd.read_sql_query(
        "SELECT t.txn_id, t.day, t.created_at, t.cashier, t.payment_mode, ti.item_id, ti.qty, ti.unit_price "
        "FROM transactions t JOIN transaction_items ti ON ti.txn_id = t.txn_id "
        "WHERE t.day BETWEEN ? AND ? ORDER BY t.created_at, t.txn_id, ti.item_id", con, params=(start, end))
    df["amount"] = df["qty"] * df["unit_price"]
    df["name"] = df["item_id"].map(lambda i: catalog.CATALOG[i]["name"] if i in catalog.CATALOG else i)
    df["group"] = df["item_id"].map(lambda i: catalog.CATALOG[i]["group"] if i in catalog.CATALOG else "Other")
    return df


def summary(df):
    if df.empty:
        return {"bills": 0, "units": 0, "revenue": 0.0, "average": 0.0}
    bills, revenue = df["txn_id"].nunique(), float(df["amount"].sum())
    return {"bills": int(bills), "units": int(df["qty"].sum()), "revenue": revenue, "average": revenue / bills}


def pct_change(cur, prev):
    return None if not prev else (cur - prev) / prev * 100


def daily(df, start, end):
    idx = pd.date_range(start, end, freq="D")
    g = df.groupby("day").agg(revenue=("amount", "sum"), units=("qty", "sum"), bills=("txn_id", "nunique"))
    g.index = pd.to_datetime(g.index)
    return g.reindex(idx, fill_value=0).rename_axis("day").reset_index()


def by_payment(df):
    g = df.groupby("payment_mode").agg(bills=("txn_id", "nunique"), amount=("amount", "sum"))
    return g.reindex(billing.PAYMENT_MODES, fill_value=0)


def by_group(df):
    return df.groupby("group").agg(units=("qty", "sum"), amount=("amount", "sum")).sort_values("amount", ascending=False)


def top_items(df, n=8):
    g = df.groupby(["item_id", "name"]).agg(units=("qty", "sum"), amount=("amount", "sum")).reset_index()
    return g.sort_values(["units", "amount", "item_id"], ascending=[False, False, True]).head(n)


def by_cashier(df):
    g = df.groupby("cashier").agg(bills=("txn_id", "nunique"), units=("qty", "sum"), amount=("amount", "sum"))
    return g.sort_values("amount", ascending=False)