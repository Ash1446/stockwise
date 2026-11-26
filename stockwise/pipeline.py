"""Upload -> validate -> forecast -> database."""
import time

from . import db
from .features import build_features, training_frame
from .forecast import fit_model, forecast_next_days, rolling_forecast
from .schema import validate_sales


def run_pipeline(raw, db_path=None, horizon=7, n_blocks=6):
    """raw: the uploaded table (a DataFrame). Returns a summary dict.

    A bad file returns {"ok": False, "errors": [...]} and leaves the database untouched.
    """
    t0 = time.time()
    v = validate_sales(raw)
    if not v.ok:
        return {"ok": False, "errors": v.errors, "warnings": v.warnings}

    feat = build_features(v.data)
    short = v.items.loc[v.items["mode"] == "fallback", "item_id"]
    expected = rolling_forecast(feat, n_blocks=n_blocks, short_items=short)

    n_model = int((v.items["mode"] == "model").sum())
    train = training_frame(feat)
    model = fit_model(train) if (n_model and len(train)) else None
    future = forecast_next_days(v.data, v.items, model, horizon=horizon)

    categories = v.data.groupby("item_id")["category"].first().rename("category").reset_index()
    items = v.items.merge(categories, on="item_id")[
        ["item_id", "category", "first_date", "last_date", "n_days",
         "mean_daily_units", "zero_share", "mode"]]

    db.init_db(db_path)
    db.replace_table("items", items, db_path)
    db.replace_table("sales", v.data[["item_id", "date", "units_sold", "price", "event"]], db_path)
    db.replace_table("expected_demand",
                     expected.rename(columns={"pred": "expected"})[["item_id", "date", "expected", "method"]],
                     db_path)
    db.replace_table("forecasts", future[["item_id", "date", "forecast", "day_ahead", "method"]], db_path)

    return {"ok": True, "errors": [], "warnings": v.warnings, "items": len(items),
            "model_items": n_model, "fallback_items": len(items) - n_model,
            "sales_rows": len(v.data), "expected_rows": len(expected),
            "forecast_rows": len(future), "seconds": round(time.time() - t0, 1)}