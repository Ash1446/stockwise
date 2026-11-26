"""From stock counts to flagged items."""
import pandas as pd

from . import config, db
from .detect import detect


def drops_from_counts(counts, deliveries=None, writeoffs=None):
    """actual_drop = yesterday's count + today's deliveries - today's count.

    Only days that have a count on BOTH that day and the day before can be used.
    """
    c = counts[["item_id", "date", "counted_stock"]].copy()
    c["date"] = pd.to_datetime(c["date"])
    prev = c.copy()
    prev["date"] = prev["date"] + pd.Timedelta(days=1)
    prev = prev.rename(columns={"counted_stock": "prev_count"})
    m = c.merge(prev, on=["item_id", "date"], how="inner")

    if deliveries is not None and len(deliveries):
        d = deliveries[["item_id", "date", "units"]].copy()
        d["date"] = pd.to_datetime(d["date"])
        d = d.groupby(["item_id", "date"], as_index=False)["units"].sum()
        m = m.merge(d, on=["item_id", "date"], how="left")
        m["units"] = m["units"].fillna(0.0)
    else:
        m["units"] = 0.0

    if writeoffs is not None and len(writeoffs):
        w = writeoffs[["item_id", "date", "qty"]].copy()
        w["date"] = pd.to_datetime(w["date"])
        w = w.groupby(["item_id", "date"], as_index=False)["qty"].sum().rename(columns={"qty": "written_off"})
        m = m.merge(w, on=["item_id", "date"], how="left")
        m["written_off"] = m["written_off"].fillna(0.0)
    else:
        m["written_off"] = 0.0

    # damaged or expired units taken off the shelf are a known loss, so they are not shrinkage
    m["actual_drop"] = m["prev_count"] + m["units"] - m["counted_stock"] - m["written_off"]
    return m[["item_id", "date", "actual_drop"]].sort_values(["item_id", "date"]).reset_index(drop=True)


def load_expected(mode="forecast", path=None):
    """Expected demand per item and day: stored forecasts, or recorded sales."""
    if mode == "recorded_sales":
        s = db.read_table("sales", path)
        return s.rename(columns={"units_sold": "expected"})[["item_id", "date", "expected"]]
    hist = db.read_table("expected_demand", path)[["item_id", "date", "expected"]]
    fut = (db.read_table("forecasts", path)
             .rename(columns={"forecast": "expected"})[["item_id", "date", "expected"]])
    fut = fut.merge(hist[["item_id", "date"]], on=["item_id", "date"], how="left", indicator=True)
    fut = fut[fut["_merge"] == "left_only"].drop(columns="_merge")
    return pd.concat([hist, fut], ignore_index=True)


def _shelf_writeoffs(path=None):
    """Damaged and expired units taken off the shelf (not linked to a bill): known losses, not shrinkage."""
    try:
        w = db.read_table("write_offs", path)
    except Exception:
        return None
    if w is None or w.empty:
        return None
    return w[w["txn_id"].isna()][["item_id", "date", "qty"]]


def run_detection(mode="forecast", z_cut=config.Z_CUT, path=None, save=True, items=None):
    """Counts and deliveries from the database -> detections (saved to the database by default).

    items: optionally re-check only these items (fast, used after a single count is entered).
    A day is scored only after the item has 28 earlier days of drops, so a store needs about
    a month of daily counts before the first flags can appear.
    """
    counts = db.read_table("stock_counts", path)
    deliveries = db.read_table("deliveries", path)
    writeoffs = _shelf_writeoffs(path)
    if items is not None:
        items = list(items)
        counts = counts[counts["item_id"].isin(items)]
        deliveries = deliveries[deliveries["item_id"].isin(items)]
        if writeoffs is not None:
            writeoffs = writeoffs[writeoffs["item_id"].isin(items)]
    if counts.empty:
        return None
    drops = drops_from_counts(counts, deliveries, writeoffs)
    frame = drops.merge(load_expected(mode, path), on=["item_id", "date"], how="inner")
    if frame.empty:
        return None
    det = detect(frame, mode=mode, z_cut=z_cut)
    if save:
        out = det[["item_id", "date", "actual_drop", "expected", "z", "flag",
                   "est_missing_units", "severity", "mode"]]
        if items is None:
            db.replace_table("detections", out, path)
        else:
            db.upsert("detections", out, path)
    return det


_ALIASES = {"item": "item_id", "sku": "item_id", "count": "counted_stock", "stock": "counted_stock",
            "counted": "counted_stock", "units_delivered": "delivered", "received": "delivered",
            "delivery": "delivered", "deliveries": "delivered"}


def validate_counts(raw, known_items):
    """Checks an uploaded counts file. Returns (counts, deliveries, errors, warnings)."""
    errors, warnings = [], []
    df = raw.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_")).rename(columns=_ALIASES).copy()
    missing = [c for c in ("item_id", "date", "counted_stock") if c not in df.columns]
    if missing:
        errors.append(f"Missing column(s): {', '.join(missing)}. The file needs item_id, date and counted_stock "
                      "(optional: delivered).")
        return None, None, errors, warnings

    df["item_id"] = df["item_id"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["counted_stock"] = pd.to_numeric(df["counted_stock"], errors="coerce")
    bad = df["date"].isna() | df["counted_stock"].isna() | (df["counted_stock"] < 0)
    if bad.any():
        warnings.append(f"{int(bad.sum())} row(s) with an unreadable date or count, or a negative count, were skipped.")
        df = df[~bad]
    unknown = ~df["item_id"].isin(set(known_items))
    if unknown.any():
        examples = ", ".join(df.loc[unknown, "item_id"].unique()[:3])
        warnings.append(f"{int(unknown.sum())} row(s) for items that are not in the database were skipped (for example {examples}).")
        df = df[~unknown]
    dup = df.duplicated(["item_id", "date"], keep="last")
    if dup.any():
        warnings.append(f"{int(dup.sum())} duplicate item/date row(s): the last one was kept.")
        df = df[~dup]
    if df.empty:
        errors.append("No usable rows remain after cleaning.")
        return None, None, errors, warnings

    counts = df[["item_id", "date", "counted_stock"]].reset_index(drop=True)
    if "delivered" in df.columns:
        deliveries = df[["item_id", "date"]].assign(
            units=pd.to_numeric(df["delivered"], errors="coerce").fillna(0).clip(lower=0)).reset_index(drop=True)
    else:
        deliveries = pd.DataFrame(columns=["item_id", "date", "units"])
    return counts, deliveries, errors, warnings