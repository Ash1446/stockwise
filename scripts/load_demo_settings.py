"""Adds the new tables and demo item settings to data/stockwise.db. Run from the project root:
    C:\\st_env\\Scripts\\python.exe scripts\\load_demo_settings.py
Perishables and purchase limits here are DEMO ASSUMPTIONS and must be labelled as such in the app.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stockwise import db
from stockwise.settings import ensure_item_settings

db.init_db()
n = ensure_item_settings(demo=True, overwrite=True)
s = db.read_table("item_settings").merge(db.read_table("items")[["item_id", "category"]], on="item_id")
print(f"Wrote settings for {n} items.")
print("Perishable items by department:")
print(s[s["perishable"] == 1]["category"].value_counts().to_string())
print("Shelf life (days):", sorted(s["shelf_life_days"].dropna().unique()))
print("Items with a purchase limit:", int(s["purchase_limit"].notna().sum()))
print(s.sort_values("target_stock", ascending=False).head(6)[
    ["item_id", "category", "perishable", "min_stock", "target_stock", "purchase_limit"]].to_string(index=False))