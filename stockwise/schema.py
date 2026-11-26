"""Input validation for uploaded sales data.

validate_sales() never crashes on bad data. It returns a ValidationResult with
plain-language errors (the file cannot be used) and warnings (it was fixed
automatically), so the app can show them to the user.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config


@dataclass
class ValidationResult:
    data: pd.DataFrame | None = None     # clean daily table, one row per item per day
    items: pd.DataFrame | None = None    # one row per item: history length and forecast mode
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _map_columns(df):
    """Understand common column names (SKU, Qty, Unit Price, ...)."""
    cleaned = {c: str(c).strip().lower().replace(" ", "_") for c in df.columns}
    mapping = {}
    for canonical, aliases in config.COLUMN_ALIASES.items():
        for original, clean in cleaned.items():
            if clean in aliases and original not in mapping:
                mapping[original] = canonical
                break
    return df.rename(columns=mapping)


def validate_sales(raw):
    res = ValidationResult()
    if raw is None or len(raw) == 0:
        res.errors.append("The file is empty.")
        return res

    df = _map_columns(raw.copy())
    missing = [c for c in config.REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        res.errors.append(
            f"Missing required column(s): {', '.join(missing)}. "
            "The file needs item_id, date and units_sold (optional: price, category, event).")
        return res
    df = df[[c for c in config.REQUIRED_COLUMNS + config.OPTIONAL_COLUMNS if c in df.columns]].copy()

    # --- item ---
    df["item_id"] = df["item_id"].astype(str).str.strip()
    blank = df["item_id"].isin(["", "nan", "None"])
    if blank.any():
        res.warnings.append(f"{int(blank.sum())} row(s) with a blank item were removed.")
        df = df[~blank].copy()

    # --- date ---
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    bad = df["date"].isna()
    if bad.any():
        res.warnings.append(f"{int(bad.sum())} row(s) with an unreadable date were removed.")
        df = df[~bad].copy()
    df["date"] = df["date"].dt.normalize()

    # --- units sold ---
    df["units_sold"] = pd.to_numeric(df["units_sold"], errors="coerce")
    bad = df["units_sold"].isna()
    if bad.any():
        res.warnings.append(f"{int(bad.sum())} row(s) with unreadable units were removed.")
        df = df[~bad].copy()
    neg = df["units_sold"] < 0
    if neg.any():
        res.warnings.append(f"{int(neg.sum())} negative unit value(s) (returns?) were set to 0.")
        df.loc[neg, "units_sold"] = 0
    if df.empty:
        res.errors.append("No usable rows remain after cleaning.")
        return res

    # --- optional columns ---
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df.loc[df["price"] <= 0, "price"] = np.nan
    else:
        df["price"] = np.nan
        res.warnings.append("No price column found, so price is ignored by the forecast.")
    df["category"] = df["category"].astype(str).str.strip() if "category" in df.columns else "all"
    df["event"] = (pd.to_numeric(df["event"], errors="coerce").fillna(0).clip(0, 1).astype(int)
                   if "event" in df.columns else 0)

    # --- duplicates ---
    dup = int(df.duplicated(["item_id", "date"]).sum())
    if dup:
        res.warnings.append(f"{dup} duplicate item/date row(s) were combined (units added, price averaged).")
        df = (df.groupby(["item_id", "date"], as_index=False)
                .agg(units_sold=("units_sold", "sum"), price=("price", "mean"),
                     category=("category", "first"), event=("event", "max")))

    # --- one row per item per day (days with no row = zero sales) ---
    frames, filled = [], 0
    for item, g in df.groupby("item_id", sort=True):
        g = g.set_index("date").sort_index()
        full = pd.date_range(g.index.min(), g.index.max(), freq="D")
        filled += len(full) - len(g)
        g = g.reindex(full)
        g["item_id"] = item
        g["units_sold"] = g["units_sold"].fillna(0)
        g["category"] = g["category"].ffill().bfill()
        g["event"] = g["event"].fillna(0).astype(int)
        g["price"] = g["price"].ffill().bfill()
        frames.append(g.rename_axis("date").reset_index())
    data = pd.concat(frames, ignore_index=True)

    if data["price"].isna().any():
        item_med = data.groupby("item_id")["price"].transform("median")
        data["price"] = data["price"].fillna(item_med).fillna(data["price"].median()).fillna(1.0)
    if filled:
        res.warnings.append(f"{filled} day(s) had no sales rows and were treated as zero sales. "
                            "If the shop was closed on those days, averages will be slightly low.")

    # --- per-item summary and forecast mode ---
    items = (data.groupby("item_id")
                 .agg(n_days=("date", "size"), first_date=("date", "min"), last_date=("date", "max"),
                      mean_daily_units=("units_sold", "mean"),
                      zero_share=("units_sold", lambda s: float((s == 0).mean())))
                 .reset_index())
    items["mode"] = np.where(items["n_days"] >= config.MIN_HISTORY_DAYS, "model", "fallback")
    short = int((items["mode"] == "fallback").sum())
    if short:
        res.warnings.append(f"{short} item(s) have fewer than {config.MIN_HISTORY_DAYS} days of history "
                            "and will use the simple rolling-average forecast.")

    res.data = data[["item_id", "date", "units_sold", "price", "category", "event"]]
    res.items = items
    return res