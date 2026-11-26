"""SQLite storage for Stockwise (one file: data/stockwise.db)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pandas as pd

from . import config

DB_PATH = config.DATA_DIR / "stockwise.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY, category TEXT, first_date TEXT, last_date TEXT,
    n_days INTEGER, mean_daily_units REAL, zero_share REAL, mode TEXT);
CREATE TABLE IF NOT EXISTS sales (
    item_id TEXT NOT NULL, date TEXT NOT NULL, units_sold REAL, price REAL, event INTEGER,
    PRIMARY KEY (item_id, date));
CREATE TABLE IF NOT EXISTS expected_demand (
    item_id TEXT NOT NULL, date TEXT NOT NULL, expected REAL, method TEXT,
    PRIMARY KEY (item_id, date));
CREATE TABLE IF NOT EXISTS forecasts (
    item_id TEXT NOT NULL, date TEXT NOT NULL, forecast REAL, day_ahead INTEGER, method TEXT,
    PRIMARY KEY (item_id, date));
CREATE TABLE IF NOT EXISTS stock_counts (
    item_id TEXT NOT NULL, date TEXT NOT NULL, counted_stock REAL,
    PRIMARY KEY (item_id, date));
CREATE TABLE IF NOT EXISTS deliveries (
    item_id TEXT NOT NULL, date TEXT NOT NULL, units REAL,
    PRIMARY KEY (item_id, date));
CREATE TABLE IF NOT EXISTS detections (
    item_id TEXT NOT NULL, date TEXT NOT NULL, actual_drop REAL, expected REAL, z REAL,
    flag INTEGER, est_missing_units REAL, severity TEXT, mode TEXT,
    PRIMARY KEY (item_id, date));
CREATE TABLE IF NOT EXISTS item_settings (
    item_id TEXT PRIMARY KEY, perishable INTEGER, shelf_life_days INTEGER,
    min_stock REAL, target_stock REAL, purchase_limit INTEGER);
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT NOT NULL,
    failed_attempts INTEGER DEFAULT 0, locked_until TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS transactions (
    txn_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, day TEXT NOT NULL,
    cashier TEXT, payment_mode TEXT, total REAL);
CREATE TABLE IF NOT EXISTS transaction_items (
    txn_id TEXT NOT NULL, item_id TEXT NOT NULL, qty REAL, unit_price REAL,
    PRIMARY KEY (txn_id, item_id));
CREATE TABLE IF NOT EXISTS write_offs (
    write_off_id TEXT PRIMARY KEY, item_id TEXT NOT NULL, date TEXT NOT NULL, qty REAL,
    reason TEXT, txn_id TEXT, note TEXT, entered_by TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS audit_log (
    created_at TEXT NOT NULL, username TEXT, action TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS day_close (
    day TEXT PRIMARY KEY, closed_by TEXT, closed_at TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS investigations (
    item_id TEXT NOT NULL, date TEXT NOT NULL, status TEXT, note TEXT, updated_at TEXT,
    PRIMARY KEY (item_id, date));
"""

TABLES = ("items", "sales", "expected_demand", "forecasts", "stock_counts",
          "deliveries", "detections", "investigations", "item_settings", "users", "transactions", "transaction_items", "write_offs", "audit_log", "day_close")
DATE_COLUMNS = ("date", "first_date", "last_date")


@contextmanager
def connect(path=None):
    con = sqlite3.connect(str(path or DB_PATH))
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db(path=None):
    with connect(path) as con:
        con.executescript(SCHEMA)


def _check(name):
    if name not in TABLES:
        raise ValueError(f"Unknown table: {name}")


def _prepare(df):
    out = df.copy()
    for c in DATE_COLUMNS:
        if c in out.columns:
            out[c] = pd.to_datetime(out[c]).dt.strftime("%Y-%m-%d")
    return out


def replace_table(name, df, path=None):
    """Delete everything in the table and store `df` (used for uploads and forecasts)."""
    _check(name)
    with connect(path) as con:
        con.execute(f"DELETE FROM {name}")
        _prepare(df).to_sql(name, con, if_exists="append", index=False)


def upsert(name, df, path=None):
    """Insert rows, replacing any row with the same primary key (counts, detections, ...)."""
    _check(name)
    out = _prepare(df)
    cols = list(out.columns)
    rows = out.astype(object).where(out.notna(), None).to_numpy().tolist()
    sql = f"INSERT OR REPLACE INTO {name} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    with connect(path) as con:
        con.executemany(sql, rows)


def read_table(name, path=None):
    _check(name)
    with connect(path) as con:
        df = pd.read_sql(f"SELECT * FROM {name}", con)
    for c in DATE_COLUMNS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c])
    return df


def set_investigation(item_id, date, status, note="", path=None):
    row = pd.DataFrame([{"item_id": item_id, "date": date, "status": status, "note": note,
                         "updated_at": datetime.now().isoformat(timespec="seconds")}])
    upsert("investigations", row, path)