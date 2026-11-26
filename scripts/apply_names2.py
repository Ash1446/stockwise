import shutil, subprocess, sys
from pathlib import Path
ROOT = Path.cwd()

ui = ROOT / "app" / "ui.py"
t = ui.read_text(encoding="utf-8")
if "def name_of(" not in t:
    shutil.copy(ui, str(ui) + ".bak_names2")
    t += '\n\ndef name_of(item_id):\n    """Product name for an item id (falls back to the id)."""\n    from stockwise import catalog\n    c = catalog.CATALOG.get(item_id)\n    return c["name"] if c else str(item_id)\n'
    ui.write_text(t, encoding="utf-8")
    print("added name_of to app/ui.py")

def patch(rel, edits):
    p = ROOT / "app" / "views" / rel
    src = p.read_text(encoding="utf-8")
    shutil.copy(p, str(p) + ".bak_names2")
    s = src
    for old, new, label in edits:
        n = s.count(old)
        if n == 1:
            s = s.replace(old, new)
        print(("done  " if n == 1 else f"SKIP  (matched {n}x) ") + f"{rel}: {label}")
    p.write_text(s, encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "py_compile", str(p)], capture_output=True, text=True)
    if r.returncode != 0:
        p.write_text(src, encoding="utf-8")
        print(f"FAIL  {rel} did not compile, restored the original\n{r.stderr[-300:]}")

patch("forecast.py", [
    ('format_func=lambda i: f"{i}  ({snap.loc[i, \'category\']})")',
     'format_func=lambda i: f"{ui.name_of(i)}  ({snap.loc[i, \'category\']})")', "product dropdown shows names"),
    ('f"{item} - last {history} days and the next {len(f)} days, units per day"',
     'f"{ui.name_of(item)} - last {history} days and the next {len(f)} days, units per day"', "chart subtitle"),
    ('<b>{theme.esc(item)}</b> is <b>{word}', '<b>{theme.esc(ui.name_of(item))}</b> is <b>{word}', "insight text"),
    ('f"Next {len(f)} days for {item}"', 'f"Next {len(f)} days for {ui.name_of(item)}"', "day-by-day subtitle"),
])

patch("shrinkage.py", [
    ('CURRENCY = "$"', 'CURRENCY = "\\u20b9"', "values in rupees"),
    ('rows.append([f"<b>{theme.esc(r[\'item_id\'])}</b>", theme.esc(r["category"])',
     'rows.append([f"<b>{theme.esc(ui.name_of(r[\'item_id\']))}</b><br><small>{theme.esc(r[\'item_id\'])}</small>", theme.esc(r["category"])',
     "table shows names"),
    ('format_func=lambda n: f"{show.loc[n, \'item_id\']} - ',
     'format_func=lambda n: f"{ui.name_of(show.loc[n, \'item_id\'])} - ', "inspect dropdown shows names"),
])