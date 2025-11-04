# -*- coding: utf-8 -*-
"""
Created on Tue Nov  4 08:50:39 2025

@author: LENOVO
"""

# main_app.py
import streamlit as st
from sc1_app import run_sc1
from sc2_app import run_sc2


st.set_page_config(page_title="Supply Chain Optimization Dashboard", layout="wide")

# Sidebar selector
st.sidebar.title("🏗️ Model Selection")
option = st.sidebar.radio(
    "Do you want to allow new factory openings?",
    ("No (SC1F – Existing Facilities Only)", "Yes (SC2F – Allow New Factories)")
)

# Route to the chosen app
if option.startswith("No"):
    run_sc1()
else:
    run_sc2()
