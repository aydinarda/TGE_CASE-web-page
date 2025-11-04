import streamlit as st
from sc1_app import run_sc1
from sc2_app import run_sc2

# ----------------------------------------------------
# PAGE CONFIGURATION (set only once)
# ----------------------------------------------------
st.set_page_config(
    page_title="Supply Chain Optimization Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------
# SIDEBAR NAVIGATION
# ----------------------------------------------------
st.sidebar.title("🏗️ Model Selection")

option = st.sidebar.radio(
    "Do you want to allow new factory openings?",
    (
        "No (SC1F – Existing Facilities Only)",
        "Yes (SC2F – Allow New Factories)"
    ),
    index=0
)

# Remember user selection (optional – preserves choice when re-running)
st.session_state["selected_model"] = (
    "SC1" if option.startswith("No") else "SC2"
)

# ----------------------------------------------------
# ROUTE TO THE SELECTED DASHBOARD
# ----------------------------------------------------
if st.session_state["selected_model"] == "SC1":
    run_sc1()
else:
    run_sc2()
