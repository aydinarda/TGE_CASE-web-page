# -*- coding: utf-8 -*-
"""
Streamlit Dashboard – Sensitivity and Factory Insights
Author: Arda Aydın (optimized with caching + discrete sliders)
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

# ✅ Use only discrete existing options for CO₂ cost and penalty cost
co2_cost_options = sorted(df["CO2_CostAtMfg"].unique().tolist())
penalty_options = sorted(df["Unit_penaltycost"].unique().tolist())

co2_cost = st.sidebar.select_slider(
    "CO₂ Manufacturing Cost (€ per ton)",
    options=co2_cost_options,
    value=co2_cost_options[len(co2_cost_options)//2]
)

penalty_cost = st.sidebar.select_slider(
    "Penalty Cost (€/unit)",
    options=penalty_options,
    value=penalty_options[len(penalty_options)//2]
)

# ----------------------------------------------------
# FILTER SUBSET AND FIND CLOSEST SCENARIO
# ----------------------------------------------------
subset = data_by_weight[weight_selected]

# Exact match on CO₂ manufacturing cost and penalty cost
pool = subset[
    (subset["CO2_CostAtMfg"] == co2_cost) &
    (subset["Unit_penaltycost"] == penalty_cost)
]

if pool.empty:
    st.warning("⚠️ No exact matches found for this combination — showing nearest instead.")
    pool = subset.copy()

closest = pool.iloc[(pool["CO2_percentage"] - co2_pct).abs().argmin()]

# ----------------------------------------------------
# KPI VIEW
# ----------------------------------------------------
st.subheader("📊 Closest Scenario Details")
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

# Let user choose which cost metric to plot
cost_metric_map = {
    "Objective Value (€)": "Objective_value",
    "Inventory Cost (€)": ["Inventory_L1", "Inventory_L2", "Inventory_L3"],
    "Transport Cost (€)": ["Transport_L1", "Transport_L2", "Transport_L3"],
}

selected_metric_label = st.selectbox(
    "Select Cost Metric to Plot:",
    list(cost_metric_map.keys()),
    index=0,
    help="Choose which cost metric to show on the Y-axis."
)

# Compute total columns if needed
filtered = pool.copy()
if isinstance(cost_metric_map[selected_metric_label], list):
    filtered["Selected_Cost"] = filtered[cost_metric_map[selected_metric_label]].sum(axis=1)
    y_label = selected_metric_label
else:
    filtered["Selected_Cost"] = filtered[cost_metric_map[selected_metric_label]]
    y_label = selected_metric_label

if not filtered.empty:
    fig_sens = px.scatter(
        filtered,
        x="CO2_Total",
        y="Selected_Cost",
        color="CO2_percentage",
        size="Unit_penaltycost",
        hover_data=["CO2_CostAtMfg", "Product_weight", "Unit_penaltycost", "CO2_percentage"],
        title=f"{selected_metric_label} vs Total CO₂ (Weight={weight_selected} kg, Penalty={penalty_cost}, MfgCO₂={co2_cost})",
        labels={"CO2_Total": "Total CO₂ Emissions (tons)", "Selected_Cost": y_label},
        color_continuous_scale="Viridis",
        template="plotly_white"
    )

    # Highlight current scenario
    if isinstance(cost_metric_map[selected_metric_label], list):
        closest_y = closest[cost_metric_map[selected_metric_label]].sum()
    else:
        closest_y = closest[cost_metric_map[selected_metric_label]]

    fig_sens.add_scatter(
        x=[closest["CO2_Total"]],
        y=[closest_y],
        mode="markers+text",
        marker=dict(size=16, color="red"),
        text=["Current Selection"],
        textposition="top center",
        name="Selected Scenario"
    )

    st.plotly_chart(fig_sens, use_container_width=True)
else:
    st.warning("No scenarios found for this exact combination to show sensitivity.")
    
    
# ----------------------------------------------------
# EMISSION DISTRIBUTION BAR CHART
# ----------------------------------------------------
st.markdown("## 🌿 Emission Distribution (Tons)")

# Extract emission components from the selected scenario
emission_fields = [
    "CO2_Prod_tons",
    "CO2_LastMile_tons",
    "CO2_Road_tons",
    "CO2_Sea_tons",
    "CO2_Air_tons"
]

# Filter to columns that exist in df
existing_emission_fields = [f for f in emission_fields if f in closest.index]

if existing_emission_fields:
    emission_data = pd.DataFrame({
        "Source": [
            name.replace("CO2_", "").replace("_tons", "").replace("_", " ").title()
            for name in existing_emission_fields
        ],
        "Emission (tons)": [closest[f] for f in existing_emission_fields]
    }).sort_values("Emission (tons)", ascending=True)

    fig_emission = px.bar(
        emission_data,
        x="Emission (tons)",
        y="Source",
        orientation="h",
        text="Emission (tons)",
        color="Emission (tons)",
        color_continuous_scale="Greens",
        title="Emission Distribution (Tons)",
        template="plotly_white",
    )

    fig_emission.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    fig_emission.update_layout(
        xaxis_title="Emission (tons)",
        yaxis_title="",
        coloraxis_showscale=False,
        height=400,
    )

    st.plotly_chart(fig_emission, use_container_width=True)
else:
    st.info("No emission breakdown columns found in this dataset.")
    
# ----------------------------------------------------
# WORLD MAP VISUALIZATION
# ----------------------------------------------------
st.markdown("## 🌍 Global Supply Chain Map")

# Example approximate coordinates (you can adjust as you like)
plants = pd.DataFrame({
    "name": ["Plant 1", "Plant 2"],
    "lat": [31.23, 22.32],   # China, Vietnam region
    "lon": [121.47, 114.17],
    "type": "Plant"
})

crossdocks = pd.DataFrame({
    "name": ["Crossdock 1", "Crossdock 2", "Crossdock 3"],
    "lat": [50.11, 48.86, 41.90],  # Germany, France, Italy
    "lon": [8.68, 2.35, 12.48],
    "type": "Crossdock"
})

dcs = pd.DataFrame({
    "name": ["DC 1", "DC 2", "DC 3", "DC 4"],
    "lat": [52.52, 48.14, 46.95, 47.50],  # Central Europe
    "lon": [13.40, 11.58, 7.44, 19.04],
    "type": "Distribution Center"
})

retailers = pd.DataFrame({
    "name": ["Retail 1", "Retail 2", "Retail 3", "Retail 4", "Retail 5"],
    "lat": [55.67, 53.35, 51.50, 45.76, 43.30],  # Scandinavia, UK, France
    "lon": [12.57, -6.26, -0.12, 4.83, 5.37],
    "type": "Retailer"
})

# 🆕 Show new facilities only if they are active in the current scenario
if "f2_2_bin" in closest.index and closest["f2_2_bin"] == 1:
    new_facilities = pd.DataFrame({
        "name": ["New Facility 1", "New Facility 2"],
        "lat": [49.61, 44.83],
        "lon": [6.13, 20.42],
        "type": "New Facility"
    })
else:
    new_facilities = pd.DataFrame(columns=["name", "lat", "lon", "type"])

# Combine all locations
locations = pd.concat([plants, crossdocks, dcs, retailers, new_facilities])

# Define colors and icons for each type
symbol_map = {
    "Plant": "factory",
    "Crossdock": "triangle-up",
    "Distribution Center": "warehouse",
    "Retailer": "circle",
    "New Facility": "star"
}

color_map = {
    "Plant": "purple",
    "Crossdock": "blue",
    "Distribution Center": "black",
    "Retailer": "red",
    "New Facility": "cyan"
}

# Plot world map
fig_map = px.scatter_geo(
    locations,
    lat="lat",
    lon="lon",
    color="type",
    hover_name="name",
    projection="natural earth",
    title="Global Network Overview",
    color_discrete_map=color_map,
)

fig_map.update_traces(marker=dict(size=10, opacity=0.8, symbol="circle"))
fig_map.update_layout(
    height=550,
    margin=dict(l=0, r=0, t=40, b=0),
    geo=dict(showland=True, landcolor="rgb(240,240,240)")
)

st.plotly_chart(fig_map, use_container_width=True)

    

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
