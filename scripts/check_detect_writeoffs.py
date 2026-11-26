"""Checks that shelf write-offs are treated as explained loss by the detector, on a COPY of the database."""
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from stockwise import config, db
from stockwise import counts as cn
from stockwise.detect import detect

failed = False


def chk(name, ok, extra=""):
    global failed
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + str(extra)) if (extra and not ok) else ""))
    failed = failed or not ok


# 1. the formula on a tiny example
c = pd.DataFrame({"item_id": ["X", "X"], "date": ["2016-01-01", "2016-01-02"], "counted_stock": [100.0, 90.0]})
dl = pd.DataFrame({"item_id": ["X"], "date": ["2016-01-02"], "units": [5.0]})
wo = pd.DataFrame({"item_id": ["X", "X"], "date": ["2016-01-02", "2016-01-02"], "qty": [3.0, 1.0]})
chk("without write-offs the drop is the old formula (100 + 5 - 90 = 15)", cn.drops_from_counts(c, dl)["actual_drop"].iloc[0] == 15)
chk("an empty write-off table changes nothing", cn.drops_from_counts(c, dl, wo.iloc[0:0])["actual_drop"].iloc[0] == 15)
chk("write-offs on the same day are summed and subtracted (15 - 4 = 11)", cn.drops_from_counts(c, dl, wo)["actual_drop"].iloc[0] == 11)
other = wo.assign(date="2016-03-01")
chk("a write-off on another day changes nothing", cn.drops_from_counts(c, dl, other)["actual_drop"].iloc[0] == 15)

# 2. on a copy of your real database
tmp = Path(tempfile.mkdtemp()) / "copy.db"
shutil.copy(ROOT / "data" / "stockwise.db", tmp)
con = sqlite3.connect(tmp)
con.execute("DELETE FROM write_offs")
con.commit()
p = str(tmp)
counts_df, deliv_df = db.read_table("stock_counts", p), db.read_table("deliveries", p)
frame = cn.drops_from_counts(counts_df, deliv_df).merge(cn.load_expected("forecast", p), on=["item_id", "date"], how="inner")
old = detect(frame, mode="forecast", z_cut=config.Z_CUT).sort_values(["item_id", "date"]).reset_index(drop=True)
new = cn.run_detection(mode="forecast", path=p, save=False).sort_values(["item_id", "date"]).reset_index(drop=True)
same = len(old) == len(new) and (old["flag"].values == new["flag"].values).all() \
    and abs(old["actual_drop"].values - new["actual_drop"].values).max() < 1e-9 \
    and abs(old["z"].fillna(0).values - new["z"].fillna(0).values).max() < 1e-9
chk(f"with no write-offs the detections are identical to the old formula ({len(new)} item-days, {int(new['flag'].sum())} flags)", same)

# 3. a shelf write-off on a flagged day
row = con.execute("SELECT item_id, date FROM detections WHERE flag=1 ORDER BY z DESC LIMIT 1").fetchone()
if row is None:
    print("SKIP  no flagged day in the database to test with")
else:
    item, day = row[0], str(row[1])[:10]

    def cell(det):
        r = det[(det["item_id"] == item) & (det["date"] == pd.Timestamp(day))]
        return None if r.empty else r.iloc[0]

    base = cell(cn.run_detection(mode="forecast", path=p, save=False, items=[item]))
    ins = "INSERT INTO write_offs (write_off_id, item_id, date, qty, reason, txn_id, note, entered_by, created_at) VALUES (?,?,?,?,?,?,?,?,?)"
    con.execute(ins, ("W-TEST-1", item, day, 5, "Damaged", None, "", "admin@demo.io", "2016-01-01T00:00:00+00:00"))
    con.commit()
    after = cell(cn.run_detection(mode="forecast", path=p, save=False, items=[item]))
    chk("the flagged day is found before and after", base is not None and after is not None)
    if base is not None and after is not None:
        chk(f"a 5-unit shelf write-off lowers that day's drop by exactly 5 ({base['actual_drop']:.1f} -> {after['actual_drop']:.1f})",
            abs((base["actual_drop"] - 5) - after["actual_drop"]) < 1e-9)
        chk("and lowers the estimated missing units", after["est_missing_units"] < base["est_missing_units"],
            (base["est_missing_units"], after["est_missing_units"]))
    con.execute("DELETE FROM write_offs")
    con.execute(ins, ("W-TEST-2", item, day, 5, "Damaged", "T20160101-0001", "", "admin@demo.io", "2016-01-01T00:00:00+00:00"))
    con.commit()
    linked = cell(cn.run_detection(mode="forecast", path=p, save=False, items=[item]))
    chk("a write-off linked to a bill does not change the detection",
        linked is not None and base is not None and abs(linked["actual_drop"] - base["actual_drop"]) < 1e-9)
con.close()
sys.exit(1 if failed else 0)