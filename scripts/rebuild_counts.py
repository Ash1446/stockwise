r"""Rebuilds stockwise/counts.py from the saved original, with shelf write-offs treated as known loss."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
orig = ROOT / "stockwise" / "counts.py.bak_writeoffs"
dest = ROOT / "stockwise" / "counts.py"
src = orig.read_text(encoding="utf-8")
for need in ("def drops_from_counts(", "def load_expected(", "def run_detection(", "def validate_counts("):
    if need not in src:
        sys.exit(f"The backup does not look like the original counts.py (missing {need}). Nothing was changed.")


def swap(text, old, new):
    if text.count(old) != 1:
        sys.exit(f"Expected exactly one match for {old.strip()[:70]!r} but found {text.count(old)}. Nothing was changed.")
    return text.replace(old, new)


NEW1 = '''    if writeoffs is not None and len(writeoffs):
        w = writeoffs[["item_id", "date", "qty"]].copy()
        w["date"] = pd.to_datetime(w["date"])
        w = w.groupby(["item_id", "date"], as_index=False)["qty"].sum().rename(columns={"qty": "written_off"})
        m = m.merge(w, on=["item_id", "date"], how="left")
        m["written_off"] = m["written_off"].fillna(0.0)
    else:
        m["written_off"] = 0.0

    # damaged or expired units taken off the shelf are a known loss, so they are not shrinkage
    m["actual_drop"] = m["prev_count"] + m["units"] - m["counted_stock"] - m["written_off"]
'''

NEW2 = '''def _shelf_writeoffs(path=None):
    """Damaged and expired units taken off the shelf (not linked to a bill): known losses, not shrinkage."""
    try:
        w = db.read_table("write_offs", path)
    except Exception:
        return None
    if w is None or w.empty:
        return None
    return w[w["txn_id"].isna()][["item_id", "date", "qty"]]


def run_detection(mode="forecast", z_cut=config.Z_CUT, path=None, save=True, items=None):'''

s = src
s = swap(s, "def drops_from_counts(counts, deliveries=None):", "def drops_from_counts(counts, deliveries=None, writeoffs=None):")
s = swap(s, '    m["actual_drop"] = m["prev_count"] + m["units"] - m["counted_stock"]\n', NEW1)
s = swap(s, 'def run_detection(mode="forecast", z_cut=config.Z_CUT, path=None, save=True, items=None):', NEW2)
s = swap(s, '    deliveries = db.read_table("deliveries", path)\n',
         '    deliveries = db.read_table("deliveries", path)\n    writeoffs = _shelf_writeoffs(path)\n')
s = swap(s, '        deliveries = deliveries[deliveries["item_id"].isin(items)]\n',
         '        deliveries = deliveries[deliveries["item_id"].isin(items)]\n'
         '        if writeoffs is not None:\n            writeoffs = writeoffs[writeoffs["item_id"].isin(items)]\n')
s = swap(s, "    drops = drops_from_counts(counts, deliveries)\n", "    drops = drops_from_counts(counts, deliveries, writeoffs)\n")
compile(s, "counts.py", "exec")
dest.write_text(s, encoding="utf-8")
print(f"rebuilt {dest.name}: {len(s)} characters")