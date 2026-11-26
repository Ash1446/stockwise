"""Stockwise app entry point. Run from the project root:
    C:\\st_env\\Scripts\\python.exe -m streamlit run app\\main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

st.set_page_config(page_title="Stockwise - Predictive Inventory Intelligence", layout="wide")

from app import shell, ui
from app.views import dashboard, forecast, inventory, shrinkage, shop, stock_counts, write_offs, end_of_day, sales_analysis
from stockwise import auth

ui.apply_style()
shell.inject_css()

if not st.session_state.get("user"):
    shell.login_screen()
    st.stop()

if not ui.db_ready():
    st.error("The database was not found or is empty. Run scripts\\build_sample_db.py and "
             "scripts\\load_demo_counts.py first.")
    st.stop()


def coming(title, note):
    def _render():
        st.title(title)
        st.info(note)
    return _render


PAGES = {
    "Dashboard": dashboard.render,
    "Shop": shop.render,
    "Inventory": inventory.render,
    "Stock counts": stock_counts.render,
    "Demand forecast": forecast.render,
    "Shrinkage detection": shrinkage.render,
    "Write-offs": write_offs.render,
    "End of day": end_of_day.render,
    "Sales analysis": sales_analysis.render,
}

role = st.session_state.user["role"]
allowed = [p for p in PAGES if auth.can_access(role, p)]
page = shell.sidebar(allowed)
auth.require_page(page)

if page != "Inventory":
    st.session_state.pop("inv_item", None)

PAGES[page]()