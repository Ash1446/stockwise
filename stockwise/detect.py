"""Shrinkage detection.

For each item and day:
    residual = actual stock drop - expected demand
The residual is judged against that item's OWN recent variability (a robust z-score over
the previous 28 days, using only earlier days). A day is flagged when z >= Z_CUT.

Expected demand is either the forecast (mode "forecast") or the recorded sales
(mode "recorded_sales"); the result is labelled with the mode used.
The first 28 days of each item have no scale yet, so they are not scored (z is empty, flag is 0).
"""
import numpy as np
import pandas as pd

from . import config


def _mad(window):
    return np.median(np.abs(window - np.median(window)))


def detect(frame, mode="forecast", z_cut=config.Z_CUT):
    """frame needs: item_id, date, actual_drop, expected. Other columns are kept."""
    df = frame.sort_values(["item_id", "date"]).reset_index(drop=True).copy()
    df["residual"] = df["actual_drop"] - df["expected"]

    g = df.groupby("item_id", sort=False)["residual"]
    w, m = config.SCALE_WINDOW, config.SCALE_MIN_PERIODS
    df["roll_med"] = g.transform(lambda s: s.shift(1).rolling(w, min_periods=m).median())
    mad = g.transform(lambda s: s.shift(1).rolling(w, min_periods=m).apply(_mad, raw=True))
    df["scale"] = np.maximum(1.4826 * mad, config.SCALE_FLOOR)
    df["z"] = (df["residual"] - df["roll_med"]) / df["scale"]

    df["flag"] = (df["z"] >= z_cut).astype(int)
    df["est_missing_units"] = (df["residual"] - df["roll_med"]).clip(lower=0).round(1)

    # severity bands sit at fixed distances above the chosen cutoff (defaults: 3.5 / 5 / 8)
    low_edge, med_edge, high_edge = config.SEVERITY_EDGES
    medium = z_cut + (med_edge - low_edge)
    high = z_cut + (high_edge - low_edge)
    df["severity"] = np.select([df["z"] >= high, df["z"] >= medium, df["z"] >= z_cut],
                               ["High", "Medium", "Low"], default="none")
    df["mode"] = mode
    return df