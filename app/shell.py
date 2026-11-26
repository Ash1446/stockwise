"""Login screen, navy sidebar and shared CSS for Stockwise (Step 16)."""
from __future__ import annotations

import streamlit as st

from stockwise import auth

CSS = """
<style>
[data-testid="stSidebar"]{background:#0f1f33;}
[data-testid="stSidebar"] *{color:#e6ebf2;}
[data-testid="stSidebar"] hr{border-color:#2a3b52;}
[data-testid="stSidebar"] .stButton button{background:transparent;border:1px solid #3a4d68;color:#fff;border-radius:10px;width:100%;}
[data-testid="stSidebar"] .stButton button:hover{border-color:#fff;}
.sw-brand{display:flex;gap:12px;align-items:center;margin:4px 0 14px 0;}
.sw-logo{width:38px;height:38px;border-radius:11px;background:#1a56db;color:#fff;display:grid;place-items:center;font-weight:700;}
.sw-brand b{display:block;font-size:14px;color:#fff;}
.sw-brand small{font-size:9px;letter-spacing:.2em;color:#9fb0c6;}
.sw-me{display:flex;gap:10px;align-items:center;padding:10px;border:1px solid #2a3b52;border-radius:14px;margin-bottom:10px;}
.sw-av{width:34px;height:34px;border-radius:50%;background:#1a56db;color:#fff;display:grid;place-items:center;font-weight:600;font-size:12px;}
.sw-me b{display:block;font-size:12.5px;color:#fff;}
.sw-me span{font-size:11px;color:#9fb0c6;}
.sw-left{background:#f1f4f8;border:1px solid #e6e8ec;border-radius:18px;padding:36px;}
.sw-left h1{font-size:36px;line-height:1.15;margin:26px 0 12px 0;letter-spacing:-.02em;color:#0f1b2d;}
.sw-left p{color:#6b7686;line-height:1.6;}
.sw-bul{display:grid;gap:10px;color:#4b5565;margin:18px 0 22px 0;}
.sw-credits{border-top:1px solid #d5dbe3;padding-top:14px;font-size:12.5px;color:#6b7686;line-height:1.7;}
.sw-credits b{color:#0f1b2d;}
.sw-left .sw-brand b{color:#0f1b2d;}
.sw-left .sw-brand small{color:#6b7686;}
.sw-left .sw-logo{background:#0f1f33;}
</style>
"""

HIDE_SIDEBAR = """
<style>
[data-testid="stSidebar"],[data-testid="collapsedControl"],[data-testid="stSidebarCollapsedControl"]{display:none;}
.block-container{padding-top:2.5rem;}
</style>
"""

LEFT_HTML = (
    '<div class="sw-left">'
    '<div class="sw-brand"><div class="sw-logo">S</div>'
    '<div><b>Stockwise</b><small>PREDICTIVE INVENTORY INTELLIGENCE</small></div></div>'
    '<h1>Smarter inventory.<br>Better decisions.</h1>'
    '<p>Forecast demand for every item and flag stock that disappears faster '
    'than demand can explain.</p>'
    '<div class="sw-bul">'
    '<div>&#9650;&nbsp; Demand forecasts per item (XGBoost)</div>'
    '<div>&#9679;&nbsp; Shrinkage flags from forecast-aware anomaly detection</div>'
    '<div>&#9632;&nbsp; 100 items across 7 departments</div>'
    '</div>'
    '<div class="sw-credits"><b>Stanley College of Engineering &amp; Technology for Women</b><br>'
    'Department of Computer Science &amp; Engineering (2026-27)<br>'
    '<b>Guide:</b> Mrs. K Naga Neeharika<br>'
    '<b>Team:</b> Mekala Madhu Mitha | Aasila Malhat | Kallepalli Suvarna</div>'
    '</div>'
)


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def _fill(username: str, password: str) -> None:
    st.session_state["login_user"] = username
    st.session_state["login_pass"] = password


def login_screen() -> None:
    inject_css()
    st.markdown(HIDE_SIDEBAR, unsafe_allow_html=True)
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.markdown(LEFT_HTML, unsafe_allow_html=True)
    with right:
        st.markdown("## Welcome back")
        st.caption("Sign in with your assigned role.")
        with st.form("login_form"):
            username = st.text_input("Email address", key="login_user", placeholder="admin@demo.io")
            password = st.text_input("Password", type="password", key="login_pass")
            submitted = st.form_submit_button("Sign in", width='stretch')
        if submitted:
            ok, user, msg = auth.authenticate(username, password)
            if ok:
                st.session_state.user = user
                st.session_state.logged_in = True
                st.session_state.pop("login_pass", None)
                st.rerun()
            else:
                st.error(msg)


def logout() -> None:
    user = st.session_state.get("user")
    if user:
        auth.log_logout(user["username"])
    for k in ("user", "logged_in", "nav", "inv_item", "login_pass"):
        st.session_state.pop(k, None)
    st.rerun()


def sidebar(allowed: list[str]) -> str:
    user = st.session_state.user
    if st.session_state.get("nav") not in allowed:
        st.session_state.pop("nav", None)
    name = user["username"].split("@")[0].title()
    with st.sidebar:
        st.markdown(
            '<div class="sw-brand"><div class="sw-logo">S</div>'
            '<div><b>Stockwise</b><small>INVENTORY INTELLIGENCE</small></div></div>',
            unsafe_allow_html=True)
        page = st.radio("Workspace", allowed, key="nav", label_visibility="collapsed")
        st.divider()
        st.markdown(
            f'<div class="sw-me"><div class="sw-av">{name[:2].upper()}</div>'
            f'<div><b>{name}</b><span>{user["role"]} access</span></div></div>',
            unsafe_allow_html=True)
        if st.button("Sign out", key="signout"):
            logout()
    return page