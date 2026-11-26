"""Shrinkage detection: flagged days, how big the gap is, and who has looked at it."""
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from app import htmlviews, theme, ui
from stockwise import auth, catalog

CURRENCY = "\u20b9"   # change to the rupee sign if you want rupees (database prices are the M5 prices)
SEVERITIES = ["High", "Medium", "Low"]
WINDOWS = {"Last 28 days": 28, "Last 90 days": 90, "All flagged days": None}
STATUS_FILTER = {"Open": "open", "Investigated": "investigated", "Dismissed": "dismissed", "All": None}
STATUS_BADGE = {"open": ("Open", "warn"), "investigated": ("Investigated", "ok"), "dismissed": ("Dismissed", "none")}
MAX_ROWS = 25


def save_review(con, username, item_id, date_str, status, note):
    """Writes one review decision and an audit-log line. status: open | investigated | dismissed."""
    if status == "open":
        con.execute("DELETE FROM investigations WHERE item_id=? AND date=?", (item_id, date_str))
    else:
        con.execute(
            "INSERT OR REPLACE INTO investigations (item_id, date, status, note, updated_at) VALUES (?,?,?,?,?)",
            (item_id, date_str, status, note, datetime.now(timezone.utc).isoformat()))
    con.execute("INSERT INTO audit_log (created_at, username, action, detail) VALUES (?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), username, "shrinkage_review",
                 f"{item_id} {date_str} -> {status}"))
    con.commit()


def _money(v):
    return "-" if pd.isna(v) else f"{CURRENCY}{v:,.0f}"


def _num(v, fmt="{:.0f}"):
    return "-" if pd.isna(v) else fmt.format(v)


def render():
    theme.inject()
    snap = ui.snapshot().set_index("item_id")
    det = ui.table("detections")
    inv = ui.table("investigations")
    sales = ui.table("sales")
    counts = ui.table("stock_counts")
    deliv = ui.table("deliveries")
    user = st.session_state.get("user") or {}
    is_admin = user.get("role") == "Admin"

    theme.page_header(
        "Shrinkage detection", "Where records and shelf disagree",
        "Each flag is a day when more stock disappeared than the forecast demand can explain, "
        "judged against that item's own usual variability.",
        demo=ui.DEMO_MODE)

    msg = st.session_state.pop("sh_msg", None)
    if msg:
        st.success(msg)

    if not len(det) or not (det["flag"] == 1).any():
        st.info("No shrinkage flags yet. Flags appear after stock counts are entered on the Stock counts page.")
        return

    flags = det[det["flag"] == 1].copy()
    latest = det["date"].max()
    if len(inv):
        flags = flags.merge(inv[["item_id", "date", "status", "note"]].rename(columns={"status": "review"}),
                            on=["item_id", "date"], how="left")
    else:
        flags["review"] = None
        flags["note"] = None
    flags["review"] = flags["review"].fillna("open")
    flags["note"] = flags["note"].fillna("")
    flags["category"] = flags["item_id"].map(snap["category"])
    flags["price"] = flags["item_id"].map(lambda i: catalog.CATALOG.get(i, {}).get("price")).astype(float)
    flags["value"] = flags["est_missing_units"] * flags["price"]

    with st.container(border=True):
        f1, f2, f3, f4 = st.columns(4)
        window = f1.selectbox("Time window", list(WINDOWS), key="sh_window")
        sev = f2.multiselect("Severity", SEVERITIES, default=SEVERITIES, key="sh_sev")
        depts = sorted(flags["category"].dropna().unique())
        dept = f3.multiselect("Department", depts, default=depts, key="sh_dept")
        status_label = f4.selectbox("Review status", list(STATUS_FILTER), key="sh_status_filter")

    days = WINDOWS[window]
    view = flags
    if days:
        view = view[view["date"] > latest - pd.Timedelta(days=days)]
    view = view[view["severity"].isin(sev) & view["category"].isin(dept)]
    if STATUS_FILTER[status_label]:
        view = view[view["review"] == STATUS_FILTER[status_label]]
    view = view.sort_values("value", ascending=False, na_position="last")

    if view.empty:
        st.info("No flagged days match these filters.")
        return

    show = view.head(MAX_ROWS).reset_index(drop=True)

    def _n(v):
        return None if pd.isna(v) else int(round(float(v)))

    rows = []
    for _, r in show.iterrows():
        d, iid = r["date"], r["item_id"]
        ci = counts[counts["item_id"] == iid]
        before = ci[ci["date"] < d].sort_values("date").tail(1)
        now = ci[ci["date"] == d]
        got = deliv[(deliv["item_id"] == iid) & (deliv["date"] == d)]["units"].sum()
        sold = sales[(sales["item_id"] == iid) & (sales["date"] == d)]["units_sold"].sum()
        counted = _n(now["counted_stock"].iloc[0]) if len(now) else None
        missing = _n(r["est_missing_units"]) or 0
        rows.append({
            "id": iid, "name": ui.name_of(iid), "category": str(r["category"]), "date": f"{d:%d %b %Y}",
            "opening": _n(before["counted_stock"].iloc[0]) if len(before) else None,
            "received": _n(got), "sold": _n(sold),
            "expected": None if counted is None else counted + missing, "counted": counted,
            "severity": str(r["severity"]), "review": STATUS_BADGE.get(r["review"], ("Open", "warn"))[0],
        })
    known = [x for x in rows if x["counted"] is not None]
    payload = {
        "flagged": len(view), "items": int(view["item_id"].nunique()),
        "expected": sum(x["expected"] for x in known), "counted": sum(x["counted"] for x in known),
        "variance": sum(x["counted"] - x["expected"] for x in known), "value": _money(view["value"].sum()),
        "rows": rows,
    }
    st.caption(f"Ranked by estimated value. Showing {len(show)} of {len(view)} flagged days.")
    htmlviews.shrinkage(payload, len(rows))

    options = list(range(len(show)))
    if st.session_state.get("sh_pick") not in options:
        st.session_state.pop("sh_pick", None)
    with st.container(border=True):
        theme.card_title("Inspect a flagged day", "Pick a row to see the counts behind it")
        i = st.selectbox("Flagged day", options, key="sh_pick", label_visibility="collapsed",
                         format_func=lambda n: f"{ui.name_of(show.loc[n, 'item_id'])} - {show.loc[n, 'date']:%d %b %Y} - "
                                               f"{show.loc[n, 'severity']} (about {show.loc[n, 'est_missing_units']:.0f} units)")
        r = show.loc[i]
        item, day = r["item_id"], r["date"]
        date_str = day.strftime("%Y-%m-%d")
        st.markdown(f"**{ui.name_of(item)}**")
        st.caption(f"Item code: {item}")

        c_item = counts[counts["item_id"] == item]
        before = c_item[c_item["date"] < day].sort_values("date").tail(1)
        now = c_item[c_item["date"] == day]
        got = deliv[(deliv["item_id"] == item) & (deliv["date"] == day)]["units"].sum()
        sold = sales[(sales["item_id"] == item) & (sales["date"] == day)]["units_sold"].sum()
        b_val = before["counted_stock"].iloc[0] if len(before) else float("nan")
        n_val = now["counted_stock"].iloc[0] if len(now) else float("nan")

        a, b, c, d, e = st.columns(5)
        a.markdown(theme.kpi("Counted before", _num(b_val), "Previous count"), unsafe_allow_html=True)
        b.markdown(theme.kpi("Delivered", _num(got), "That day"), unsafe_allow_html=True)
        c.markdown(theme.kpi("Sold", _num(sold), "That day"), unsafe_allow_html=True)
        d.markdown(theme.kpi("Counted now", _num(n_val), f"{day:%d %b}"), unsafe_allow_html=True)
        e.markdown(theme.kpi("Missing (est.)", _num(r["est_missing_units"]), "Beyond expected demand", "r"),
                   unsafe_allow_html=True)
        st.markdown(
            f'<div class="sw-sub" style="margin-top:10px">Stock fell by <b>{_num(r["actual_drop"])}</b> units against '
            f'<b>{_num(r["expected"], "{:.1f}")}</b> expected from demand. z-score <b>{r["z"]:.1f}</b> '
            f'(higher means more unusual for this item). Severity {theme.severity_badge(r["severity"])}</div>',
            unsafe_allow_html=True)
        if r["note"]:
            st.markdown(f'<div class="sw-sub">Note on file: {theme.esc(r["note"])}</div>', unsafe_allow_html=True)

        st.write("")
        if is_admin:
            s1, s2 = st.columns([1, 2])
            options_status = ["open", "investigated", "dismissed"]
            new_status = s1.selectbox("Review status", options_status, index=options_status.index(r["review"]),
                                      key=f"sh_new_{item}_{date_str}", format_func=str.title)
            note = s2.text_input("Note", value=r["note"], key=f"sh_note_{item}_{date_str}",
                                 placeholder="What did you find? (optional)")
            if st.button("Save review", key="sh_save"):
                con = sqlite3.connect(auth.DB_PATH)
                try:
                    save_review(con, user["username"], item, date_str, new_status, note.strip())
                finally:
                    con.close()
                st.session_state["sh_msg"] = f"Saved: {ui.name_of(item)} on {day:%d %b %Y} marked {new_status}."
                st.rerun()
        else:
            st.caption("View-only access. Ask an Admin to mark flags as investigated or dismissed.")