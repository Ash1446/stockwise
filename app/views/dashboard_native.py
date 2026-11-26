"""Dashboard: the clearest read on inventory health and where to look next."""
import altair as alt
import pandas as pd
import streamlit as st

from app import theme, ui

STATUS_ORDER = ["Healthy", "Low", "Critical", "Out of stock", "No count"]
STATUS_COLORS = ["#15803d", "#f59e0b", "#dc2626", "#7f1d1d", "#9ca3af"]


def render():
    theme.inject()
    snap = ui.snapshot()
    det = ui.table("detections")
    sales = ui.table("sales")
    exp = ui.table("expected_demand")
    inv = ui.table("investigations")

    latest = sales["date"].max()
    theme.page_header(
        "Dashboard", "Inventory health at a glance",
        f"Latest data <b>{latest:%d %b %Y}</b>. What is healthy, what needs a reorder, "
        "and where records and shelf disagree.",
        demo=ui.DEMO_MODE)

    # ---- shrinkage flags in the last 28 days that nobody has dealt with yet ----
    recent = pd.DataFrame(columns=["item_id", "date", "est_missing_units", "severity", "done"])
    if len(det):
        recent = det[(det["flag"] == 1) &
                     (det["date"] > det["date"].max() - pd.Timedelta(days=28))].copy()
        if len(inv):
            handled = inv[inv["status"].isin(["investigated", "dismissed"])][["item_id", "date"]].assign(done=True)
            recent = recent.merge(handled, on=["item_id", "date"], how="left")
            recent["done"] = recent["done"].eq(True)
        else:
            recent["done"] = False
    open_flags = recent[~recent["done"]]

    has_counts = snap["stock"].notna().any()
    total = len(snap)
    healthy = int((snap["status"] == "Healthy").sum())
    low = int(snap["status"].isin(["Low", "Critical", "Out of stock"]).sum())
    units = f"{int(snap['stock'].sum()):,} units on hand" if has_counts else "No counts yet"

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(theme.kpi("Total products", total, units), unsafe_allow_html=True)
    k2.markdown(theme.kpi("Healthy stock", healthy, f"{round(healthy / max(total, 1) * 100)}% of catalogue", "g"),
                unsafe_allow_html=True)
    k3.markdown(theme.kpi("Low stock alerts", low, f"Under {ui.LOW_COVER_DAYS} days of cover at forecast demand", "a"),
                unsafe_allow_html=True)
    k4.markdown(theme.kpi("Open shrinkage flags", len(open_flags), "Flagged in the last 28 days, not yet reviewed", "r"),
                unsafe_allow_html=True)
    st.write("")

    left, right = st.columns(2)

    with left:
        with st.container(border=True):
            theme.card_title("Inventory distribution", "Stock position by days of cover")
            full = snap["status"].value_counts().reindex(STATUS_ORDER, fill_value=0)
            counts = full.reset_index()
            counts.columns = ["status", "items"]
            counts = counts[counts["items"] > 0]
            d1, d2 = st.columns([1.2, 1])
            donut = alt.Chart(counts).mark_arc(innerRadius=55).encode(
                theta="items:Q",
                color=alt.Color("status:N", scale=alt.Scale(domain=STATUS_ORDER, range=STATUS_COLORS), legend=None),
                tooltip=["status", "items"]).properties(height=210)
            d1.altair_chart(donut, width='stretch')
            key_rows = [(c, s, int(full[s]), round(full[s] / max(total, 1) * 100))
                        for s, c in zip(STATUS_ORDER, STATUS_COLORS) if full[s] > 0]
            d2.markdown(theme.key_list(key_rows), unsafe_allow_html=True)

    with right:
        with st.container(border=True):
            theme.card_title("Actual vs predicted demand", "Units per day, all items together, last 28 days")
            pulse = (sales.merge(exp[["item_id", "date", "expected"]], on=["item_id", "date"])
                          .groupby("date")[["units_sold", "expected"]].sum().tail(28).reset_index()
                          .melt("date", var_name="series", value_name="units"))
            pulse["series"] = pulse["series"].map({"units_sold": "Actual demand", "expected": "Forecast"})
            names = ["Actual demand", "Forecast"]
            line = alt.Chart(pulse).mark_line(strokeWidth=2.2).encode(
                x=alt.X("date:T", title=""), y=alt.Y("units:Q", title="Units"),
                color=alt.Color("series:N", scale=alt.Scale(domain=names, range=["#0f1f33", "#2563eb"]),
                                legend=alt.Legend(orient="bottom", title=None)),
                strokeDash=alt.StrokeDash("series:N", scale=alt.Scale(domain=names, range=[[1, 0], [5, 4]]),
                                          legend=None)).properties(height=230)
            st.altair_chart(line, width='stretch')

    # ---- items to review (shrinkage) ----
    with st.container(border=True):
        theme.card_title("Items to review", "Open shrinkage flags ranked by estimated value (price x units missing)")
        if not len(det):
            st.info("No stock counts yet, so shrinkage cannot be checked. Counts are entered on the Stock counts page.")
        elif open_flags.empty:
            st.success("No open shrinkage flags in the last 28 days.")
        else:
            flags = open_flags.merge(snap[["item_id", "category", "price"]], on="item_id", how="left")
            flags["est_value"] = flags["est_missing_units"] * flags["price"]
            rows = []
            for _, r in flags.sort_values("est_value", ascending=False).head(6).iterrows():
                rows.append([f"<b>{theme.esc(r['item_id'])}</b>", theme.esc(r["category"]), f"{r['date']:%d %b %Y}",
                             theme.severity_badge(r["severity"]), f"<b>{r['est_missing_units']:.0f}</b>",
                             f"{r['est_value']:,.0f}"])
            st.markdown(theme.table(["Item", "Department", "Date", "Severity", "Units missing", "Est. value"], rows),
                        unsafe_allow_html=True)
            st.caption("Severity shows how unusual the loss is for that specific item.")

    # ---- running low ----
    running_low = snap[snap["status"].isin(["Low", "Critical", "Out of stock"])].sort_values("cover_days").head(8)
    if len(running_low):
        with st.container(border=True):
            theme.card_title("Needs attention", f"{low} items are low or out of stock. Showing the {len(running_low)} most urgent.")
            rows = []
            for _, r in running_low.iterrows():
                rows.append([f"<b>{theme.esc(r['item_id'])}</b>", theme.esc(r["category"]), f"<b>{r['stock']:.0f}</b>",
                             f"{r['cover_days']:.0f} days", theme.status_badge(r["status"])])
            st.markdown(theme.table(["Item", "Department", "In stock", "Cover at forecast demand", "Status"], rows),
                        unsafe_allow_html=True)