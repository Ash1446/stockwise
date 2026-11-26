"""Bills created by cashiers: a read-only history for the manager (Admin)."""
import sqlite3
from datetime import datetime, timedelta

import streamlit as st

from app import theme
from stockwise import billing, catalog

RUPEE = "\u20b9"
SHOW = 50


def _money(v):
    return f"{RUPEE}{v:,.0f}"


def _lines(txn_id):
    con = sqlite3.connect(billing.DB_PATH)
    try:
        return billing.bill_lines(con, txn_id)
    finally:
        con.close()


def render():
    theme.inject()
    user = st.session_state.get("user") or {}
    if user.get("role") != "Admin":
        st.error("Only the manager can view all bills.")
        return
    con = sqlite3.connect(billing.DB_PATH)
    try:
        bills = billing.bill_list(con)
    finally:
        con.close()

    theme.page_header(
        "Shop", "Bills from cashiers",
        "Read-only. Bills are created by cashiers at the billing counter, and every bill reduces stock.",
        demo=True)
    if not bills:
        st.info("No bills yet. Bills appear here as soon as a cashier completes a sale.")
        return

    days = sorted({b[2] for b in bills}, reverse=True)
    modes = billing.PAYMENT_MODES
    if st.session_state.get("adm_day") not in ["All days"] + days:
        st.session_state.pop("adm_day", None)
    with st.container(border=True):
        f1, f2 = st.columns(2)
        day = f1.selectbox("Store day", ["All days"] + days, key="adm_day")
        pay = f2.multiselect("Payment mode", modes, default=modes, key="adm_pay")

    view = [b for b in bills if (day == "All days" or b[2] == day) and (b[4] in pay)]
    units = sum(int(b[6] or 0) for b in view)
    revenue = sum(b[5] or 0 for b in view)
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(theme.kpi("Bills", len(view), "Created by cashiers"), unsafe_allow_html=True)
    k2.markdown(theme.kpi("Units sold", units, "Across these bills"), unsafe_allow_html=True)
    k3.markdown(theme.kpi("Revenue", _money(revenue), "Sum of bill totals", "g"), unsafe_allow_html=True)
    k4.markdown(theme.kpi("Average bill", _money(revenue / len(view)) if view else "-", "Revenue per bill"),
                unsafe_allow_html=True)
    st.write("")
    if not view:
        st.info("No bills match these filters.")
        return

    shown = view[:SHOW]
    with st.container(border=True):
        theme.card_title("All bills", f"Newest first. Showing {len(shown)} of {len(view)}.")
        rows = []
        for txn_id, created, d, cashier, pay_mode, total, qty in shown:
            when = (datetime.fromisoformat(created) + timedelta(hours=5, minutes=30)).strftime("%H:%M")
            rows.append([f"<b>{theme.esc(txn_id)}</b>", theme.esc(d), f"{when} IST", theme.esc(cashier or "-"),
                         theme.esc(pay_mode or "-"), f"{int(qty or 0)}", f"<b>{_money(total)}</b>"])
        st.markdown(theme.table(["Bill", "Store day", "Time", "Cashier", "Payment", "Units", "Total"], rows),
                    unsafe_allow_html=True)

    ids = [b[0] for b in shown]
    if st.session_state.get("adm_pick") not in ids:
        st.session_state.pop("adm_pick", None)
    with st.container(border=True):
        theme.card_title("Bill details", "Pick a bill to see what was sold")
        pick = st.selectbox("Bill", ids, key="adm_pick", label_visibility="collapsed")
        rows = []
        for item_id, qty, price in _lines(pick):
            c = catalog.CATALOG.get(item_id)
            name = theme.esc(c["name"]) if c else theme.esc(item_id)
            pack = theme.esc(c["pack"]) if c else ""
            rows.append([f"<b>{name}</b><br><small>{pack} - {theme.esc(item_id)}</small>", f"{int(qty)}",
                         _money(price), f"<b>{_money(price * qty)}</b>"])
        st.markdown(theme.table(["Item", "Qty", "Price", "Amount"], rows), unsafe_allow_html=True)
        st.caption("View-only. A manager cannot create or change bills.")