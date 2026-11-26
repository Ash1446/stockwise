"""HTTP API for the Stockwise web app. Run from the project root:
    C:\\st_env\\Scripts\\python.exe -m uvicorn stockwise.api:app --port 8000
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import FileResponse

from . import db

FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
app = FastAPI(title="Stockwise API")

ITEMS_SQL = """
SELECT i.item_id, i.category, i.mean_daily_units, i.mode,
       s.min_stock, s.target_stock, s.perishable, s.shelf_life_days, s.purchase_limit,
       c.counted_stock AS stock, c.date AS count_date,
       (SELECT price FROM sales WHERE item_id = i.item_id ORDER BY date DESC LIMIT 1) AS price
FROM items i
LEFT JOIN item_settings s ON s.item_id = i.item_id
LEFT JOIN stock_counts c ON c.item_id = i.item_id
     AND c.date = (SELECT MAX(date) FROM stock_counts WHERE item_id = i.item_id)
ORDER BY i.item_id
"""

DASH_SQL = """
SELECT e.date AS date, SUM(s.units_sold) AS actual, SUM(e.expected) AS predicted
FROM expected_demand e JOIN sales s ON s.item_id = e.item_id AND s.date = e.date
GROUP BY e.date ORDER BY e.date DESC LIMIT 14
"""


def _query(sql):
    with db.connect() as con:
        return pd.read_sql_query(sql, con)


def _records(df):
    return json.loads(df.to_json(orient="records"))


@app.get("/api/items")
def items():
    df = _query(ITEMS_SQL)
    df["stock"] = df["stock"].fillna(0)          # no count on file is treated as out of stock
    df["status"] = np.select([df["stock"] <= 0, df["stock"] < df["min_stock"]],
                             ["Out of stock", "Low stock"], default="Healthy")
    df["to_add"] = (df["target_stock"] - df["stock"]).clip(lower=0).round()
    return _records(df)


@app.get("/api/dashboard")
def dashboard():
    return {"series": _records(_query(DASH_SQL).iloc[::-1])}


@app.get("/")
def index():
    return FileResponse(FRONTEND)