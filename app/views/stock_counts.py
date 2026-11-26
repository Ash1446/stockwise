"""Stock counts: enter one count, or upload a counts file. Every save re-checks the item."""
import pandas as pd
import streamlit as st

from app import ui
from stockwise import catalog
from stockwise import db
from stockwise.counts import run_detection, validate_counts


def render():
    st.caption("DAILY CHECK")
    st.title("Stock counts")
    st.write("Enter the physical count at the end of the day. Stockwise compares how much stock actually "
             "left the shelf with the demand it expected, and flags losses that sales cannot explain.")
    items = ui.table("items")
    counts = ui.table("stock_counts")
    tab_one, tab_file = st.tabs(["Enter a count", "Upload a counts file"])
    with tab_one:
        _single(items, counts)
    with tab_file:
        _upload(items)


def _single(items, counts):
    ids = sorted((i for i in items["item_id"] if i in catalog.CATALOG), key=ui.name_of)
    wanted = st.session_state.get("count_item")
    item = st.selectbox("Item", ids, index=ids.index(wanted) if wanted in ids else 0, format_func=ui.name_of)
    st.caption(f"Item code: {item}")

    mine = counts[counts["item_id"] == item].sort_values("date")
    if len(mine):
        last = mine.iloc[-1]
        st.caption(f"Last count: {last['counted_stock']:,.0f} units on {last['date']:%d %b %Y}")
        start_date = (last["date"] + pd.Timedelta(days=1)).date()
        start_value = float(last["counted_stock"])
    else:
        start_date = (items.loc[items["item_id"] == item, "last_date"].iloc[0] + pd.Timedelta(days=1)).date()
        start_value = 0.0

    c1, c2, c3 = st.columns(3)
    day = c1.date_input("Date of count", value=start_date)
    counted = c2.number_input("Counted stock (units)", min_value=0.0, step=1.0, value=start_value)
    delivered = c3.number_input("Units delivered that day", min_value=0.0, step=1.0, value=0.0,
                                help="Stock received that day before sales. Leave 0 if nothing arrived.")

    if st.button("Save count"):
        day = pd.Timestamp(day)
        db.upsert("stock_counts", pd.DataFrame([{"item_id": item, "date": day, "counted_stock": counted}]))
        db.upsert("deliveries", pd.DataFrame([{"item_id": item, "date": day, "units": delivered}]))
        _show_result(run_detection("forecast", items=[item]), item, day)

    if len(mine):
        st.caption("Recent counts")
        recent = mine.tail(7)
        st.dataframe(pd.DataFrame({"Date": recent["date"].dt.strftime("%d %b %Y"),
                                   "Counted stock": recent["counted_stock"]}), hide_index=True)


def _show_result(det, item, day):
    row = pd.DataFrame() if det is None else det[(det["item_id"] == item) & (det["date"] == day)]
    if row.empty:
        st.warning("Count saved, but this day could not be checked yet. A check needs a count on the previous day "
                   "and a forecast for this date (forecasts cover the 7 days after the last uploaded sales).")
        return
    r = row.iloc[0]
    a, b, c = st.columns(3)
    a.metric("Stock that left", f"{r['actual_drop']:,.0f}")
    b.metric("Expected demand", f"{r['expected']:,.1f}")
    c.metric("Unexplained", f"{r['actual_drop'] - r['expected']:,.1f}")
    if r["actual_drop"] < 0:
        st.warning("Stock went up since the last count. Was there a delivery that was not entered?")
    if pd.isna(r["z"]):
        st.info("Count saved. This item needs 28 earlier days of counts before the check can start.")
    elif r["flag"] == 1:
        st.error(f"Flagged: {r['severity']} severity. About {r['est_missing_units']:.0f} units are unexplained.")
    else:
        st.success("Count saved. The stock drop is in line with expected demand.")


def _upload(items):
    st.write("A CSV with the columns **item_id**, **date**, **counted_stock** and, optionally, "
             "**delivered** (units received that day).")
    template = pd.DataFrame({"item_id": [sorted(items["item_id"])[0]],
                             "date": [(items["last_date"].max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")],
                             "counted_stock": [250], "delivered": [0]})
    st.download_button("Download a template", template.to_csv(index=False), "counts_template.csv", mime="text/csv")

    f = st.file_uploader("Counts file", type="csv")
    if f is None:
        return
    try:
        raw = pd.read_csv(f)
    except Exception:
        st.error("That file could not be read as a CSV.")
        return
    counts, deliveries, errors, warnings = validate_counts(raw, set(items["item_id"]))
    for e in errors:
        st.error(e)
    for w in warnings:
        st.warning(w)
    if errors:
        return
    st.write(f"{len(counts):,} counts ready to save for {counts['item_id'].nunique()} item(s).")
    if st.button("Save counts and run the check"):
        db.upsert("stock_counts", counts)
        if len(deliveries):
            db.upsert("deliveries", deliveries)
        det = run_detection("forecast", items=counts["item_id"].unique())
        if det is None:
            st.success(f"Saved {len(counts):,} counts. None could be checked yet (see the note under Enter a count).")
        else:
            hit = det.merge(counts[["item_id", "date"]], on=["item_id", "date"])
            st.success(f"Saved {len(counts):,} counts. {int(hit['flag'].sum())} of them were flagged.")