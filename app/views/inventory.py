"""Inventory: browse items, open one to see its demand, stock and shrinkage history."""
import altair as alt
import pandas as pd
import streamlit as st

from app import ui

BADGE = {"Healthy": "tag-ok", "Low": "tag-warn", "Critical": "tag-bad",
         "Out of stock": "tag-bad", "No count": "tag-low"}
RANK = {"Out of stock": 0, "Critical": 1, "Low": 2, "No count": 3, "Healthy": 4}
PAGE_SIZE = 24


def _fmt(value, digits=0):
    return "-" if pd.isna(value) else f"{value:,.{digits}f}"


def render():
    item = st.session_state.get("inv_item")
    if item:
        _detail(item)
    else:
        _grid()


def _grid():
    snap = ui.snapshot()
    st.caption("CATALOG INTELLIGENCE")
    st.title("Inventory")
    st.write(f"Browse {len(snap)} products and spot the next action at a glance.")

    f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
    search = f1.text_input("Search", placeholder="Search by item ID...", label_visibility="collapsed")
    category = f2.selectbox("Category", ["All categories"] + sorted(snap["category"].dropna().unique()),
                            label_visibility="collapsed")
    status = f3.selectbox("Status", ["All status", "Needs attention", "Healthy", "Low", "Critical",
                                     "Out of stock", "No count"], label_visibility="collapsed")
    sort = f4.selectbox("Sort", ["Worst first", "Item ID", "Stock (low to high)",
                                 "Forecast demand (high to low)"], label_visibility="collapsed")

    view = snap.copy()
    if search.strip():
        view = view[view["item_id"].str.contains(search.strip(), case=False, regex=False) | view["item_id"].map(ui.name_of).str.contains(search.strip(), case=False, regex=False)]
    if category != "All categories":
        view = view[view["category"] == category]
    if status == "Needs attention":
        view = view[view["status"].isin(["Low", "Critical", "Out of stock"])]
    elif status != "All status":
        view = view[view["status"] == status]

    if sort == "Worst first":
        view = view.assign(_rank=view["status"].map(RANK)).sort_values(["_rank", "cover_days"]).drop(columns="_rank")
    elif sort == "Item ID":
        view = view.loc[view["item_id"].map(ui.name_of).sort_values().index]
    elif sort == "Stock (low to high)":
        view = view.sort_values("stock")
    else:
        view = view.sort_values("forecast_7d", ascending=False)
    view = view.reset_index(drop=True)

    n_pages = max(1, -(-len(view) // PAGE_SIZE))
    page = 1
    if n_pages > 1:
        page = int(st.number_input("Page", min_value=1, max_value=n_pages, value=1, step=1))
    st.caption(f"{len(view)} of {len(snap)} items" + (f" - page {page} of {n_pages}" if n_pages > 1 else ""))
    if view.empty:
        st.info("No items match these filters.")
        return

    chunk = view.iloc[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    cols = st.columns(4)
    for i, r in enumerate(chunk.itertuples()):
        with cols[i % 4]:
            with st.container(border=True):
                st.markdown(f"**{ui.name_of(r.item_id)}**  \n:gray[{r.item_id}]")
                st.caption(r.category)
                st.markdown(f'<span class="{BADGE.get(r.status, "tag-low")}">{r.status}</span>', unsafe_allow_html=True)
                st.write(f"Stock: **{_fmt(r.stock)}**")
                st.caption(f"Cover: {_fmt(r.cover_days)} days | Next 7 days: {_fmt(r.forecast_7d)}")
                if st.button("View item", key=f"view_{r.item_id}"):
                    st.session_state["inv_item"] = r.item_id
                    st.rerun()


def _detail(item_id):
    snap = ui.snapshot().set_index("item_id")
    if item_id not in snap.index:
        st.session_state.pop("inv_item", None)
        st.rerun()
    r = snap.loc[item_id]

    if st.button("Back to inventory"):
        st.session_state.pop("inv_item", None)
        st.rerun()
    st.caption(f"{r['category']} | forecast method: {r['mode']}")
    st.title(ui.name_of(item_id)); st.caption(item_id)
    st.markdown(f'<span class="{BADGE.get(r["status"], "tag-low")}">{r["status"]}</span>', unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Stock", _fmt(r["stock"]))
    m2.metric("Days of cover", _fmt(r["cover_days"]))
    m3.metric("Forecast, next 7 days", _fmt(r["forecast_7d"]))
    m4.metric("Price", _fmt(r["price"], 2))
    st.button("Enter a count for this item", on_click=ui.go_to, args=("Stock counts",),
              kwargs={"count_item": item_id})

    sales, exp = ui.table("sales"), ui.table("expected_demand")
    counts, det = ui.table("stock_counts"), ui.table("detections")

    st.subheader("Demand: actual vs forecast")
    d = (sales[sales["item_id"] == item_id]
         .merge(exp[exp["item_id"] == item_id][["date", "expected"]], on="date")
         .sort_values("date").tail(60))
    if d.empty:
        st.info("No forecast history for this item yet.")
    else:
        m = d.melt("date", value_vars=["units_sold", "expected"], var_name="series", value_name="units")
        m["series"] = m["series"].map({"units_sold": "Actual demand", "expected": "Forecast"})
        chart = alt.Chart(m).mark_line(point=True).encode(
            x=alt.X("date:T", title=""), y=alt.Y("units:Q", title="Units"),
            color=alt.Color("series:N", scale=alt.Scale(range=["#1a56db", "#8b5cf6"]))).properties(height=240)
        st.altair_chart(chart, width='stretch')

    st.subheader("Stock level (red dots = flagged days)")
    c = counts[counts["item_id"] == item_id].sort_values("date").tail(60)
    if c.empty:
        st.info("No stock counts for this item yet.")
    else:
        fl = det[(det["item_id"] == item_id) & (det["flag"] == 1)][["date", "severity", "est_missing_units"]]
        c = c.merge(fl, on="date", how="left")
        line = alt.Chart(c).mark_line(color="#1a56db").encode(
            x=alt.X("date:T", title=""), y=alt.Y("counted_stock:Q", title="Units in stock"))
        dots = (alt.Chart(c.dropna(subset=["severity"])).mark_circle(size=110, color="#c22222")
                .encode(x="date:T", y="counted_stock:Q", tooltip=["date:T", "severity", "est_missing_units"]))
        st.altair_chart((line + dots).properties(height=240), width='stretch')

    fut = ui.table("forecasts")
    f = fut[fut["item_id"] == item_id].sort_values("date")
    if len(f):
        st.subheader("Next 7 days")
        st.dataframe(pd.DataFrame({"Day": f["date"].dt.strftime("%a %d %b"),
                                   "Forecast units": f["forecast"].round(1)}), hide_index=True)

    flagged = det[(det["item_id"] == item_id) & (det["flag"] == 1)].sort_values("date", ascending=False).head(10)
    if len(flagged):
        st.subheader("Recent flagged days")
        st.dataframe(pd.DataFrame({"Date": flagged["date"].dt.strftime("%d %b %Y"),
                                   "Severity": flagged["severity"],
                                   "Units missing": flagged["est_missing_units"],
                                   "z-score": flagged["z"].round(1)}), hide_index=True)