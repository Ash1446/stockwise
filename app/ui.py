"""Shared look and data loading for the Stockwise app."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import streamlit as st

from stockwise import db

DEMO_MODE = True        # the stock counts and shrinkage in the sample database are simulated
LOW_COVER_DAYS = 14     # fewer days of stock than this counts as low

CSS = """
<style>
.stApp { background-color: #f7f8fa; }
section[data-testid="stSidebar"] { background-color: #0f1b3d; }
section[data-testid="stSidebar"] * { color: #ffffff !important; }
section[data-testid="stSidebar"] .demo-note, section[data-testid="stSidebar"] .demo-note * { color: #0f1b3d !important; }
.demo-note { background: #fff4e5; border-radius: 8px; padding: 10px 12px; font-size: 13px; margin-top: 8px; }
.stButton > button { background-color: #1a56db; color: white; border-radius: 8px; border: none; }
.stButton > button:hover { background-color: #1442a8; color: white; }
div[data-testid="stMetric"] { background-color: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 16px; }
.block-card { background-color: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 18px; margin-bottom: 10px; }
.tag-ok { background:#e6f4ea; color:#1e7a34; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.tag-warn { background:#fff4e5; color:#a15c00; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.tag-bad { background:#fde8e8; color:#c22; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.tag-low { background:#eef2ff; color:#3730a3; padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }
.muted { color:#6b7280; font-size:13px; }
.stApp [data-testid="stHeading"], .stApp [data-testid="stHeading"] * { color:#111827; }
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stMarkdownContainer"] p, .stApp [data-testid="stCaptionContainer"], .stApp label { color:#1f2937; }
div[data-testid="stMetric"], div[data-testid="stMetric"] * { color:#111827 !important; }
</style>
"""


def apply_style():
    st.markdown(CSS, unsafe_allow_html=True)


def db_ready():
    if not db.DB_PATH.exists() or db.DB_PATH.stat().st_size < 100_000:
        return False
    try:
        return len(db.read_table("items")) > 0
    except Exception:
        return False


def db_stamp():
    """Changes whenever the database file changes, so cached data refreshes."""
    p = db.DB_PATH
    found = [q.stat().st_mtime for q in (p, p.with_name(p.name + "-wal")) if q.exists()]
    return max(found) if found else 0.0


@st.cache_data(show_spinner=False)
def _load(name, stamp):
    return db.read_table(name)


def table(name):
    return _load(name, db_stamp())


@st.cache_data(show_spinner=False)
def _snapshot(stamp):
    items = db.read_table("items")
    sales = db.read_table("sales")
    forecasts = db.read_table("forecasts")
    counts = db.read_table("stock_counts")

    price = sales.sort_values("date").groupby("item_id")["price"].last().rename("price")
    week = forecasts.groupby("item_id")["forecast"].sum().rename("forecast_7d")
    snap = items.set_index("item_id")[["category", "mode"]].join(price).join(week)

    if len(counts):
        last = counts.sort_values("date").groupby("item_id").tail(1).set_index("item_id")
        snap = snap.join(last[["date", "counted_stock"]].rename(
            columns={"date": "count_date", "counted_stock": "stock"}))
    else:
        snap["count_date"] = pd.NaT
        snap["stock"] = np.nan

    from stockwise import billing
    adj = billing.stock_adjustments()
    if adj:
        snap["stock"] = snap["stock"] + snap.index.to_series().map(adj).fillna(0.0)
    snap["daily_demand"] = snap["forecast_7d"] / 7
    snap["cover_days"] = snap["stock"] / snap["daily_demand"].clip(lower=0.05)
    snap["status"] = np.select(
        [snap["stock"].isna(), snap["stock"] <= 0, snap["cover_days"] < 3, snap["cover_days"] < LOW_COVER_DAYS],
        ["No count", "Out of stock", "Critical", "Low"], default="Healthy")
    from stockwise import catalog
    snap = snap[~snap.index.isin(catalog.EXCLUDED)]
    return snap.reset_index()


def snapshot():
    """One row per item: latest count, price, next-7-day forecast, days of cover, stock status."""
    return _snapshot(db_stamp())

def go_to(page, **state):
    """Button callback: switch to another page and pass it some state."""
    st.session_state["nav"] = page
    for key, value in state.items():
        st.session_state[key] = value

def name_of(item_id):
    """Product name for an item id (falls back to the id)."""
    from stockwise import catalog
    c = catalog.CATALOG.get(item_id)
    return c["name"] if c else str(item_id)
