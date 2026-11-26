"""Write-offs: damaged and expired entry (manager only)."""
import sqlite3
from datetime import datetime, timedelta

import streamlit as st

from app import theme, ui
from stockwise import billing, catalog, writeoffs

RUPEE = "\u20b9"
SHELF = "Shelf stock"
BILL = "Item from a bill"


def _money(v):
    return f"{RUPEE}{v:,.0f}"


def _save():
    ss = st.session_state
    user = ss.get("user") or {}
    if ss.get("wo_mode") == SHELF:
        item, txn = ss.get("wo_item"), None
    else:
        item, txn = ss.get("wo_bill_item"), ss.get("wo_bill")
    if not item:
        ss["wo_msg"] = ("error", "Choose an item first.")
        return
    con = sqlite3.connect(billing.DB_PATH)
    try:
        wid = writeoffs.record_write_off(con, user.get("username", ""), item, ss.get("wo_qty", 1),
                                         ss.get("wo_reason"), (ss.get("wo_note") or "").strip(), txn)
        ss["wo_msg"] = ("ok", f"Saved {wid}: {int(ss.get('wo_qty', 1))} x {catalog.CATALOG[item]['name']} marked {ss.get('wo_reason').lower()}.")
        ss["wo_qty"] = 1
        ss["wo_note"] = ""
    except writeoffs.WriteOffError as e:
        ss["wo_msg"] = ("error", str(e))
    finally:
        con.close()


def render():
    theme.inject()
    user = st.session_state.get("user") or {}
    if user.get("role") != "Admin":
        st.error("Only the manager can record damaged or expired items.")
        return

    con = sqlite3.connect(billing.DB_PATH)
    try:
        stock = billing.stock_now(con)
        day = billing.store_day(con)
        bills = billing.bill_list(con, 100)
        recent = writeoffs.recent(con, 15)
        totals = writeoffs.day_totals(con, day)
    finally:
        con.close()
    settings = ui.table("item_settings").set_index("item_id")

    theme.page_header(
        "Write-offs", "Damaged and expired items",
        f"Manager only. Store day <b>{day}</b>. Shelf stock reduces stock; an item from a bill is recorded without changing stock.",
        demo=True)
    k1, k2, k3 = st.columns(3)
    k1.markdown(theme.kpi("Entries today", totals["entries"], f"Store day {day}"), unsafe_allow_html=True)
    k2.markdown(theme.kpi("Units written off", int(totals["units"]), "Damaged and expired", "r"), unsafe_allow_html=True)
    k3.markdown(theme.kpi("Value written off", _money(totals["value"]), "Shop price x units", "a"), unsafe_allow_html=True)
    st.write("")

    note = st.session_state.pop("wo_msg", None)
    if note:
        (st.error if note[0] == "error" else st.success)(note[1])

    st.session_state.setdefault("wo_qty", 1)
    with st.container(border=True):
        theme.card_title("Record a damaged or expired item", "Choose where the item is, then what happened to it")
        mode = st.radio("Where is the item?", [SHELF, BILL], horizontal=True, key="wo_mode")
        cap = 0
        if mode == SHELF:
            ids = sorted(catalog.CATALOG, key=lambda i: catalog.CATALOG[i]["name"])
            item = st.selectbox("Item", ids, key="wo_item",
                                format_func=lambda i: f"{catalog.label(i)} - {i} - "
                                                      f"{'no count' if stock.get(i) is None else str(int(stock[i])) + ' in stock'}")
            cap = int(stock.get(item) or 0)
        else:
            item = None
            if not bills:
                st.info("No bills yet, so there is nothing to link to. Use Shelf stock, or wait for a cashier to make a bill.")
            else:
                ids = [b[0] for b in bills]
                lab = {b[0]: f"{b[0]} - {b[2]} - {b[4]} - {_money(b[5])}" for b in bills}
                txn = st.selectbox("Bill", ids, key="wo_bill", format_func=lambda t: lab[t])
                c2 = sqlite3.connect(billing.DB_PATH)
                try:
                    left = {i: q - writeoffs.written_off_for_bill(c2, txn, i) for i, q, p in billing.bill_lines(c2, txn)}
                finally:
                    c2.close()
                left = {i: q for i, q in left.items() if q > 0 and i in catalog.CATALOG}
                if not left:
                    st.info("Every item on this bill has already been marked.")
                else:
                    opts = sorted(left)
                    if st.session_state.get("wo_bill_item") not in opts:
                        st.session_state.pop("wo_bill_item", None)
                    item = st.selectbox("Item on the bill", opts, key="wo_bill_item",
                                        format_func=lambda i: f"{catalog.label(i)} - {int(left[i])} can still be marked")
                    cap = int(left[item])
        reason = st.radio("What happened?", writeoffs.REASONS, horizontal=True, key="wo_reason")
        if item and reason == "Expired" and item in settings.index and settings.loc[item, "perishable"] == 0:
            st.caption("This item is not marked perishable in the item settings.")
        if st.session_state.get("wo_qty", 1) > max(1, cap):
            st.session_state["wo_qty"] = max(1, cap)
        q1, q2 = st.columns([1, 3])
        q1.number_input("Quantity", min_value=1, max_value=max(1, cap), step=1, key="wo_qty", disabled=cap < 1)
        q2.text_input("Note (optional)", key="wo_note", placeholder="For example: dented tin found while stocking")
        st.button("Save write-off", on_click=_save, key="wo_save", type="primary", disabled=cap < 1 or not item)
        if cap < 1 and item:
            st.caption("There is nothing available to write off for this item.")

    with st.container(border=True):
        theme.card_title("Recent write-offs", "The last 15 entries, newest first")
        if not recent:
            st.caption("No write-offs yet.")
        else:
            rows = []
            for wid, d, item_id, qty, why, txn_id, nt, by in recent:
                c = catalog.CATALOG.get(item_id)
                name = theme.esc(c["name"]) if c else theme.esc(item_id)
                kind = "danger" if why == "Damaged" else "warn"
                badge = theme.badge(why, "bad" if why == "Damaged" else "warn")
                rows.append([f"<b>{theme.esc(wid)}</b>", theme.esc(d), f"<b>{name}</b><br><small>{theme.esc(item_id)}</small>",
                             f"{int(qty)}", badge, theme.esc(txn_id) if txn_id else "Shelf", theme.esc(nt or "-"),
                             theme.esc((by or "-").split("@")[0])])
            st.markdown(theme.table(["Entry", "Store day", "Item", "Qty", "Reason", "Bill", "Note", "By"], rows),
                        unsafe_allow_html=True)