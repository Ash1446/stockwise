"""Offline check: every database item has exactly one catalogue entry, with sane values."""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stockwise import catalog

ids = {r[0] for r in sqlite3.connect(ROOT / "data" / "stockwise.db").execute("select item_id from items")} - catalog.EXCLUDED
cat = set(catalog.CATALOG)
names = [c["name"] for c in catalog.CATALOG.values()]
checks = [
    ("every database item has a catalogue entry", not (ids - cat), f"missing: {sorted(ids - cat)}"),
    ("no catalogue entry for an unknown item", not (cat - ids), f"extra: {sorted(cat - ids)}"),
    ("99 items in the catalogue (1 hidden on request)", len(cat) == 99, f"found {len(cat)}"),
    ("product names are all different", len(set(names)) == len(names), "duplicate names"),
    ("all prices are positive rupee amounts", all(c["price"] > 0 for c in catalog.CATALOG.values()), ""),
    ("all groups are known", all(c["group"] in catalog.GROUPS for c in catalog.CATALOG.values()), ""),
    ("every item has an emoji and a photo title", all(c["emoji"] and c["wiki"] for c in catalog.CATALOG.values()), ""),
]
bad = False
for name, ok, why in checks:
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  -> " + why))
    bad = bad or not ok
by_group = {}
for c in catalog.CATALOG.values():
    by_group[c["group"]] = by_group.get(c["group"], 0) + 1
print("items per group:", by_group)
sys.exit(1 if bad else 0)