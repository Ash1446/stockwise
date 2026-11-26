"""Sales analysis: bills made by cashiers for today, this week, this month or a custom range (manager only)."""
import sqlite3
from datetime import date

import altair as alt
import streamlit as st

from app import theme
from stockwise import analysis, billing

RUPEE = "\u20b9"


def _money(v):
    return f"{RUPEE}{v:,.0f}"


def _delta(cur, prev, label):
    p = analysis.pct_change(cur, prev)
    if p is None:
        return f"No bills in the previous {label}"
    return f"{abs(p):.0f}% {'higher' if p >= 0 else 'lower'} than the previous {label}"


def render():
    theme.inject()
    user = st.session_state.get("user") or {}
    if user.get("role") != "Admin":
        st.error("Only the manager can see sales analysis.")
        return

    con = sqlite3.connect(billing.DB_PATH)
    try:
        anchor = analysis.anchor_day(con)
        first = con.execute("SELECT MIN(day) FROM transactions").fetchone()[0]
    finally:
        con.close()

    theme.page_header(
        "Sales analysis", "How the shop is selling",
        "Manager only. Built from the bills cashiers make. Each period is compared with the one before it.",
        demo=True)
    if first is None:
        st.info("No bills yet. Sales analysis appears as soon as a cashier completes a sale.")
        return

    lo, hi = date.fromisoformat(first), date.fromisoformat(anchor)
    cur_range = st.session_state.get("sa_range")
    if isinstance(cur_range, (tuple, list)) and cur_range and not all(lo <= d <= hi for d in cur_range):
        st.session_state.pop("sa_range")
    with st.container(border=True):
        kind = st.radio("Period", analysis.PERIODS, horizontal=True, key="sa_period")
        custom = None
        if kind == "Custom":
            picked = st.date_input("From and to", value=(lo, hi), min_value=lo, max_value=hi, key="sa_range")
            if not isinstance(picked, (tuple, list)) or len(picked) != 2:
                st.info("Pick both a start date and an end date.")
                return
            custom = picked

    start, end = analysis.bounds(kind, anchor, custom)
    pstart, pend = analysis.previous(start, end)
    n_days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    label = "day" if n_days == 1 else f"{n_days} days"

    con = sqlite3.connect(billing.DB_PATH)
    try:
        cur = analysis.lines(con, start, end)
        prev = analysis.lines(con, pstart, pend)
    finally:
        con.close()
    st.caption(f"Showing {start}" if start == end else f"Showing {start} to {end} ({label})")
    if cur.empty:
        st.info("No bills in this period.")
        return

    cs, ps = analysis.summary(cur), analysis.summary(prev)
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(theme.kpi("Bills", cs["bills"], _delta(cs["bills"], ps["bills"], label)), unsafe_allow_html=True)
    k2.markdown(theme.kpi("Units sold", cs["units"], _delta(cs["units"], ps["units"], label)), unsafe_allow_html=True)
    k3.markdown(theme.kpi("Revenue", _money(cs["revenue"]), _delta(cs["revenue"], ps["revenue"], label), "g"),
                unsafe_allow_html=True)
    k4.markdown(theme.kpi("Average bill", _money(cs["average"]),
                          _delta(cs["average"], ps["average"], label)), unsafe_allow_html=True)
    st.write("")

    if n_days > 1:
        with st.container(border=True):
            theme.card_title("Revenue by day", f"{start} to {end}, days with no bills show as zero")
            d = analysis.daily(cur, start, end)
            chart = alt.Chart(d).mark_bar(color="#0f1f33", cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("day:T", title=""), y=alt.Y("revenue:Q", title=f"Revenue ({RUPEE})"),
                tooltip=[alt.Tooltip("day:T", title="Day"), alt.Tooltip("revenue:Q", title="Revenue", format=",.0f"),
                         alt.Tooltip("units:Q", title="Units"), alt.Tooltip("bills:Q", title="Bills")]).properties(height=260)
            st.altair_chart(chart, width="stretch")

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            theme.card_title("Payment modes", "How customers paid")
            p = analysis.by_payment(cur)
            rows = [[f"<b>{theme.esc(m)}</b>", f"{int(r.bills)}", _money(r.amount),
                     f"{r.amount / cs['revenue'] * 100:.0f}%" if cs["revenue"] else "-"] for m, r in p.iterrows()]
            st.markdown(theme.table(["Mode", "Bills", "Amount", "Share"], rows), unsafe_allow_html=True)
        with st.container(border=True):
            theme.card_title("Departments", "Revenue by product group")
            g = analysis.by_group(cur)
            rows = [[f"<b>{theme.esc(name)}</b>", f"{int(r.units)}", _money(r.amount),
                     f"{r.amount / cs['revenue'] * 100:.0f}%"] for name, r in g.iterrows()]
            st.markdown(theme.table(["Group", "Units", "Amount", "Share"], rows), unsafe_allow_html=True)
    with right:
        with st.container(border=True):
            theme.card_title("Top items", "By units sold, up to 8")
            t = analysis.top_items(cur, 8)
            rows = [[f"<b>{theme.esc(r.name)}</b><br><small>{theme.esc(r.item_id)}</small>", f"{int(r.units)}",
                     _money(r.amount)] for r in t.itertuples()]
            st.markdown(theme.table(["Item", "Units", "Amount"], rows), unsafe_allow_html=True)
        with st.container(border=True):
            theme.card_title("Cashiers", "Who made the bills")
            c = analysis.by_cashier(cur)
            rows = [[f"<b>{theme.esc((name or '-').split('@')[0])}</b>", f"{int(r.bills)}", f"{int(r.units)}",
                     _money(r.amount)] for name, r in c.iterrows()]
            st.markdown(theme.table(["Cashier", "Bills", "Units", "Amount"], rows), unsafe_allow_html=True)

    csv_df = cur[["txn_id", "day", "cashier", "payment_mode", "name", "item_id", "qty", "unit_price", "amount"]]
    st.download_button("Download these sales (CSV)", data=csv_df.to_csv(index=False), file_name=f"sales_{start}_to_{end}.csv",
                       mime="text/csv", key="sa_csv")