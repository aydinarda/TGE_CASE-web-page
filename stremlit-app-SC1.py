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
# Create slider for CO₂ Reduction %
co2_pct = st.sidebar.slider(
    f"CO₂ Reduction Target ({co2_col})",
    0.0, 1.0, 0.25, step=0.01,
    help="Select a CO₂ reduction target between 0–100%. If the scenario was never feasible, you’ll see a message below."
)

# Find closest feasible scenario (if any)
if (subset[co2_col] - co2_pct).abs().min() < 1e-6:
    closest = subset.iloc[(subset[co2_col] - co2_pct).abs().argmin()]
    feasible = True
else:
    feasible = False

# ----------------------------------------------------
# 🚦 FEASIBILITY CHECK
# ----------------------------------------------------
if not feasible:
    st.error(
        f"❌ This solution was never feasible — even Swiss precision couldn't optimize it! 🇨🇭\n\n"
        "Try adjusting your CO₂ target or demand level."
    )
    st.stop()


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
# ---------- totals with smart fallbacks ----------
# Inventory
inv_layer_cols = [c for c in ["Inventory_L1", "Inventory_L2", "Inventory_L3"] if c in closest.index]
if inv_layer_cols:
    inv_total = float(closest[inv_layer_cols].sum())
elif "Transit Inventory Cost" in closest.index:
    inv_total = float(closest["Transit Inventory Cost"])
else:
    inv_total = None

# Transport
tr_layer_cols = [c for c in ["Transport_L1", "Transport_L2", "Transport_L3"] if c in closest.index]
if tr_layer_cols:
    tr_total = float(closest[tr_layer_cols].sum())
elif "Transportation Cost" in closest.index:
    tr_total = float(closest["Transportation Cost"])
else:
    tr_total = None

col3.metric("Inventory Total (€)", f"{inv_total:.2f}" if inv_total is not None else "N/A")
col4.metric("Transport Total (€)", f"{tr_total:.2f}" if tr_total is not None else "N/A")

# ----------------------------------------------------
# COST vs EMISSION PLOT
# ----------------------------------------------------
st.markdown("## 📈 Cost vs CO₂ Emission Sensitivity")

cost_metric_map = {
    "Total Cost (€)": "Objective_value" if "Objective_value" in df.columns else "Total Cost",
    "Inventory Cost (€)": (
        ["Inventory_L1", "Inventory_L2", "Inventory_L3"]
        if any(c in df.columns for c in ["Inventory_L1", "Inventory_L2", "Inventory_L3"])
        else ["Transit Inventory Cost"]
    ),
    "Transport Cost (€)": (
        ["Transport_L1", "Transport_L2", "Transport_L3"]
        if any(c in df.columns for c in ["Transport_L1", "Transport_L2", "Transport_L3"])
        else ["Transportation Cost"]
    ),
}

selected_metric_label = st.selectbox(
    "Select Cost Metric to Plot:",
    list(cost_metric_map.keys()),
    index=0
)

filtered = subset.copy()

# Compute selected cost robustly
metric_cols = cost_metric_map[selected_metric_label]
if isinstance(metric_cols, list):
    cols_to_sum = [c for c in metric_cols if c in filtered.columns]
    if cols_to_sum:
        filtered["Selected_Cost"] = filtered[cols_to_sum].sum(axis=1)
    else:
        st.warning(f"⚠️ Could not find any columns for {selected_metric_label}.")
        st.stop()
else:
    filtered["Selected_Cost"] = filtered[metric_cols]

x_col = "Total Emissions" if "Total Emissions" in filtered.columns else "CO2_Total"

# --- Build Plotly chart ---
fig = px.scatter(
    filtered,
    x=x_col,
    y="Selected_Cost",
    color=co2_col,
    template="plotly_white",
    color_continuous_scale="Viridis",
    title=f"{selected_metric_label} vs CO₂ Emissions ({selected_sheet})",
)

# Safely find the point for the selected scenario
if "Selected_Cost" in closest.index:
    closest_y = closest["Selected_Cost"]
else:
    if isinstance(metric_cols, list):
        cols_to_sum = [c for c in metric_cols if c in closest.index]
        closest_y = closest[cols_to_sum].sum()
    else:
        closest_y = closest.get(metric_cols, 0)

fig.add_scatter(
    x=[closest[x_col]],
    y=[closest_y],
    mode="markers+text",
    marker=dict(size=14, color="red"),
    text=["Selected Scenario"],
    textposition="top center",
    name="Selected"
)


# --- Display chart ---
st.plotly_chart(fig, use_container_width=True)

# ----------------------------------------------------
# 🆕 COST vs EMISSIONS DUAL-AXIS BAR-LINE PLOT (DYNAMIC)
# ----------------------------------------------------
st.markdown("## 💶 Cost vs Emissions ")

@st.cache_data(show_spinner=False)
def generate_cost_emission_chart_plotly_dynamic(df_sheet: pd.DataFrame, selected_value: float):
    # Detect column names
    emissions_col = "Total Emissions" if "Total Emissions" in df_sheet.columns else "CO2_Total"
    cost_col = "Total Cost" if "Total Cost" in df_sheet.columns else "Objective_value"
    co2_col = next((c for c in df_sheet.columns if "reduction" in c.lower() or "%" in c.lower()), None)

    df_chart = df_sheet[[emissions_col, cost_col, co2_col]].copy().sort_values(by=co2_col)
    df_chart["Emissions (k)"] = df_chart[emissions_col] / 1000
    df_chart["Cost (M)"] = df_chart[cost_col] / 1_000_000

    import plotly.graph_objects as go
    fig = go.Figure()

    # Grey bars: emissions
    fig.add_trace(go.Bar(
        x=df_chart[co2_col],
        y=df_chart["Emissions (k)"],
        name="Emissions (thousand)",
        marker_color="dimgray",
        opacity=0.9,
        yaxis="y1"
    ))

    # Red dotted line: cost
    fig.add_trace(go.Scatter(
        x=df_chart[co2_col],
        y=df_chart["Cost (M)"],
        name="Cost (million €)",
        mode="lines+markers",
        line=dict(color="red", width=2, dash="dot"),
        marker=dict(size=6, color="red"),
        yaxis="y2"
    ))

    # Highlight the selected scenario
    if selected_value is not None and selected_value in df_chart[co2_col].values:
        highlight_row = df_chart.loc[df_chart[co2_col] == selected_value].iloc[0]
        fig.add_trace(go.Scatter(
            x=[highlight_row[co2_col]],
            y=[highlight_row["Cost (M)"]],
            mode="markers+text",
            marker=dict(size=14, color="red", symbol="circle"),
            text=[f"{highlight_row[co2_col]:.2%}"],
            textposition="top center",
            name="Selected Scenario",
            yaxis="y2"
        ))

    # Layout and style
    fig.update_layout(
        template="plotly_white",
        title=dict(text="<b>Cost vs. Emissions</b>", x=0.45, font=dict(color="firebrick", size=20)),
        xaxis=dict(
            title="CO₂ Reduction (%)",
            tickformat=".0%",
            showgrid=False
        ),
        yaxis=dict(title="Emissions (thousand)", side="left", showgrid=False),
        yaxis2=dict(title="Cost (million €)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=-0.25, x=0.3),
        margin=dict(l=40, r=40, t=60, b=60),
        height=450
    )

    return fig

fig_cost_emission = generate_cost_emission_chart_plotly_dynamic(df, closest[co2_col])
st.plotly_chart(fig_cost_emission, use_container_width=True)

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
# 🚢✈️🚛 FLOW SUMMARY (using LayerX naming)
# ----------------------------------------------------
st.markdown("## 🚚 Transport Flows by Mode")

# --- Helper to read totals safely ---
def get_value_safe(col):
    return float(closest[col]) if col in closest.index else 0.0

# --- Layer 1: Plants → Cross-docks ---
st.markdown("### Layer 1: Plants → Cross-docks (f1)")
col1, col2 = st.columns(2)
col1.metric("🚢 Sea", f"{get_value_safe('Layer1Sea'):,.0f} units")
col2.metric("✈️ Air", f"{get_value_safe('Layer1Air'):,.0f} units")
if get_value_safe("Layer1Sea") + get_value_safe("Layer1Air") == 0:
    st.info("No transport activity recorded for this layer.")
st.markdown("---")

# --- Layer 2: Cross-docks → DCs ---
st.markdown("### Layer 2: Cross-docks → DCs (f2)")
col1, col2, col3 = st.columns(3)
col1.metric("🚢 Sea", f"{get_value_safe('Layer2Sea'):,.0f} units")
col2.metric("✈️ Air", f"{get_value_safe('Layer2Air'):,.0f} units")
col3.metric("🚛 Road", f"{get_value_safe('Layer2Road'):,.0f} units")
if get_value_safe("Layer2Sea") + get_value_safe("Layer2Air") + get_value_safe("Layer2Road") == 0:
    st.info("No transport activity recorded for this layer.")
st.markdown("---")

# --- Layer 3: DCs → Retailers ---
st.markdown("### Layer 3: DCs → Retailers (f3)")
col1, col2, col3 = st.columns(3)
col1.metric("🚢 Sea", f"{get_value_safe('Layer3Sea'):,.0f} units")
col2.metric("✈️ Air", f"{get_value_safe('Layer3Air'):,.0f} units")
col3.metric("🚛 Road", f"{get_value_safe('Layer3Road'):,.0f} units")
if get_value_safe("Layer3Sea") + get_value_safe("Layer3Air") + get_value_safe("Layer3Road") == 0:
    st.info("No transport activity recorded for this layer.")
st.markdown("---")

# ----------------------------------------------------
# 💰🌿 COST & EMISSION DISTRIBUTION SECTION
# ----------------------------------------------------
st.markdown("## 💰 Cost and 🌿 Emission Distribution")

colB, colC = st.columns(2)


# --- 2️⃣ Cost Distribution ---
with colB:
    st.subheader("Cost Distribution")

    cost_components = {
        "Transportation Cost": closest.get("Transportation Cost", 0),
        "Sourcing/Handling Cost": closest.get("Sourcing/Handling Cost", 0),
        "CO₂ Cost in Production": closest.get("CO2 Cost in Production", 0),
        "Inventory Cost": closest.get("Transit Inventory Cost", 0),
    }

    df_cost_dist = pd.DataFrame({
        "Category": list(cost_components.keys()),
        "Value": list(cost_components.values())
    })

    fig_cost_dist = px.bar(
        df_cost_dist,
        x="Category",
        y="Value",
        text="Value",
        color="Category",
        color_discrete_sequence=["#A7C7E7", "#B0B0B0", "#F8C471", "#5D6D7E"],
        title="Cost Distribution"
    )
    fig_cost_dist.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    fig_cost_dist.update_layout(
        template="plotly_white",
        showlegend=False,
        xaxis_tickangle=-35,
        yaxis_title="€",
        height=400
    )
    st.plotly_chart(fig_cost_dist, use_container_width=True)

# --- 3️⃣ Emission Distribution ---
with colC:
    st.subheader("Emission Distribution")

    emission_cols = ["E(Air)", "E(Sea)", "E(Road)", "E(Last-mile)", "E(Production)"]

    # ensure emission columns exist in current Array sheet
    available_cols = [c for c in emission_cols if c in df.columns]
    if not available_cols:
        st.warning("No emission columns found in this sheet.")
    else:
        # Find the row that matches selected CO2 %
        co2_col = next((c for c in df.columns if "reduction" in c.lower()), None)
        if co2_col is None:
            st.error("No CO₂ reduction column found.")
        else:
            # Find the nearest CO₂ value in current sheet
            target_row = df.iloc[(df[co2_col] - co2_pct).abs().argmin()]

            # Build emission data dictionary
            emission_data = {}
            for col in emission_cols:
                try:
                    emission_data[col.replace("E(", "").replace(")", "")] = float(target_row[col])
                except Exception:
                    emission_data[col.replace("E(", "").replace(")", "")] = 0.0

            df_emission_dist = pd.DataFrame({
                "Mode": list(emission_data.keys()),
                "Emissions": list(emission_data.values())
            })

            import plotly.express as px
            fig_emission_dist = px.bar(
                df_emission_dist,
                x="Mode",
                y="Emissions",
                text="Emissions",
                color="Mode",
                color_discrete_sequence=["#4B8A08", "#2E8B57", "#228B22", "#90EE90", "#1C7C54"],
                title="Emission Distribution"
            )

            fig_emission_dist.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig_emission_dist.update_layout(
                template="plotly_white",
                showlegend=False,
                xaxis_tickangle=-35,
                yaxis_title="Tons of CO₂",
                height=400
            )
            st.plotly_chart(fig_emission_dist, use_container_width=True)

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
