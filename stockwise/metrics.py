"""Accuracy metrics used in the report."""
import numpy as np
import pandas as pd


def wape(y, p):
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    return float(np.abs(y - p).sum() / max(np.abs(y).sum(), 1e-9))


def accuracy_table(res, columns):
    """res needs item_id, day_num, category, units_sold and one column per forecaster.
    columns: {display name: column name}. Weeks are 7-day windows from the start of the test period."""
    week = (res["day_num"] - res["day_num"].min()) // 7
    rows = []
    for name, col in columns.items():
        err = res["units_sold"] - res[col]
        daily = res.groupby("day_num")[["units_sold", col]].sum()
        weekly = res.assign(week=week).groupby(["category", "week"])[["units_sold", col]].sum()
        rows.append({"model": name,
                     "MAE": float(err.abs().mean()),
                     "RMSE": float(np.sqrt((err ** 2).mean())),
                     "WAPE": wape(res["units_sold"], res[col]),
                     "1-WAPE store-day": 1 - wape(daily["units_sold"], daily[col]),
                     "1-WAPE category-week": 1 - wape(weekly["units_sold"], weekly[col])})
    return pd.DataFrame(rows)