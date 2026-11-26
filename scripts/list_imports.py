import re, sys, pathlib
std = sys.stdlib_module_names
found = set()
for p in list(pathlib.Path("app").rglob("*.py")) + list(pathlib.Path("stockwise").rglob("*.py")):
    for m in re.findall(r"^\s*(?:import|from)\s+(\w+)", p.read_text(encoding="utf-8", errors="ignore"), re.M):
        if m not in std and m not in ("app", "stockwise"):
            found.add(m)
print(sorted(found))
