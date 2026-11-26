import re, shutil, subprocess, sys
from pathlib import Path

p = Path.cwd() / "app" / "shell.py"
src = p.read_text(encoding="utf-8")
pat = re.compile(r'\n        st\.caption\("Demo accounts.*?\n        c2\.button\([^\n]*\n', re.S)
if len(pat.findall(src)) != 1:
    sys.exit("Could not find the demo-account buttons exactly once. Nothing changed.")
shutil.copy(p, str(p) + ".bak_nodemo")
out = pat.sub("\n", src)
p.write_text(out, encoding="utf-8")
r = subprocess.run([sys.executable, "-m", "py_compile", str(p)], capture_output=True, text=True)
if r.returncode != 0:
    p.write_text(src, encoding="utf-8")
    sys.exit("shell.py did not compile, original restored:\n" + r.stderr[-300:])
print("demo buttons removed from the login page")