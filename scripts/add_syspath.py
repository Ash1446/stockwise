import re, shutil
p = r"app\main.py"
t = open(p, encoding="utf-8", newline="").read()
if "parents[1]" in t:
    print("already has a sys.path fix")
else:
    shutil.copy(p, p + ".bak_syspath")
    nl = "\r\n" if "\r\n" in t else "\n"
    fix = nl.join(["import sys", "from pathlib import Path", "sys.path.insert(0, str(Path(__file__).resolve().parents[1]))", ""]) + nl
    m = re.search(r"^(?:import|from)\s+(?!__future__)", t, re.M)
    t = t[:m.start()] + fix + t[m.start():]
    open(p, "w", encoding="utf-8", newline="").write(t)
    print("added")
