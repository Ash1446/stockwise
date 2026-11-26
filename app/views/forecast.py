"""Demand forecast in the teammate's HTML look: recent demand against the next 7 days, read against stock held."""
import pandas as pd
import streamlit as st

from app import htmlviews, ui
from stockwise import catalog

HORIZON = 7
KEEP = 60


def _val(x, digits=None):
    if pd.isna(x):
        return None
    return round(float(x), digits) if digits is not None else float(x)


def build_payload():
    snap = ui.snapshot().sort_values("item_id").set_index("item_id")
    sales = ui.table("sales").copy()
    fc = ui.table("forecasts").copy()
    settings = ui.table("item_settings").set_index("item_id")
    sales["date"] = pd.to_datetime(sales["date"])
    fc["date"] = pd.to_datetime(fc["date"])
    sales_by = {i: g.sort_values("date").tail(KEEP) for i, g in sales.groupby("item_id")}
    fc_by = {i: g.sort_values("date").head(HORIZON) for i, g in fc.groupby("item_id")}
    items = []
    for iid in snap.index:
        s, f = sales_by.get(iid), fc_by.get(iid)
        if s is None or f is None or s.empty or f.empty:
            continue
        cfg = settings.loc[iid] if iid in settings.index else None
        c = catalog.CATALOG.get(iid)
        shelf = None
        if cfg is not None and cfg["perishable"] == 1 and pd.notna(cfg["shelf_life_days"]):
            shelf = float(cfg["shelf_life_days"])
        items.append({
            "id": iid, "name": c["name"] if c else iid, "category": str(snap.loc[iid, "category"]),
            "hist": [int(round(v)) for v in s["units_sold"]], "hl": [f"{d.day} {d:%b}" for d in s["date"]],
            "fc": [round(float(v), 1) for v in f["forecast"]], "fl": [f"{d.day} {d:%b}" for d in f["date"]],
            "stock": _val(snap.loc[iid, "stock"], 0), "status": str(snap.loc[iid, "status"]),
            "min": _val(cfg["min_stock"], 0) if cfg is not None else None,
            "target": _val(cfg["target_stock"], 0) if cfg is not None else None, "shelf": shelf,
        })
    return {"items": items}


def render():
    payload = build_payload()
    if not payload["items"]:
        st.info("No sales history or forecast is stored yet.")
        return
    htmlviews.forecast(payload)