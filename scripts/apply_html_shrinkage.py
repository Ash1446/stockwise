import shutil, subprocess, sys
from pathlib import Path

p = Path.cwd() / "app" / "views" / "shrinkage.py"
src = p.read_text(encoding="utf-8")
START = '    reviewed = int((view["review"] != "open").sum())\n'
END = '    options = list(range(len(show)))\n'
IMP = "from app import theme, ui\n"
for name, m in (("start marker", START), ("end marker", END), ("import line", IMP)):
    if src.count(m) != 1:
        sys.exit(f"{name} found {src.count(m)} times, expected 1. Nothing changed.")
a, b = src.index(START), src.index(END)
if a > b:
    sys.exit("markers are in the wrong order. Nothing changed.")

NEW = '''    if view.empty:
        st.info("No flagged days match these filters.")
        return

    show = view.head(MAX_ROWS).reset_index(drop=True)

    def _n(v):
        return None if pd.isna(v) else int(round(float(v)))

    rows = []
    for _, r in show.iterrows():
        d, iid = r["date"], r["item_id"]
        ci = counts[counts["item_id"] == iid]
        before = ci[ci["date"] < d].sort_values("date").tail(1)
        now = ci[ci["date"] == d]
        got = deliv[(deliv["item_id"] == iid) & (deliv["date"] == d)]["units"].sum()
        sold = sales[(sales["item_id"] == iid) & (sales["date"] == d)]["units_sold"].sum()
        counted = _n(now["counted_stock"].iloc[0]) if len(now) else None
        missing = _n(r["est_missing_units"]) or 0
        rows.append({
            "id": iid, "name": ui.name_of(iid), "category": str(r["category"]), "date": f"{d:%d %b %Y}",
            "opening": _n(before["counted_stock"].iloc[0]) if len(before) else None,
            "received": _n(got), "sold": _n(sold),
            "expected": None if counted is None else counted + missing, "counted": counted,
            "severity": str(r["severity"]), "review": STATUS_BADGE.get(r["review"], ("Open", "warn"))[0],
        })
    known = [x for x in rows if x["counted"] is not None]
    payload = {
        "flagged": len(view), "items": int(view["item_id"].nunique()),
        "expected": sum(x["expected"] for x in known), "counted": sum(x["counted"] for x in known),
        "variance": sum(x["counted"] - x["expected"] for x in known), "value": _money(view["value"].sum()),
        "rows": rows,
    }
    st.caption(f"Ranked by estimated value. Showing {len(show)} of {len(view)} flagged days.")
    htmlviews.shrinkage(payload, len(rows))

'''
out = src[:a] + NEW + src[b:]
out = out.replace(IMP, "from app import htmlviews, theme, ui\n").replace('CURRENCY = "$"', 'CURRENCY = "\\u20b9"', 1)
shutil.copy(p, str(p) + ".bak_html2")
p.write_text(out, encoding="utf-8")
r = subprocess.run([sys.executable, "-m", "py_compile", str(p)], capture_output=True, text=True)
if r.returncode != 0:
    p.write_text(src, encoding="utf-8")
    sys.exit("shrinkage.py did not compile, original restored:\n" + r.stderr[-400:])
print("shrinkage.py patched")