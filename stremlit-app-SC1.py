# -*- coding: utf-8 -*-
"""
Streamlit Dashboard – Simplified Supply Chain Model (SC1F)
Author: Arda Aydın
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO
import re

# ----------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------
st.set_page_config(
    page_title="Simplified CO₂ Supply Chain Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏭 Simplified CO₂ Supply Chain Dashboard (SC1F Model)")

# ----------------------------------------------------
# SAFE CACHED DATA LOADER
# ----------------------------------------------------
@st.cache_data(show_spinner="📡 Fetching data from GitHub...")
def load_excel_from_github(url: str):
    """Load all Excel sheets into a dict of DataFrames (pickle-safe)."""
    response = requests.get(url)
    response.raise_for_status()
    excel_data = pd.read_excel(BytesIO(response.content), sheet_name=None)
    return excel_data  # dictionary of {sheet_name: DataFrame}

# 👉 Replace with your GitHub-hosted file URL when public
GITHUB_XLSX_URL = (
    "https://raw.githubusercontent.com/aydınarda/TGE_CASE-web-page/main/"
    "simulation_results_demand_levels.xlsx"
)

try:
    excel_data = load_excel_from_github(GITHUB_XLSX_URL)
    sheet_names = [s for s in excel_data.keys() if s.startswith("Array_")]
    if not sheet_names:
        st.error("❌ No sheets starting with 'Array_' found.")
        st.stop()
    st.success(f"✅ Loaded {len(sheet_names)} demand-level sheets.")
except Exception as e:
    st.error(f"❌ Failed to load Excel file: {e}")
    st.stop()

# ----------------------------------------------------
# SIDEBAR CONTROLS
# ----------------------------------------------------
st.sidebar.header("🎛️ Model Controls")

# Extract numeric levels automatically (e.g., Array_90% → 90)
levels = sorted(
    [int(re.findall(r"\d+", name)[0]) for name in sheet_names],
    reverse=True
)

# Slider to pick demand level
selected_level = st.sidebar.slider(
    "Select Demand Level (%)",
    min_value=min(levels),
    max_value=max(levels),
    step=5,
    value=max(levels)
)

selected_sheet = f"Array_{selected_level}%"
st.sidebar.write(f"📄 Using sheet: `{selected_sheet}`")

# Load selected sheet
df = excel_data[selected_sheet]

# ----------------------------------------------------
# OPTIONAL FILTERS
# ----------------------------------------------------
if "Product_weight" in df.columns:
    weight_selected = st.sidebar.selectbox(
        "Product Weight (kg)",
        sorted(df["Product_weight"].unique())
    )
    subset = df[df["Product_weight"] == weight_selected]
else:
    subset = df.copy()

if "Unit_penaltycost" in subset.columns:
    penalty_selected = st.sidebar.select_slider(
        "Penalty Cost (€/unit)",
        options=sorted(subset["Unit_penaltycost"].unique()),
        value=subset["Unit_penaltycost"].iloc[0]
    )
    subset = subset[subset["Unit_penaltycost"] == penalty_selected]

# ----------------------------------------------------
# DETECT CO₂ REDUCTION COLUMN AUTOMATICALLY
# ----------------------------------------------------
possible_co2_cols = [
    c for c in subset.columns
    if "co2" in c.lower() and any(x in c.lower() for x in ["%", "reduction", "percent", "perc"])
]

if possible_co2_cols:
    co2_col = possible_co2_cols[0]
else:
    st.error(
        "❌ Could not find any CO₂-related percentage column. "
        "Make sure one of the columns includes terms like 'CO2', 'Reduction', or '%'."
    )
    st.stop()

# Create slider for CO2 Reduction %
co2_pct = st.sidebar.slider(
    f"CO₂ Reduction Target ({co2_col})",
    float(subset[co2_col].min()),
    float(subset[co2_col].max()),
    float(subset[co2_col].mean()),
    step=0.01
)

# ----------------------------------------------------
# FIND CLOSEST SCENARIO
# ----------------------------------------------------
closest = subset.iloc[(subset[co2_col] - co2_pct).abs().argmin()]

# ----------------------------------------------------
# KPI SUMMARY
# ----------------------------------------------------
st.subheader("📊 Closest Scenario Details")
st.write(closest.to_frame().T)

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Total Cost (€)",
    f"{closest['Total Cost'] if 'Total Cost' in closest else closest.get('Objective_value', 0):.2f}"
)
col2.metric(
    "Total CO₂ (tons)",
    f"{closest['Total Emissions'] if 'Total Emissions' in closest else closest.get('CO2_Total', 0):.2f}"
)
col3.metric(
    "Inventory Total (€)",
    f"{closest[['Inventory_L1','Inventory_L2','Inventory_L3']].sum():.2f}"
    if all(c in closest for c in ['Inventory_L1','Inventory_L2','Inventory_L3'])
    else "N/A"
)
col4.metric(
    "Transport Total (€)",
    f"{closest[['Transport_L1','Transport_L2','Transport_L3']].sum():.2f}"
    if all(c in closest for c in ['Transport_L1','Transport_L2','Transport_L3'])
    else "N/A"
)

# ----------------------------------------------------
# COST vs EMISSION PLOT
# ----------------------------------------------------
st.markdown("## 📈 Cost vs CO₂ Emission Sensitivity")

cost_metric_map = {
    "Total Cost (€)": "Objective_value" if "Objective_value" in df.columns else "Total Cost",
    "Inventory Cost (€)": ["Inventory_L1", "Inventory_L2", "Inventory_L3"],
    "Transport Cost (€)": ["Transport_L1", "Transport_L2", "Transport_L3"],
}

selected_metric_label = st.selectbox(
    "Select Cost Metric to Plot:",
    list(cost_metric_map.keys()),
    index=0
)

filtered = subset.copy()
if isinstance(cost_metric_map[selected_metric_label], list):
    cols_to_sum = [c for c in cost_metric_map[selected_metric_label] if c in filtered.columns]
    filtered["Selected_Cost"] = filtered[cols_to_sum].sum(axis=1)
else:
    filtered["Selected_Cost"] = filtered[cost_metric_map[selected_metric_label]]

y_label = selected_metric_label

x_col = "Total Emissions" if "Total Emissions" in filtered.columns else "CO2_Total"

fig = px.scatter(
    filtered,
    x=x_col,
    y="Selected_Cost",
    color=co2_col,
    template="plotly_white",
    color_continuous_scale="Viridis",
    title=f"{selected_metric_label} vs CO₂ Emissions ({selected_sheet})"
)

# Compute the Y value safely (Selected Cost)
if "Selected_Cost" in closest.index:
    closest_y = closest["Selected_Cost"]
else:
    # If column missing, compute from selected metric mapping
    if isinstance(cost_metric_map[selected_metric_label], list):
        cols_to_sum = [c for c in cost_metric_map[selected_metric_label] if c in closest.index]
        closest_y = closest[cols_to_sum].sum()
    else:
        closest_y = closest.get(cost_metric_map[selected_metric_label], 0)

# Add the point on the chart
fig.add_scatter(
    x=[closest[x_col]],
    y=[closest_y],
    mode="markers+text",
    marker=dict(size=14, color="red"),
    text=["Selected Scenario"],
    textposition="top center",
    name="Selected"
)

# ----------------------------------------------------
# 🌍 SUPPLY CHAIN MAP
# ----------------------------------------------------
st.markdown("## 🌍 Global Supply Chain Network")

plants = pd.DataFrame({
    "Type": ["Plant", "Plant"],
    "Lat": [31.23, 22.32],
    "Lon": [121.47, 114.17]
})

crossdocks = pd.DataFrame({
    "Type": ["Cross-dock"] * 3,
    "Lat": [48.85, 50.11, 37.98],
    "Lon": [2.35, 8.68, 23.73]
})

dcs = pd.DataFrame({
    "Type": ["Distribution Centre"] * 4,
    "Lat": [47.50, 48.14, 46.95, 45.46],
    "Lon": [19.04, 11.58, 7.44, 9.19]
})

retailers = pd.DataFrame({
    "Type": ["Retailer Hub"] * 7,
    "Lat": [55.67, 53.35, 51.50, 49.82, 45.76, 43.30, 40.42],
    "Lon": [12.57, -6.26, -0.12, 19.08, 4.83, 5.37, -3.70]
})

locations = pd.concat([plants, crossdocks, dcs, retailers])
color_map = {
    "Plant": "purple",
    "Cross-dock": "dodgerblue",
    "Distribution Centre": "black",
    "Retailer Hub": "red"
}

fig_map = px.scatter_geo(
    locations,
    lat="Lat",
    lon="Lon",
    color="Type",
    color_discrete_map=color_map,
    projection="natural earth",
    scope="world",
    title="Global Supply Chain Structure",
    template="plotly_white"
)

for trace in fig_map.data:
    trace.marker.update(size=14, line=dict(width=0.5, color='white'))

fig_map.update_geos(
    showcountries=True,
    countrycolor="lightgray",
    showland=True,
    landcolor="rgb(245,245,245)",
    fitbounds="locations"
)
fig_map.update_layout(height=550, margin=dict(l=0, r=0, t=40, b=0))
st.plotly_chart(fig_map, use_container_width=True)

# ----------------------------------------------------
# 🚢✈️🚛 FLOW SUMMARY
# ----------------------------------------------------
st.markdown("## 🚚 Transport Flows by Mode")

def sum_flows_by_mode(prefix):
    flow_cols = [c for c in df.columns if c.startswith(prefix + "[")]
    totals = {"air": 0.0, "sea": 0.0, "road": 0.0}
    for col in flow_cols:
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

display_layer_summary("Layer 1: Plants → Cross-docks (f1)", "f1", include_road=False)
display_layer_summary("Layer 2: Cross-docks → DCs (f2)", "f2", include_road=True)
display_layer_summary("Layer 3: DCs → Retailers (f3)", "f3", include_road=True)

# ----------------------------------------------------
# RAW DATA VIEW
# ----------------------------------------------------
with st.expander("📄 Show Full Data Table"):
    st.dataframe(df.head(500), use_container_width=True)

# ----------------------------------------------------
# 🌐 FOOTER LINK
# ----------------------------------------------------
st.markdown(
    """
    ---
    🌐 **Explore the full model with new facilities [here](https://tgecase-web-page-01.streamlit.app/)**
    """,
    unsafe_allow_html=True
)
