"""Feature engineering for the demand forecast.

Every lag and rolling value uses ONLY earlier days, never the day being predicted.
"""
import pandas as pd

from . import config


def build_features(data: pd.DataFrame, price_median=None) -> pd.DataFrame:
    """price_median: optional Series (item_id -> typical price). Pass it when `data` is only
    a recent slice of the history, so price_ratio still uses the full-history median."""
    df = data.sort_values(["item_id", "date"]).reset_index(drop=True).copy()
    g = df.groupby("item_id", sort=False)["units_sold"]

    df["wday"] = df["date"].dt.dayofweek.astype("int8")
    df["month"] = df["date"].dt.month.astype("int8")
    df["day_num"] = (df["date"] - df["date"].min()).dt.days.astype("int32")

    for k in config.LAGS:
        df[f"lag{k}"] = g.shift(k)
    for w in config.ROLL_WINDOWS:
        df[f"roll{w}"] = g.transform(lambda s, w=w: s.shift(1).rolling(w).mean())
    df["std7"] = g.transform(lambda s: s.shift(1).rolling(7).std())

    if price_median is None:
        median = df.groupby("item_id")["price"].transform("median")
    else:
        median = df["item_id"].map(price_median)
    df["price_ratio"] = (df["price"] / median).astype("float32")
    df["category_code"] = pd.factorize(df["category"], sort=True)[0].astype("int16")
    return df


def training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Rows with enough history for all features (the first 28 days of each item are dropped)."""
    return df.dropna(subset=config.HISTORY_COLUMNS).reset_index(drop=True)