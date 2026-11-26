"""Simulated shrinkage and stock counts for tests and demos (real labels do not exist publicly)."""
import numpy as np
import pandas as pd


def simulate_shrinkage(frame, rate=0.07, loss_range=(5, 30), noise=2, seed=42):
    """Adds anomaly_label, injected_loss and actual_drop to a table with item_id, date, units_sold.

    actual_drop is the stock drop a physical count would show:
        units sold + injected loss - normal counting noise (+/- `noise` units on every day).
    Same procedure and seed as the Colab experiments.
    """
    df = frame.sort_values(["item_id", "date"]).reset_index(drop=True).copy()
    rng = np.random.default_rng(seed)
    label = np.zeros(len(df), dtype=int)
    loss = np.zeros(len(df), dtype=int)
    for _, g in df.groupby("item_id", sort=False):
        n = int(round(len(g) * rate))
        pick = rng.choice(g.index.to_numpy(), size=n, replace=False)
        label[pick] = 1
        loss[pick] = rng.integers(loss_range[0], loss_range[1] + 1, size=n)
    count_noise = rng.integers(-noise, noise + 1, size=len(df))
    df["anomaly_label"] = label
    df["injected_loss"] = loss
    df["actual_drop"] = df["units_sold"] + df["injected_loss"] - count_noise
    return df


def simulate_counts(frame, start=500, reorder_point=100, order_up_to=500):
    """Turns each item's daily stock drops into the counts and deliveries a store would record.

    frame needs item_id, date, actual_drop. A baseline count is added for the day before the
    first day. When the previous end-of-day count is at or below the reorder point, a delivery
    the next morning brings stock back up to `order_up_to`.
    Returns (counts, deliveries) as DataFrames.
    """
    counts, deliveries = [], []
    for item, g in frame.sort_values(["item_id", "date"]).groupby("item_id", sort=False):
        dates = g["date"].to_numpy()
        drops = g["actual_drop"].to_numpy(dtype=float)
        level = float(start)
        counts.append((item, pd.Timestamp(dates[0]) - pd.Timedelta(days=1), level))
        for d, drop in zip(dates, drops):
            delivery = (order_up_to - level) if level <= reorder_point else 0.0
            if delivery > 0:
                deliveries.append((item, pd.Timestamp(d), delivery))
            level = level + delivery - drop
            counts.append((item, pd.Timestamp(d), level))
    return (pd.DataFrame(counts, columns=["item_id", "date", "counted_stock"]),
            pd.DataFrame(deliveries, columns=["item_id", "date", "units"]))