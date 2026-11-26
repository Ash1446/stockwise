"""Builds data/stockwise.db from the M5 sample upload. Run from the project root:
    C:\\st_env\\Scripts\\python.exe scripts\\build_sample_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from stockwise import config, db
from stockwise.pipeline import run_pipeline

raw = pd.read_csv(config.DATA_DIR / "sample_sales_upload.csv")
out = run_pipeline(raw)
print(out)
print("Database:", db.DB_PATH, f"({db.DB_PATH.stat().st_size / 1e6:.1f} MB)")