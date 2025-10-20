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
    "CO₂ Reduction",
    float(df["CO2_percentage"].min()),
    float(df["CO2_percentage"].max()),
    float(df["CO2_percentage"].mean()),
    step=0.01
)

# ✅ Define discrete values consistent with SC2F simulation
co2_cost_options = [0, 20, 40, 60, 80, 100]   # from SC2F: CO_2_CostsAtEU
penalty_options = [1.7]                       # single fixed penalty value

# CO₂ cost (select one from 0–100)
co2_cost = st.sidebar.select_slider(
    "CO₂ Price In Europe (€ per ton)",
    options=co2_cost_options,
    value=60  # default mid-range value
)

# Penalty cost (only one)
penalty_cost = st.sidebar.selectbox(
    "Penalty Cost (€/unit)",
    options=penalty_options,
    index=0,
    help="Fixed penalty cost from SC2F configuration"
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
col1.metric("Total Cost (€)", f"{closest['Objective_value']:.2f}")
col2.metric("Total CO₂", f"{closest['CO2_Total']:.2f}")
col3.metric("Inventory Total (€)", f"{closest[['Inventory_L1','Inventory_L2','Inventory_L3']].sum():.2f}")
col4.metric("Transport Total (€)", f"{closest[['Transport_L1','Transport_L2','Transport_L3']].sum():.2f}")

# ----------------------------------------------------
# COST vs EMISSION SENSITIVITY PLOT
# ----------------------------------------------------
st.markdown("## 📈 Cost vs CO₂ Emission Sensitivity")

# Let user choose which cost metric to plot
cost_metric_map = {
    "Total Cost (€)": "Objective_value",
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
# 🌿 EMISSION DISTRIBUTION BAR CHART (Updated for new SC2F outputs)
# ----------------------------------------------------
st.markdown("## 🌿 Emission Distribution (Tons)")

# Correct emission column names from SC2F.py outputs
emission_fields = ["E(Air)", "E(Sea)", "E(Road)", "E(Last-mile)", "E(Production)"]

# Filter to the columns that actually exist in the loaded dataset
existing_emission_fields = [col for col in emission_fields if col in df.columns]

if existing_emission_fields:
    # Build DataFrame for plotting from the currently selected scenario
    emission_data = pd.DataFrame({
        "Source": [name.replace("E(", "").replace(")", "") for name in existing_emission_fields],
        "Emission (tons)": [closest[name] for name in existing_emission_fields]
    }).sort_values("Emission (tons)", ascending=True)

    import plotly.express as px

    fig_emission = px.bar(
        emission_data,
        x="Emission (tons)",
        y="Source",
        orientation="h",
        text="Emission (tons)",
        color="Source",
        color_discrete_sequence=["#0077C8", "#00A6A6", "#999999", "#FFD24C", "#6B7A8F"],
        title="Emission Distribution by Source",
        template="plotly_white"
    )

    fig_emission.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig_emission.update_layout(
        xaxis_title="Emission (tons)",
        yaxis_title="",
        showlegend=False,
        height=400,
        margin=dict(t=60, l=30, r=30, b=30)
    )

    st.plotly_chart(fig_emission, use_container_width=True)

else:
    st.info("ℹ️ Emission data not found in this dataset.")
    
# ----------------------------------------------------
# 🌍 GLOBAL SUPPLY CHAIN MAP
# ----------------------------------------------------
st.markdown("## 🌍 Global Supply Chain Network")

# --- Plants (f1, China region) ---
plants = pd.DataFrame({
    "Type": ["Plant", "Plant"],
    "Lat": [31.23, 22.32],        # Shanghai & Southern China
    "Lon": [121.47, 114.17]
})

# --- Cross-docks (f2) ---
crossdocks = pd.DataFrame({
    "Type": ["Cross-dock"] * 3,
    "Lat": [48.85, 50.11, 37.98],   # France, Germany, Greece
    "Lon": [2.35, 8.68, 23.73]
})

# --- Distribution Centres (DCs) ---
dcs = pd.DataFrame({
    "Type": ["Distribution Centre"] * 4,
    "Lat": [47.50, 48.14, 46.95, 45.46],   # Central Europe
    "Lon": [19.04, 11.58, 7.44, 9.19]
})

# --- Retailer Hubs (f3) ---
retailers = pd.DataFrame({
    "Type": ["Retailer Hub"] * 7,
    "Lat": [55.67, 53.35, 51.50, 49.82, 45.76, 43.30, 40.42],  # North to South
    "Lon": [12.57, -6.26, -0.12, 19.08, 4.83, 5.37, -3.70]
})

# --- New Production Facilities (f2_2) ---
f2_2_cols = [c for c in closest.index if c.startswith("f2_2_bin")]

# Define coordinates (one per possible facility)
facility_coords = {
    "f2_2_bin[HUDTG]": (49.61, 6.13),
    "f2_2_bin[CZMCT]":  (44.83, 20.42),
    "f2_2_bin[IEILG]": (47.09, 16.37),
    "f2_2_bin[FIMPF]": (50.45, 14.50),
    "f2_2_bin[PLZCA]": (42.70, 12.65),
}

active_facilities = []
for col in f2_2_cols:
    try:
        val = float(closest[col])
        if val > 0.5 and col in facility_coords:
            lat, lon = facility_coords[col]
            active_facilities.append((col, lat, lon))
    except Exception:
        continue

if active_facilities:
    new_facilities = pd.DataFrame({
        "Type": "New Production Facility",
        "Lat": [lat for _, lat, _ in active_facilities],
        "Lon": [lon for _, _, lon in active_facilities],
        "Name": [col for col, _, _ in active_facilities]
    })
else:
    new_facilities = pd.DataFrame(columns=["Type", "Lat", "Lon", "Name"])
    
# --- Combine all ---
locations = pd.concat([plants, crossdocks, dcs, retailers, new_facilities])

# --- Define colors & sizes ---
color_map = {
    "Plant": "purple",
    "Cross-dock": "dodgerblue",
    "Distribution Centre": "black",
    "Retailer Hub": "red",
    "New Production Facility": "deepskyblue"
}

size_map = {
    "Plant": 15,
    "Cross-dock": 14,
    "Distribution Centre": 16,
    "Retailer Hub": 20,
    "New Production Facility": 14
}

# --- Create Map ---
fig_map = px.scatter_geo(
    locations,
    lat="Lat",
    lon="Lon",
    color="Type",
    color_discrete_map=color_map,
    hover_name="Type",
    projection="natural earth",
    scope="world",
    title="Global Supply Chain Structure",
    template="plotly_white"
)

# Customize markers
for trace in fig_map.data:
    trace.marker.update(size=size_map[trace.name], opacity=0.9, line=dict(width=0.5, color='white'))

fig_map.update_geos(
    showcountries=True,
    countrycolor="lightgray",
    showland=True,
    landcolor="rgb(245,245,245)",
    fitbounds="locations"
)

fig_map.update_layout(
    height=550,
    margin=dict(l=0, r=0, t=40, b=0)
)

st.plotly_chart(fig_map, use_container_width=True)

# --- Legend ---
st.markdown("""
**Legend:**
- 🏗️ **Cross-dock**  
- 🏬 **Distribution Centre**  
- 🔴 **Retailer Hub**  
- ⚙️ **New Production Facility**  
- 🏭 **Plant** 
""")


# ----------------------------------------------------
# 🚢✈️🚛 FLOW SUMMARY BY MODE PER LAYER (f1, f2, f2_2, f3)
# ----------------------------------------------------
st.markdown("## 🚚 Transport Flows by Mode")

import re

def sum_flows_by_mode(prefix):
    """Sum up air/sea/road units for a given flow prefix like 'f1', 'f2', 'f2_2', or 'f3'."""
    flow_cols = [c for c in df.columns if c.startswith(prefix + "[")]
    totals = {"air": 0.0, "sea": 0.0, "road": 0.0}

    for col in flow_cols:
        # Extract mode from inside brackets, e.g. f2_2[CZMC,DEBER,road]
        match = re.search(r",\s*([a-zA-Z]+)\]$", col)
        if match:
            mode = match.group(1).lower()
            if mode in totals:
                try:
                    totals[mode] += float(closest[col])
                except:
                    pass
    return totals


def display_layer_summary(title, prefix, include_road=True):
    totals = sum_flows_by_mode(prefix)
    st.markdown(f"### {title}")
    cols = st.columns(3 if include_road else 2)
    cols[0].metric("🚢 Sea", f"{totals['sea']:,.0f} units")
    cols[1].metric("✈️ Air", f"{totals['air']:,.0f} units")
    if include_road:
        cols[2].metric("🚛 Road", f"{totals['road']:,.0f} units")

    if sum(totals.values()) == 0:
        st.info("No transport activity recorded for this layer.")
    st.markdown("---")


# Layer summaries
display_layer_summary("Layer 1: Plants → Cross-docks (f1)", "f1", include_road=False)
display_layer_summary("Layer 2a: Cross-docks → DCs (f2)", "f2", include_road=True)
display_layer_summary("Layer 2b: New Facilities → DCs (f2_2)", "f2_2", include_road=True)
display_layer_summary("Layer 3: DCs → Retailers (f3)", "f3", include_road=True)

# ----------------------------------------------------
# 💰 COST & 🌿 EMISSION DISTRIBUTION VISUALS (Corrected)
# ----------------------------------------------------
st.markdown("## 💰 Cost and 🌿 Emission Distribution")

import plotly.graph_objects as go

# ---------- COST DISTRIBUTION ----------
cost_labels = [
    "Transportation Cost",
    "Sourcing/Handling Cost",
    "CO₂ Cost in Production",
    "Inventory Cost"
]

# Compute from closest scenario row
transport_cost = (
    closest.get("Transport_L1", 0) +
    closest.get("Transport_L2", 0) +
    closest.get("Transport_L3", 0)
)

# 🧩 Corrected sourcing/handling combination
sourcing_handling_cost = (
    closest.get("Sourcing_L1", 0) +
    closest.get("Handling_L2_total", 0) +
    closest.get("Handling_L3", 0)
)

# 🧩 Corrected CO₂ cost in manufacturing
co2_prod_cost = (
    closest.get("CO2_Cost_L2_2", 0) +
    closest.get("CO2_Manufacturing_State1", 0)
)

# Inventory cost
inventory_cost = (
    closest.get("Inventory_L1", 0) +
    closest.get("Inventory_L2", 0) +
    closest.get("Inventory_L3", 0)
)

cost_values = [
    transport_cost,
    sourcing_handling_cost,
    co2_prod_cost,
    inventory_cost
]

cost_colors = ["#AECBFA", "#D3D3D3", "#FFD24C", "#6B7A8F"]

fig_cost = go.Figure()
fig_cost.add_trace(go.Bar(
    x=cost_labels,
    y=cost_values,
    text=[f"{v:,.0f}" for v in cost_values],
    textposition="outside",
    marker_color=cost_colors
))

fig_cost.update_layout(
    title="Cost Distribution",
    title_font=dict(size=18, family="Arial Black"),
    xaxis=dict(title="", tickfont=dict(size=13, family="Arial Black")),
    yaxis=dict(title="", showgrid=False),
    template="plotly_white",
    height=400,
    margin=dict(t=60, l=30, r=30, b=30)
)

# ----------------------------------------------------
# 🌿 EMISSION DISTRIBUTION SECTION (Bottom of Page)
# ----------------------------------------------------
st.markdown("## 🌿 Emission Distribution")

# Emission columns as recorded in SC2F simulation
emission_cols = ["E(Air)", "E(Sea)", "E(Road)", "E(Last-mile)", "E(Production)"]

# Check which emission columns exist in the dataset
available_emission_cols = [c for c in emission_cols if c in df.columns]

if not available_emission_cols:
    st.info("No emission data found for this scenario.")
else:
    # Extract emission data for the currently selected scenario
    emission_data = {
        c.replace("E(", "").replace(")", ""): float(closest[c])
        for c in available_emission_cols
    }

    df_emission = pd.DataFrame({
        "Source": list(emission_data.keys()),
        "Emission (tons)": list(emission_data.values())
    })

    import plotly.express as px
    fig_emission = px.bar(
        df_emission,
        x="Source",
        y="Emission (tons)",
        text="Emission (tons)",
        color="Source",
        color_discrete_sequence=["#0077C8", "#00A6A6", "#999999", "#FFD24C", "#6B7A8F"],
        title="Emission Distribution by Source",
        template="plotly_white"
    )

    fig_emission.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig_emission.update_layout(
        showlegend=False,
        xaxis_tickangle=-35,
        yaxis_title="Tons of CO₂",
        height=400,
        margin=dict(l=30, r=30, t=60, b=60)
    )

    st.plotly_chart(fig_emission, use_container_width=True)


# ---------- SIDE-BY-SIDE DISPLAY ----------
col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(fig_cost, use_container_width=True)
with col2:
    st.plotly_chart(fig_emis, use_container_width=True)




# ----------------------------------------------------
# RAW DATA VIEW
# ----------------------------------------------------
with st.expander("📄 Show Full Summary Data"):
    st.dataframe(df.head(500), use_container_width=True)
