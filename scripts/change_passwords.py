"""Sets new passwords for the two demo accounts. Passwords are typed here and never saved in a file."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stockwise import auth

for user, role in (("admin@demo.io", "Admin"), ("cashier@demo.io", "Cashier")):
    while True:
        p1 = getpass.getpass(f"New password for {user} (at least 8 characters): ")
        p2 = getpass.getpass("Type it again: ")
        if len(p1) < 8:
            print("Too short, try again.")
        elif p1 != p2:
            print("They do not match, try again.")
        else:
            break
    auth.create_user(user, p1, role)
    ok, _, _ = auth.authenticate(user, p1)
    print(f"{user}: password updated, login test {'OK' if ok else 'FAILED'}")