"""Demand forecasting: XGBoost for items with enough history, a rolling average for the rest."""
import numpy as np
import pandas as pd
import xgboost as xgb

from . import config
from .features import build_features, training_frame


def fit_model(train_df):
    model = xgb.XGBRegressor(**config.XGB_PARAMS)
    model.fit(train_df[config.FEATURE_COLUMNS], train_df["units_sold"])
    return model


def predict(model, frame):
    return np.clip(model.predict(frame[config.FEATURE_COLUMNS]), 0, None)


def fallback_forecast(frame):
    """28-day average (7-day average if there is less history) for short-history items."""
    return frame["roll28"].fillna(frame["roll7"]).fillna(0).clip(lower=0)


def rolling_forecast(feat, n_blocks=6, block_days=config.TEST_BLOCK_DAYS, short_items=()):
    """One-day-ahead forecasts for the last n_blocks * block_days days, retraining every block.

    For each block the model only sees days BEFORE the block, so every prediction is
    out-of-sample. Items without enough history before the block use the fallback.
    """
    usable = training_frame(feat)
    last_day = int(feat["day_num"].max())
    out = []
    for k in range(n_blocks, 0, -1):
        start = last_day - block_days * k
        end = start + block_days
        train = usable[usable["day_num"] <= start]
        test = feat[(feat["day_num"] > start) & (feat["day_num"] <= end)].copy()

        hist_days = feat[feat["day_num"] <= start].groupby("item_id")["units_sold"].size()
        enough = hist_days.index[hist_days >= config.MIN_HISTORY_DAYS]
        ok = (test["item_id"].isin(enough)
              & ~test["item_id"].isin(list(short_items))
              & test[config.HISTORY_COLUMNS].notna().all(axis=1))

        pred = fallback_forecast(test)
        if ok.any():
            model = fit_model(train)
            pred.loc[ok] = predict(model, test.loc[ok])
        test["pred"] = pred
        test["method"] = np.where(ok, "model", "fallback")
        test["block"] = n_blocks - k + 1
        out.append(test[["item_id", "date", "day_num", "category", "units_sold",
                         "pred", "lag7", "roll28", "method", "block"]])
    return pd.concat(out, ignore_index=True)


def forecast_next_days(data, items, model, horizon=7):
    """Forecast the next `horizon` days for every item.

    data  : clean table from validate_sales().data
    items : summary table from validate_sales().items (has the 'mode' column)
    Model items are forecast day by day, each predicted day feeding the next day's features.
    Short-history items get a flat forecast equal to their recent 28-day average.
    The forecast for each item starts the day after that item's last date.
    """
    model_items = set(items.loc[items["mode"] == "model", "item_id"])
    price_median = data.groupby("item_id")["price"].median()
    rows = []

    # --- items forecast by the model ---
    ext = data[data["item_id"].isin(model_items)].groupby("item_id", sort=False).tail(60).copy()
    ext["is_new"] = False
    for h in (range(1, horizon + 1) if model_items else []):
        ext = ext.sort_values(["item_id", "date"]).reset_index(drop=True)
        newest = ext.groupby("item_id").tail(1).copy()
        newest["date"] = newest["date"] + pd.Timedelta(days=1)
        newest["event"] = 0
        newest["units_sold"] = np.nan
        newest["is_new"] = True
        ext = pd.concat([ext, newest], ignore_index=True)
        ext = ext.sort_values(["item_id", "date"]).reset_index(drop=True)

        feat = build_features(ext, price_median=price_median)
        mask = feat["is_new"].to_numpy(dtype=bool)
        p = predict(model, feat.loc[mask])
        rows.append(pd.DataFrame({"item_id": feat.loc[mask, "item_id"].to_numpy(),
                                  "date": feat.loc[mask, "date"].to_numpy(),
                                  "forecast": p, "day_ahead": h, "method": "model"}))
        ext.loc[mask, "units_sold"] = p
        ext["is_new"] = False

    # --- short-history items: flat recent average ---
    level = data.groupby("item_id")["units_sold"].apply(lambda s: float(s.tail(28).mean()))
    for item, last_date in items.loc[items["mode"] == "fallback", ["item_id", "last_date"]].itertuples(index=False):
        dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon)
        rows.append(pd.DataFrame({"item_id": item, "date": dates, "forecast": level[item],
                                  "day_ahead": range(1, horizon + 1), "method": "fallback"}))

    return pd.concat(rows, ignore_index=True).sort_values(["item_id", "date"]).reset_index(drop=True)