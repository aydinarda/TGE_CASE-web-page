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
@st.cache_data(show_spinner="📡 Loading Excel from local or GitHub...")
def load_data_from_excel(path: str, sheet: str):
    """Load selected demand level sheet."""
    return pd.read_excel(path, sheet_name=sheet)


# ----------------------------------------------------
# DEMAND LEVEL SELECTOR
# ----------------------------------------------------
st.sidebar.header("📦 Select Demand Level")

# 👇 Available demand sheets in your new file
demand_levels = ["100%", "95%", "90%", "85%", "80%", "75%"]
selected_demand = st.sidebar.selectbox(
    "Demand Level",
    demand_levels,
    index=0,
    help="Choose which demand level's scenarios to visualize."
)

# 👇 Path to your new Excel output (update if using a hosted version)
LOCAL_XLSX_PATH = "simulation_results_demand_levelsSC2.xlsx"

try:
    df = load_data_from_excel(LOCAL_XLSX_PATH, sheet=selected_demand)
    st.success(f"✅ Loaded data for {selected_demand} demand level.")
except Exception as e:
    st.error(f"❌ Failed to load data: {e}")
    st.stop()

# ----------------------------------------------------
# PREPROCESSING (same as before)
# ----------------------------------------------------
@st.cache_data
def preprocess(df: pd.DataFrame):
    """Pre-group the dataframe by Product_weight for instant filtering."""
    if "Product_weight" not in df.columns:
        return {"N/A": df}
    return {w: d for w, d in df.groupby("Product_weight")}

@st.cache_data
def compute_pivot(df: pd.DataFrame):
    """Compute factory openings pivot once for heatmap."""
    if "f2_2" not in df.columns:
        return pd.DataFrame()
    return df.groupby(["CO2_percentage", "Product_weight"])["f2_2"].mean().unstack()

data_by_weight = preprocess(df)

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
# SIDEBAR FILTERS (simplified)
# ----------------------------------------------------
st.sidebar.header("🎛️ Filter Parameters")

# Remove Product Weight and Penalty Cost
co2_pct = st.sidebar.slider(
    "CO₂ Reduction",
    float(df["CO2_percentage"].min()),
    float(df["CO2_percentage"].max()),
    float(df["CO2_percentage"].mean()),
    step=0.01
)

co2_cost_options = [0, 20, 40, 60, 80, 100]
co2_cost = st.sidebar.select_slider(
    "CO₂ Price In Europe (€ per ton)",
    options=co2_cost_options,
    value=60
)


# ----------------------------------------------------
# FILTER SUBSET AND FIND CLOSEST SCENARIO
# ----------------------------------------------------
pool = df[df["CO2_CostAtMfg"] == co2_cost]

if pool.empty:
    st.warning("⚠️ No scenarios match this CO₂ price — showing all instead.")
    pool = df.copy()

closest = pool.iloc[(pool["CO2_percentage"] - co2_pct).abs().argmin()]

# ----------------------------------------------------
# CHECK FOR FEASIBILITY (NaN COST)
# ----------------------------------------------------
if pd.isna(closest["Objective_value"]):
    st.error(
        "💥 *Kaboom!* The optimizer just threw its hands in the air — "
        "this setup isn’t **feasible**! 😅\n\n"
        "Try loosening your CO₂ reduction target or lowering the CO₂ price in Europe — "
        "sometimes the planet needs a little compromise. 🌍💸"
    )
    st.stop()


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
        hover_data=["CO2_CostAtMfg", "Product_weight", "CO2_percentage"],
        title=f"{selected_metric_label} vs Total CO₂ (MfgCO₂={co2_cost})",
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
# 💰🌿 COST & EMISSION DISTRIBUTION SECTION (FINAL)
# ----------------------------------------------------
st.markdown("## 💰 Cost and 🌿 Emission Distribution")

col1, col2 = st.columns(2)

# --- 💰 Cost Distribution (calculated as before) ---
with col1:
    st.subheader("Cost Distribution")

    # --- Dynamically compute costs from model components ---
    transport_cost = (
        closest.get("Transport_L1", 0)
        + closest.get("Transport_L2", 0)
        + closest.get("Transport_L2_new", 0)
        + closest.get("Transport_L3", 0)
    )

    sourcing_handling_cost = (
        closest.get("Sourcing_L1", 0)
        + closest.get("Handling_L2_total", 0)
        + closest.get("Handling_L3", 0)
    )

    co2_cost_production = closest.get("CO2_Manufacturing_State1", 0)

    inventory_cost = (
        closest.get("Inventory_L1", 0)
        + closest.get("Inventory_L2", 0)
        + closest.get("Inventory_L2_new", 0)
        + closest.get("Inventory_L3", 0)
    )

    # Prepare for plot
    cost_parts = {
        "Transportation Cost": transport_cost,
        "Sourcing/Handling Cost": sourcing_handling_cost,
        "CO₂ Cost in Production": co2_cost_production,
        "Inventory Cost": inventory_cost
    }

    df_cost_dist = pd.DataFrame({
        "Category": list(cost_parts.keys()),
        "Value": list(cost_parts.values())
    })

    import plotly.express as px
    fig_cost = px.bar(
        df_cost_dist,
        x="Category",
        y="Value",
        text="Value",
        color="Category",
        color_discrete_sequence=["#A7C7E7", "#B0B0B0", "#F8C471", "#5D6D7E"],
        title="Cost Distribution"
    )
    fig_cost.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    fig_cost.update_layout(
        template="plotly_white",
        showlegend=False,
        xaxis_tickangle=-35,
        yaxis_title="€",
        height=400
    )
    st.plotly_chart(fig_cost, use_container_width=True)

# --- 🌿 Emission Distribution (from new recorded columns) ---
with col2:
    st.subheader("Emission Distribution")

    emission_cols = ["E(Air)", "E(Sea)", "E(Road)", "E(Last-mile)", "E(Production)"]
    available_cols = [c for c in emission_cols if c in df.columns]

    if not available_cols:
        st.info("No emission data available for this scenario.")
    else:
        emission_data = {
            c.replace("E(", "").replace(")", ""): float(closest[c])
            for c in available_cols
        }

        df_emission = pd.DataFrame({
            "Source": list(emission_data.keys()),
            "Emission (tons)": list(emission_data.values())
        })

        fig_emission = px.bar(
            df_emission,
            x="Source",
            y="Emission (tons)",
            text="Emission (tons)",
            color="Source",
            color_discrete_sequence=["#0077C8", "#00A6A6", "#999999", "#FFD24C", "#6B7A8F"],
            title="Emission Distribution"
        )
        fig_emission.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig_emission.update_layout(
            template="plotly_white",
            showlegend=False,
            xaxis_tickangle=-35,
            yaxis_title="Tons of CO₂",
            height=400
        )
        st.plotly_chart(fig_emission, use_container_width=True)



# ----------------------------------------------------
# RAW DATA VIEW
# ----------------------------------------------------
with st.expander("📄 Show Full Summary Data"):
    st.dataframe(df.head(500), use_container_width=True)
