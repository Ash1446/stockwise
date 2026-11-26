"""Billing screen: scan or search items, build a bill, choose payment mode, complete the sale."""
import sqlite3
from datetime import datetime, timedelta, timezone

import streamlit as st

from app import theme
from stockwise import billing, catalog

RUPEE = "\u20b9"
IST = timezone(timedelta(hours=5, minutes=30))


def _money(v):
    return f"{RUPEE}{v:,.0f}"


def _read():
    con = sqlite3.connect(billing.DB_PATH)
    try:
        return billing.stock_now(con), billing.limits(con), billing.store_day(con), billing.recent_bills(con)
    finally:
        con.close()


def _note(kind, text):
    st.session_state["bill_note"] = (kind, text)


def _add(item_id):
    bill = st.session_state.setdefault("bill", {})
    con = sqlite3.connect(billing.DB_PATH)
    try:
        stock = billing.stock_now(con)
        limit = billing.limits(con).get(item_id)
    finally:
        con.close()
    name = catalog.CATALOG[item_id]["name"]
    have = stock.get(item_id)
    cur = bill.get(item_id, 0)
    if have is None:
        return _note("error", f"{name} has no stock count yet.")
    if have <= 0:
        return _note("error", f"{name} is out of stock.")
    if cur + 1 > have:
        return _note("error", f"Only {have:.0f} of {name} in stock.")
    if limit is not None and cur + 1 > limit:
        return _note("error", f"{name}: purchase limit is {int(limit)} per bill.")
    bill[item_id] = cur + 1
    st.session_state[f"bill_qty_{item_id}"] = bill[item_id]
    _note("ok", f"Added {name} ({cur + 1} on the bill).")


def _scan():
    q = st.session_state.get("bill_scan", "")
    st.session_state["bill_scan"] = ""
    if not q.strip():
        return
    item_id, why = billing.find_item(q)
    if item_id is None:
        _note("error", why)
    else:
        _add(item_id)


def _pick_add():
    _add(st.session_state["bill_pick"])


def _set_qty(item_id):
    bill = st.session_state.get("bill", {})
    if item_id in bill:
        bill[item_id] = int(st.session_state[f"bill_qty_{item_id}"])


def _remove(item_id):
    st.session_state.get("bill", {}).pop(item_id, None)
    st.session_state.pop(f"bill_qty_{item_id}", None)


def _clear():
    for i in list(st.session_state.get("bill", {})):
        st.session_state.pop(f"bill_qty_{i}", None)
    st.session_state["bill"] = {}


def render():
    theme.inject()
    user = st.session_state.get("user") or {}
    stock, limits, day, recent = _read()
    bill = st.session_state.setdefault("bill", {})
    for i in list(bill):
        if i not in catalog.CATALOG:
            bill.pop(i)

    theme.page_header(
        "Shop", "Billing",
        f"Scan or search items to build a bill. Store day <b>{day}</b>. "
        "Each completed bill reduces that item's stock.", demo=True)

    last = st.session_state.get("last_sale")
    if last:
        st.success(f"Bill {last['txn_id']} saved: {_money(last['total'])} paid by {last['mode']}.")
        rows = [[theme.esc(n), f"{q}", _money(p), _money(p * q)] for n, q, p in last["lines"]]
        st.markdown(theme.table(["Item", "Qty", "Price", "Amount"], rows), unsafe_allow_html=True)

    note = st.session_state.pop("bill_note", None)
    if note:
        (st.error if note[0] == "error" else st.success)(note[1])

    left, right = st.columns([1, 1.25], gap="large")

    with left:
        with st.container(border=True):
            theme.card_title("Add items", "Click the box once, then scan. Each scan adds one unit.")
            st.text_input("Scan or type item code or name", key="bill_scan", on_change=_scan,
                          placeholder="Scan a barcode, or type FOODS_3_050 or Basmati Rice, then press Enter")
            ids = sorted(catalog.CATALOG, key=lambda i: catalog.CATALOG[i]["name"])
            st.selectbox("Or pick an item", ids, key="bill_pick",
                         format_func=lambda i: f"{catalog.label(i)} - {_money(catalog.CATALOG[i]['price'])} - "
                                               f"{'no count' if stock.get(i) is None else str(int(stock[i])) + ' in stock'}")
            st.button("Add to bill", on_click=_pick_add, key="bill_pick_add")

    with right:
        with st.container(border=True):
            theme.card_title("Current bill", "Change quantities here. Limits and stock are checked again when you complete the sale.")
            if not bill:
                st.caption("No items yet. Scan or pick an item on the left.")
            total = 0
            for i in list(bill):
                c = catalog.CATALOG[i]
                have = stock.get(i) or 0
                cap = max(1, int(min(have, limits.get(i, have))))
                key = f"bill_qty_{i}"
                if st.session_state.get(key, bill[i]) > cap:
                    st.session_state[key] = cap
                st.session_state.setdefault(key, bill[i])
                a, b, d, e, f = st.columns([3, 1.1, 1.3, 1.2, 0.6])
                a.markdown(f"<b>{theme.esc(c['name'])}</b><br><span class='sw-sub'>{theme.esc(c['pack'])} - {i}</span>",
                           unsafe_allow_html=True)
                b.markdown(_money(c["price"]))
                d.number_input("Qty", min_value=1, max_value=cap, step=1, key=key, on_change=_set_qty,
                               args=(i,), label_visibility="collapsed")
                bill[i] = int(st.session_state[key])
                e.markdown(f"<b>{_money(c['price'] * bill[i])}</b>", unsafe_allow_html=True)
                f.button("x", key=f"bill_rm_{i}", on_click=_remove, args=(i,))
                total += c["price"] * bill[i]
            k1, k2 = st.columns(2)
            k1.markdown(theme.kpi("Items on bill", sum(bill.values()), f"{len(bill)} lines"), unsafe_allow_html=True)
            k2.markdown(theme.kpi("Total", _money(total), "Including all lines", "g"), unsafe_allow_html=True)
            st.write("")
            mode = st.radio("Payment mode", billing.PAYMENT_MODES, horizontal=True, key="bill_pay")
            b1, b2 = st.columns(2)
            done = b1.button("Complete sale", type="primary", disabled=not bill, key="bill_done", width="stretch")
            b2.button("Clear bill", on_click=_clear, key="bill_clear", width="stretch")
            if done:
                con = sqlite3.connect(billing.DB_PATH)
                txn_id = None
                try:
                    lines = [(i, q) for i, q in bill.items()]
                    txn_id, amount = billing.record_sale(con, user.get("username", ""), mode, lines)
                except billing.BillingError as e:
                    st.error(str(e))
                finally:
                    con.close()
                if txn_id:
                    st.session_state["last_sale"] = {
                        "txn_id": txn_id, "total": amount, "mode": mode,
                        "lines": [(catalog.CATALOG[i]["name"], q, catalog.CATALOG[i]["price"]) for i, q in lines]}
                    _clear()
                    st.rerun()

    with st.container(border=True):
        theme.card_title("Recent bills", "The last 10 bills, newest first")
        if not recent:
            st.caption("No bills yet.")
        else:
            rows = []
            for txn_id, created, cashier, pay, amount, qty in recent:
                when = (datetime.fromisoformat(created) + timedelta(hours=5, minutes=30)).strftime("%d %b %H:%M")
                rows.append([f"<b>{theme.esc(txn_id)}</b>", f"{when} IST", theme.esc(cashier or "-"),
                             f"{int(qty or 0)}", theme.esc(pay or "-"), f"<b>{_money(amount)}</b>"])
            st.markdown(theme.table(["Bill", "Time", "Cashier", "Units", "Payment", "Total"], rows),
                        unsafe_allow_html=True)