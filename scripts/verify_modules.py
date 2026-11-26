"""Imports every module in the stockwise package and checks that each still has its main functions."""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
bad = False
for p in sorted((ROOT / "stockwise").glob("*.py")):
    if p.stem == "__init__":
        continue
    try:
        importlib.import_module(f"stockwise.{p.stem}")
        print("OK    ", p.stem)
    except Exception as e:
        print("FAIL  ", p.stem, type(e).__name__, str(e)[:110])
        bad = True
need = {"counts": ["drops_from_counts", "run_detection", "load_expected", "validate_counts"],
        "catalog": ["CATALOG", "EXCLUDED", "info"], "billing": ["record_sale", "stock_now", "bill_list"],
        "auth": ["authenticate", "PAGES"], "writeoffs": ["record_write_off"], "eod": ["close_day"],
        "analysis": ["summary", "bounds"], "db": ["read_table"], "detect": ["detect"]}
for mod, names in need.items():
    try:
        m = importlib.import_module(f"stockwise.{mod}")
    except Exception:
        continue
    missing = [n for n in names if not hasattr(m, n)]
    if missing:
        print("FAIL  ", mod, "is missing", missing)
        bad = True
print("ALL MODULES LOOK RIGHT" if not bad else "PROBLEMS FOUND, paste this output")
sys.exit(1 if bad else 0)