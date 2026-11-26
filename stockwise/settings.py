"""Per-item stock settings: required (target) stock, minimum stock, shelf life, purchase limit.

The admin can edit all of them. Defaults come from each item's forecast demand.
With demo=True, some food items are also marked perishable and the highest-demand items get a
purchase limit. Those two are DEMO ASSUMPTIONS (M5 has neither) and must be labelled as such.
"""
import numpy as np
import pandas as pd

from . import db

LEAD_TIME_DAYS = 2        # days a delivery takes
SAFETY_DAYS = 1           # extra days of demand kept as a buffer
TARGET_DAYS = 14          # required stock = this many days of demand (non-perishables)
PERISHABLE_SHARE = 0.30   # demo only: share of food items marked perishable
SHELF_LIFE_CHOICES = (2, 3)
LIMIT_TOP_SHARE = 0.10    # demo only: top share of items by demand get a purchase limit
LIMIT_QTY = 5


def default_settings(items, sales, forecasts, demo=False, seed=42):
    """One row per item: perishable, shelf_life_days, min_stock, target_stock, purchase_limit."""
    out = items[["item_id", "category"]].sort_values("item_id").set_index("item_id")
    recent = sales.sort_values("date").groupby("item_id")["units_sold"].apply(lambda s: float(s.tail(28).mean()))
    daily = (forecasts.groupby("item_id")["forecast"].sum() / 7) if len(forecasts) else pd.Series(dtype=float)
    out["daily_demand"] = daily.reindex(out.index).fillna(recent.reindex(out.index)).fillna(0.0)

    n = len(out)
    d = out["daily_demand"].to_numpy()
    rng = np.random.default_rng(seed)
    perishable = np.zeros(n, dtype=bool)
    shelf = np.full(n, np.nan)
    limit = np.full(n, np.nan)
    if demo:
        is_food = out["category"].astype(str).str.upper().str.startswith("FOODS").to_numpy()
        perishable = is_food & (rng.random(n) < PERISHABLE_SHARE)
        shelf = np.where(perishable, rng.choice(SHELF_LIFE_CHOICES, size=n), np.nan)
        cutoff = np.quantile(d, 1 - LIMIT_TOP_SHARE)
        limit = np.where((d >= cutoff) & (d > 0), LIMIT_QTY, np.nan)

    min_days = np.where(perishable, 1.0, LEAD_TIME_DAYS + SAFETY_DAYS)
    target_days = np.where(perishable, np.maximum(np.nan_to_num(shelf, nan=1.0) - 1, 1.0), TARGET_DAYS)
    min_stock = np.maximum(np.ceil(d * min_days), 1)
    target_stock = np.maximum(np.ceil(d * target_days), min_stock + 1)

    return pd.DataFrame({"item_id": out.index, "perishable": perishable.astype(int),
                         "shelf_life_days": shelf, "min_stock": min_stock,
                         "target_stock": target_stock, "purchase_limit": limit}).reset_index(drop=True)


def ensure_item_settings(path=None, demo=False, overwrite=False):
    """Creates settings for items that have none (or for all items with overwrite=True).

    Settings the admin has edited are kept unless overwrite=True. Returns how many rows were written.
    """
    db.init_db(path)
    items = db.read_table("items", path)
    existing = set(db.read_table("item_settings", path)["item_id"])
    defaults = default_settings(items, db.read_table("sales", path), db.read_table("forecasts", path), demo=demo)
    if not overwrite:
        defaults = defaults[~defaults["item_id"].isin(existing)]
    if defaults.empty:
        return 0
    db.upsert("item_settings", defaults, path)
    return len(defaults)