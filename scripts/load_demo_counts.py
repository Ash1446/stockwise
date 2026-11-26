"""Loads SIMULATED demo counts into data/stockwise.db and runs detection. Run from the project root:
    C:\\st_env\\Scripts\\python.exe scripts\\load_demo_counts.py
The counts are simulated (injected shrinkage) and must be labelled as demo data in the app.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stockwise import db
from stockwise.counts import run_detection
from stockwise.simulate import simulate_counts, simulate_shrinkage

sales = db.read_table("sales")
exp = db.read_table("expected_demand")
frame = sales.merge(exp[["item_id", "date"]], on=["item_id", "date"], how="inner")
counts, deliveries = simulate_counts(simulate_shrinkage(frame))
db.upsert("stock_counts", counts)
db.upsert("deliveries", deliveries)
det = run_detection("forecast")
print(f"Saved {len(counts):,} counts and {len(deliveries):,} deliveries (simulated demo data).")
print(f"Detections saved: {len(det):,} rows, {int(det['flag'].sum())} flagged.")
print(det[det["flag"] == 1]["severity"].value_counts().to_string())