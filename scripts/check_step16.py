import sqlite3, sys, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stockwise import auth

SCHEMA = """
CREATE TABLE users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT NOT NULL,
    failed_attempts INTEGER DEFAULT 0, locked_until TEXT, created_at TEXT);
CREATE TABLE audit_log (created_at TEXT NOT NULL, username TEXT, action TEXT, detail TEXT);
"""
fd, tmp = tempfile.mkstemp(suffix=".db"); os.close(fd)
con = sqlite3.connect(tmp); con.executescript(SCHEMA)
passed = 0

def check(name, cond):
    global passed
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        sys.exit(1)
    passed += 1

auth.create_user("admin@demo.io", "Admin@1234", "Admin", con)
auth.create_user("cashier@demo.io", "Cashier@1234", "Cashier", con)

ok, user, _ = auth.authenticate("admin@demo.io", "Admin@1234", con)
check("correct password logs in with the right role", ok and user["role"] == "Admin")
ok, _, _ = auth.authenticate("admin@demo.io", "wrong", con)
check("wrong password is refused", not ok)
ok, _, _ = auth.authenticate("nobody@demo.io", "x", con)
check("unknown user is refused", not ok)
ok, _, _ = auth.authenticate("ADMIN@demo.io ", "Admin@1234", con)
check("username is case and space insensitive", ok)

h = con.execute("select password_hash from users where username='admin@demo.io'").fetchone()[0]
check("password is stored hashed, not as plain text", h.startswith("scrypt$") and "Admin@1234" not in h)

for i in range(5):
    auth.authenticate("cashier@demo.io", "bad", con)
ok, _, msg = auth.authenticate("cashier@demo.io", "Cashier@1234", con)
check("account locks after 5 failures, even for the right password", not ok and "ocked" in msg)

con.execute("update users set locked_until='2000-01-01T00:00:00+00:00' where username='cashier@demo.io'")
ok, _, _ = auth.authenticate("cashier@demo.io", "Cashier@1234", con)
check("login works again after the lock expires", ok)

admin_only = [p for p in auth.PAGES["Admin"] if p not in auth.PAGES["Cashier"]]
check("cashier is refused every admin-only page", not any(auth.can_access("Cashier", p) for p in admin_only))
check("cashier can open Shop, Forecast, Shrinkage", all(auth.can_access("Cashier", p) for p in auth.PAGES["Cashier"]))
check("admin can open every page", all(auth.can_access("Admin", p) for p in auth.PAGES["Admin"]))
check("unknown role gets nothing", not auth.can_access("Hacker", "Shop"))

acts = {r[0] for r in con.execute("select action from audit_log")}
check("audit log has login_ok, login_failed, account_locked",
      {"login_ok", "login_failed", "account_locked"} <= acts)

con.close(); os.remove(tmp)
print(f"\nStep 16 checks: {passed} passed")