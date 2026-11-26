"""Central settings for Stockwise. Anything you might want to tune lives here."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

# ---------- Upload format ----------
REQUIRED_COLUMNS = ["item_id", "date", "units_sold"]
OPTIONAL_COLUMNS = ["price", "category", "event"]
COLUMN_ALIASES = {
    "item_id": ["item_id", "item", "sku", "product", "product_id", "item_code"],
    "date": ["date", "day", "sale_date", "transaction_date"],
    "units_sold": ["units_sold", "units", "qty", "quantity", "sold", "sales_units"],
    "price": ["price", "sell_price", "unit_price"],
    "category": ["category", "dept", "department", "dept_id", "cat"],
    "event": ["event", "holiday", "promo", "promotion"],
}

# ---------- Forecast features ----------
LAGS = (7, 14, 28)
ROLL_WINDOWS = (7, 28)
FEATURE_COLUMNS = ["wday", "month", "lag7", "lag14", "lag28", "roll7", "roll28", "std7",
                   "price", "price_ratio", "event", "category_code"]
HISTORY_COLUMNS = ["lag28", "roll28", "std7"]   # rows missing these cannot be used for the model
MIN_HISTORY_DAYS = 90                           # shorter history -> simple rolling-average fallback

# ---------- Forecast model (settings chosen on the validation window in Step 2) ----------
XGB_PARAMS = dict(n_estimators=500, learning_rate=0.03, max_depth=6,
                  subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1)
TEST_BLOCK_DAYS = 28

# ---------- Shrinkage detector (Steps 3b to 4) ----------
SCALE_WINDOW = 28
SCALE_MIN_PERIODS = 14
SCALE_FLOOR = 1.0
Z_CUT = 3.5
SEVERITY_EDGES = (3.5, 5.0, 8.0)                # Low / Medium / High