"""End of day: the daily report, a CSV of the day's bills, and closing the day (manager only)."""
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from app import theme, ui
from stockwise import billing, catalog, eod

RUPEE = "\u20b9"


def _money(v):
    return f"{RUPEE}{v:,.0f}"


def _ist(iso):
    return (datetime.fromisoformat(iso) + timedelta(hours=5, minutes=30)).strftime("%d %b %Y %H:%M")


def _close():
    ss = st.session_state
    user = ss.get("user") or {}
    con = sqlite3.connect(billing.DB_PATH)
    try:
        day = ss.get("eod_day")
        eod.close_day(con, user.get("username", ""), day, (ss.get("eod_note") or "").strip())
        ss["eod_msg"] = ("ok", f"Store day {day} is closed. The next bill starts a new store day.")
        ss["eod_note"] = ""
        ss["eod_confirm"] = False
        ss.pop("eod_day", None)
    except eod.EodError as e:
        ss["eod_msg"] = ("error", str(e))
    finally:
        con.close()


def render():
    theme.inject()
    user = st.session_state.get("user") or {}
    if user.get("role") != "Admin":
        st.error("Only the manager can see the end-of-day report.")
        return

    con = sqlite3.connect(billing.DB_PATH)
    try:
        open_day = billing.store_day(con)
        days = eod.days_with_activity(con, open_day)
        closed = {r[0] for r in con.execute("SELECT day FROM day_close")}
    finally:
        con.close()

    theme.page_header(
        "End of day", "Daily report and close",
        f"Manager only. Open store day <b>{open_day}</b>. Closing the day moves the next bill to a new store day.",
        demo=True)

    note = st.session_state.pop("eod_msg", None)
    if note:
        (st.error if note[0] == "error" else st.success)(note[1])

    if st.session_state.get("eod_day") not in days:
        st.session_state.pop("eod_day", None)
    with st.container(border=True):
        c1, c2 = st.columns([1, 2])
        day = c1.selectbox("Store day", days, key="eod_day",
                           format_func=lambda d: f"{d} - " + ("closed" if d in closed else "open" if d == open_day else "past"))

    con = sqlite3.connect(billing.DB_PATH)
    try:
        s = eod.summary(con, day)
        info = eod.closed_info(con, day)
        csv_text = eod.bills_csv(con, day)
    finally:
        con.close()

    if info:
        c2.markdown(theme.badge("Closed", "ok") + f" &nbsp; by {theme.esc((info[0] or '-').split('@')[0])} at {_ist(info[1])} IST"
                    + (f"<br><span class='sw-sub'>Note: {theme.esc(info[2])}</span>" if info[2] else ""), unsafe_allow_html=True)
    elif day == open_day:
        c2.markdown(theme.badge("Open", "warn") + " &nbsp; bills are still being added to this day", unsafe_allow_html=True)
    else:
        c2.markdown(theme.badge("Past day", "none"), unsafe_allow_html=True)

    st.write("")
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(theme.kpi("Bills", s["bills"], "Made by cashiers"), unsafe_allow_html=True)
    k2.markdown(theme.kpi("Units sold", int(s["units"]), "Across all bills"), unsafe_allow_html=True)
    k3.markdown(theme.kpi("Revenue", _money(s["revenue"]), "Sum of bill totals", "g"), unsafe_allow_html=True)
    k4.markdown(theme.kpi("Average bill", _money(s["revenue"] / s["bills"]) if s["bills"] else "-", "Revenue per bill"),
                unsafe_allow_html=True)
    st.write("")

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            theme.card_title("Payment modes", "How customers paid")
            rows = []
            for mode, (c, amt) in s["modes"].items():
                share = f"{amt / s['revenue'] * 100:.0f}%" if s["revenue"] else "-"
                rows.append([f"<b>{theme.esc(mode)}</b>", f"{c}", _money(amt), share])
            st.markdown(theme.table(["Mode", "Bills", "Amount", "Share"], rows), unsafe_allow_html=True)
    with right:
        with st.container(border=True):
            theme.card_title("Top items sold", "By units, up to 8")
            if not s["top"]:
                st.caption("No bills on this day.")
            else:
                rows = []
                for item_id, q, amt in s["top"]:
                    c = catalog.CATALOG.get(item_id)
                    rows.append([f"<b>{theme.esc(c['name']) if c else theme.esc(item_id)}</b><br><small>{theme.esc(item_id)}</small>",
                                 f"{int(q)}", _money(amt)])
                st.markdown(theme.table(["Item", "Units", "Amount"], rows), unsafe_allow_html=True)

    with st.container(border=True):
        theme.card_title("Stock movement and write-offs", "What came in, what went out, and what was lost")
        a, b, c, d = st.columns(4)
        a.markdown(theme.kpi("Received", int(s["received"]), "Deliveries that day"), unsafe_allow_html=True)
        b.markdown(theme.kpi("Sold", int(s["units"]), "On bills"), unsafe_allow_html=True)
        c.markdown(theme.kpi("Shelf write-offs", int(s["shelf_units"]), "Reduced stock", "a"), unsafe_allow_html=True)
        d.markdown(theme.kpi("Net stock change", f"{s['net_change']:+.0f}", "Received - sold - shelf write-offs",
                             "r" if s["net_change"] < 0 else ""), unsafe_allow_html=True)
        st.write("")
        e, f, g, h = st.columns(4)
        e.markdown(theme.kpi("Damaged", int(s["damaged"]), "Units"), unsafe_allow_html=True)
        f.markdown(theme.kpi("Expired", int(s["expired"]), "Units"), unsafe_allow_html=True)
        g.markdown(theme.kpi("Marked on bills", int(s["bill_units"]), "Recorded, stock unchanged"), unsafe_allow_html=True)
        h.markdown(theme.kpi("Write-off value", _money(s["wo_value"]), f"{s['wo_entries']} entries", "a"), unsafe_allow_html=True)

    with st.container(border=True):
        theme.card_title("Items to watch", "Low or out of stock right now, most urgent first")
        snap = ui.snapshot()
        low = snap[snap["status"].isin(["Low", "Critical", "Out of stock"])].sort_values("cover_days").head(8)
        if low.empty:
            st.success("No item is low or out of stock.")
        else:
            rows = []
            for _, r in low.iterrows():
                c = catalog.CATALOG.get(r["item_id"])
                cover = "-" if pd.isna(r["cover_days"]) else f"{r['cover_days']:.0f} days"
                rows.append([f"<b>{theme.esc(c['name']) if c else theme.esc(r['item_id'])}</b><br><small>{theme.esc(r['item_id'])}</small>",
                             theme.esc(c["group"]) if c else "-", f"{r['stock']:.0f}", cover, theme.status_badge(r["status"])])
            st.markdown(theme.table(["Item", "Department", "In stock", "Cover", "Status"], rows), unsafe_allow_html=True)

    with st.container(border=True):
        theme.card_title("Close the day", "Saves who closed it and when. The next bill starts a new store day.")
        can_close = day == open_day and not info and s["bills"] > 0
        if info:
            st.caption("This day is already closed.")
        elif day != open_day:
            st.caption("Only the current open store day can be closed.")
        elif s["bills"] == 0:
            st.caption("There are no bills on this day yet, so there is nothing to close.")
        st.text_input("Note (optional)", key="eod_note", disabled=not can_close,
                      placeholder="For example: counted cash drawer, all matches")
        st.checkbox("I confirm this day's bills and write-offs are complete", key="eod_confirm", disabled=not can_close)
        st.button("Close the day", on_click=_close, key="eod_close", type="primary",
                  disabled=not (can_close and st.session_state.get("eod_confirm")))
        st.download_button("Download this day's bills (CSV)", data=csv_text, file_name=f"bills_{day}.csv",
                           mime="text/csv", key="eod_csv", disabled=s["bills"] == 0)