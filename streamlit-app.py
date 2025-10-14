# -*- coding: utf-8 -*-
"""
Streamlit Dashboard – Sensitivity and Factory Insights
Author: Arda Aydın (optimized with caching + penalty cost slider)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO

# ----------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------
st.set_page_config(
    page_title="Optimization Sensitivity Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏭 CO₂ Sensitivity & Factory Opening Dashboard")

# ----------------------------------------------------
# CACHED DATA LOADERS
# ----------------------------------------------------
@st.cache_data(show_spinner="📡 Fetching live data from GitHub...")
def load_data_from_github(url: str):
    """Download and read the Excel file from GitHub (cached)."""
    response = requests.get(url)
    response.raise_for_status()
    return pd.read_excel(BytesIO(response.content), sheet_name="Summary")

@st.cache_data
def preprocess(df: pd.DataFrame):
    """Pre-group the dataframe by Product_weight for instant filtering."""
    return {w: d for w, d in df.groupby("Product_weight")}

@st.cache_data
def compute_pivot(df: pd.DataFrame):
    """Compute factory openings pivot once for heatmap."""
    return df.groupby(["CO2_percentage", "Product_weight"])["f2_2"].mean().unstack()

# ----------------------------------------------------
# LOAD DATA (from cache)
# ----------------------------------------------------
GITHUB_XLSX_URL = "https://raw.githubusercontent.com/aydınarda/TGE_CASE-web-page/main/simulation_results_full.xlsx"

try:
    df = load_data_from_github(GITHUB_XLSX_URL)
    data_by_weight = preprocess(df)
    st.success("✅ Data successfully loaded and cached from GitHub!")
except Exception as e:
    st.error(f"❌ Failed to load data: {e}")
    st.stop()

# ----------------------------------------------------
# SIDEBAR FILTERS
# ----------------------------------------------------
st.sidebar.header("🎛️ Filter Parameters")

weight_selected = st.sidebar.selectbox(
    "Select Product Weight (kg)",
    sorted(df["Product_weight"].unique())
)

co2_pct = st.sidebar.slider(
    "CO₂ Percentage",
    float(df["CO2_percentage"].min()),
    float(df["CO2_percentage"].max()),
    float(df["CO2_percentage"].mean()),
    step=0.01
)

co2_cost = st.sidebar.slider(
    "CO₂ Manufacturing Cost (€ per ton)",
    float(df["CO2_CostAtMfg"].min()),
    float(df["CO2_CostAtMfg"].max()),
    float(df["CO2_CostAtMfg"].mean()),
    step=0.5
)

# ✅ NEW SLIDER FOR PENALTY COST
if "Unit_penaltycost" in df.columns:
    penalty_cost = st.sidebar.slider(
        "Penalty Cost (€/unit)",
        float(df["Unit_penaltycost"].min()),
        float(df["Unit_penaltycost"].max()),
        float(df["Unit_penaltycost"].mean()),
        step=0.1
    )
else:
    penalty_cost = None

# ✅ Use preprocessed group to avoid repeated filtering
subset = data_by_weight[weight_selected]

# ----------------------------------------------------
# KPI VIEW – Closest Scenario
# ----------------------------------------------------
st.subheader("📊 Closest Scenario Details")

# Match closest scenario using all three dimensions
if penalty_cost is not None:
    subset["penalty_diff"] = (subset["Unit_penaltycost"] - penalty_cost).abs()
else:
    subset["penalty_diff"] = 0

closest_idx = (
    (subset["CO2_percentage"] - co2_pct).abs()
    + (subset["CO2_CostAtMfg"] - co2_cost).abs()
    + subset["penalty_diff"]
).idxmin()

closest = subset.loc[closest_idx]

st.write(closest.to_frame().T)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Objective (€)", f"{closest['Objective_value']:.2f}")
col2.metric("Total CO₂", f"{closest['CO2_Total']:.2f}")
col3.metric("Inventory Total (€)", f"{closest[['Inventory_L1','Inventory_L2','Inventory_L3']].sum():.2f}")
col4.metric("Transport Total (€)", f"{closest[['Transport_L1','Transport_L2','Transport_L3']].sum():.2f}")

# ----------------------------------------------------
# COST vs EMISSION SENSITIVITY PLOT
# ----------------------------------------------------
st.markdown("## 📈 Cost vs CO₂ Emission Sensitivity")

# Filter for current penalty and manufacturing cost neighborhood (for stability)
filtered = subset.copy()
if penalty_cost is not None:
    # Keep penalty cost dimension narrow around selected value
    tol_penalty = 0.2
    filtered = filtered[
        (filtered["Unit_penaltycost"] >= penalty_cost - tol_penalty)
        & (filtered["Unit_penaltycost"] <= penalty_cost + tol_penalty)
    ]

tol_cost = 1.0
filtered = filtered[
    (filtered["CO2_CostAtMfg"] >= co2_cost - tol_cost)
    & (filtered["CO2_CostAtMfg"] <= co2_cost + tol_cost)
]

if not filtered.empty:
    fig_sens = px.scatter(
        filtered,
        x="CO2_Total",
        y="Objective_value",
        color="CO2_percentage",
        size="Unit_penaltycost",
        hover_data=["CO2_CostAtMfg", "Product_weight", "Unit_penaltycost"],
        title=f"Objective Cost vs Total CO₂ (Weight={weight_selected} kg)",
        labels={
            "CO2_Total": "Total CO₂ Emissions (tons)",
            "Objective_value": "Objective Cost (€)"
        },
        color_continuous_scale="Viridis",
        template="plotly_white"
    )

    # Highlight the currently selected scenario
    fig_sens.add_scatter(
        x=[closest["CO2_Total"]],
        y=[closest["Objective_value"]],
        mode="markers+text",
        marker=dict(size=16, color="red"),
        text=["Current Selection"],
        textposition="top center",
        name="Selected Scenario"
    )

    st.plotly_chart(fig_sens, use_container_width=True)
else:
    st.warning("No nearby scenarios found for this combination to show sensitivity.")


# ----------------------------------------------------
# FACTORY OPENINGS (f2_2)
# ----------------------------------------------------
if "f2_2" in df.columns:
    st.markdown("## 🏭 Factory Openings (f2_2)")
    pivot_factories = compute_pivot(df)

    fig_fact = px.imshow(
        pivot_factories,
        aspect="auto",
        color_continuous_scale="Blues",
        title="Factory Opening Heatmap (1=open)",
        labels={"x": "CO₂ %", "y": "Product Weight"}
    )
    st.plotly_chart(fig_fact, use_container_width=True)
    st.dataframe(pivot_factories.reset_index(), use_container_width=True)

# ----------------------------------------------------
# RAW DATA VIEW
# ----------------------------------------------------
with st.expander("📄 Show Full Summary Data"):
    st.dataframe(df.head(500), use_container_width=True)
