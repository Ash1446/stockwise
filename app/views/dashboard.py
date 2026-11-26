"""Dashboard: the teammate's HTML dashboard, filled with real data."""
import streamlit as st
import streamlit.components.v1 as components

from app import htmlpage


def render():
    role = (st.session_state.get("user") or {}).get("role", "Cashier")
    try:
        page = htmlpage.build("dashboard", role)
    except Exception as e:
        st.error(f"Could not build the dashboard page: {e}")
        return
    components.html(page, height=1400, scrolling=True)