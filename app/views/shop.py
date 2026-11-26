"""Shop: Billing for the cashier, read-only Bills for the manager, and the HTML product catalogue for both."""
import streamlit as st
import streamlit.components.v1 as components

from app import htmlpage
from app.views import billing as billing_view
from app.views import bills as bills_view


def render():
    role = (st.session_state.get("user") or {}).get("role", "Cashier")
    first = "Billing" if role == "Cashier" else "Bills"
    tab1, tab2 = st.tabs([first, "Catalogue"])
    with tab1:
        if role == "Cashier":
            billing_view.render()
        else:
            bills_view.render()
    with tab2:
        try:
            page = htmlpage.build("shop", role)
        except Exception as e:
            st.error(f"Could not build the catalogue page: {e}")
        else:
            components.html(page, height=900, scrolling=True)
            st.caption("The restock queue is a visual demo for now: it does not write purchase orders to the database yet.")