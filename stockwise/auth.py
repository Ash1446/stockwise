"""Login, roles and lockout for Stockwise (Step 16)."""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "stockwise.db"
MAX_ATTEMPTS = 5
LOCK_MINUTES = 15
_N, _R, _P = 2**14, 8, 1

# Page names must match the labels in your sidebar.
PAGES = {
    "Admin": ["Dashboard", "Shop", "Inventory", "Stock counts", "Demand forecast",
              "Shrinkage detection", "Write-offs", "End of day",
              "Sales analysis"],
    "Cashier": ["Shop", "Demand forecast", "Shrinkage detection"],
}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, h = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt),
                              n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except (ValueError, TypeError):
        return False


_DUMMY = hash_password("dummy-password")  # keeps timing similar for unknown users


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _connect(con):
    if con is not None:
        return con, False
    return sqlite3.connect(DB_PATH), True


def _audit(con, username, action, detail=""):
    con.execute("INSERT INTO audit_log (created_at, username, action, detail) VALUES (?,?,?,?)",
                (_now().isoformat(), username, action, detail))


def create_user(username: str, password: str, role: str, con=None) -> None:
    if role not in PAGES:
        raise ValueError(f"Unknown role: {role}")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    con, own = _connect(con)
    try:
        con.execute(
            "INSERT OR REPLACE INTO users (username, password_hash, role, failed_attempts, locked_until, created_at) "
            "VALUES (?,?,?,0,NULL,?)",
            (username.strip().lower(), hash_password(password), role, _now().isoformat()))
        _audit(con, username.strip().lower(), "user_created", role)
    finally:
        con.commit()
        if own:
            con.close()


def authenticate(username: str, password: str, con=None):
    """Returns (ok, user_dict_or_None, message)."""
    username = (username or "").strip().lower()
    password = password or ""
    con, own = _connect(con)
    try:
        row = con.execute(
            "SELECT username, password_hash, role, failed_attempts, locked_until "
            "FROM users WHERE username=?", (username,)).fetchone()
        if row is None:
            verify_password(password, _DUMMY)
            _audit(con, username, "login_failed", "unknown user")
            return False, None, "Invalid username or password."

        _, ph, role, failed, locked_until = row
        now = _now()
        if locked_until and datetime.fromisoformat(locked_until) > now:
            mins = int((datetime.fromisoformat(locked_until) - now).total_seconds() // 60) + 1
            _audit(con, username, "login_blocked", "account locked")
            return False, None, f"Account locked. Try again in about {mins} min."

        if verify_password(password, ph):
            con.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE username=?", (username,))
            _audit(con, username, "login_ok", role)
            return True, {"username": username, "role": role}, "OK"

        failed = (failed or 0) + 1
        if failed >= MAX_ATTEMPTS:
            until = (now + timedelta(minutes=LOCK_MINUTES)).isoformat()
            con.execute("UPDATE users SET failed_attempts=0, locked_until=? WHERE username=?", (until, username))
            _audit(con, username, "account_locked", f"{MAX_ATTEMPTS} failed attempts")
            return False, None, f"Too many failed attempts. Locked for {LOCK_MINUTES} minutes."
        con.execute("UPDATE users SET failed_attempts=? WHERE username=?", (failed, username))
        _audit(con, username, "login_failed", f"attempt {failed}")
        return False, None, "Invalid username or password."
    finally:
        con.commit()
        if own:
            con.close()


def log_logout(username: str, con=None) -> None:
    con, own = _connect(con)
    try:
        _audit(con, username, "logout")
    finally:
        con.commit()
        if own:
            con.close()


def can_access(role: str, page: str) -> bool:
    return page in PAGES.get(role, [])


def require_page(page: str) -> None:
    """Call at the top of every Streamlit page."""
    import streamlit as st
    user = st.session_state.get("user")
    if not user:
        st.warning("Please sign in.")
        st.stop()
    if not can_access(user["role"], page):
        st.error("Your role does not have access to this page.")
        st.stop()