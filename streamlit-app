# -*- coding: utf-8 -*-
"""
Streamlit Dashboard – Sensitivity and Factory Insights
Author: Arda Aydın
"""

import streamlit as st
import pandas as pd
import plotly.express as px

# ---------------------------------------------
# CONFIGURATION
# ---------------------------------------------
st.set_page_config(
    page_title="Optimization Sensitivity Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏭 CO₂ Sensitivity & Factory Opening Dashboard")

uploaded_file = st.file_uploader("📂 Upload your 'simulation_results_full.xlsx' (single Summary sheet):", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, sheet_name="Summary")

    # ---------------------------------------------
    # SIDEBAR FILTERS
    # ---------------------------------------------
    st.sidebar.header("🎛️ Filter Parameters")

    weight_selected = st.sidebar.selectbox("Select Product Weight (kg)", sorted(df["Product_weight"].unique()))
    co2_pct = st.sidebar.slider("CO₂ Percentage", float(df["CO2_percentage"].min()), float(df["CO2_percentage"].max()),
                                float(df["CO2_percentage"].mean()), step=0.01)
    co2_cost = st.sidebar.slider("CO₂ Manufacturing Cost (€ per ton)",
                                 float(df["CO2_CostAtMfg"].min()), float(df["CO2_CostAtMfg"].max()),
                                 float(df["CO2_CostAtMfg"].mean()), step=0.5)

    # Filter by product weight for simplicity
    subset = df[df["Product_weight"] == weight_selected]

    # ---------------------------------------------
    # KPI VIEW – Closest Scenario
    # ---------------------------------------------
    st.subheader("📊 Closest Scenario Details")
    closest = subset.loc[
        (subset["CO2_percentage"] - co2_pct).abs().idxmin()
    ]
    st.write(closest.to_frame().T)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Objective (€)", f"{closest['Objective_value']:.2f}")
    col2.metric("Total CO₂", f"{closest['CO2_Total']:.2f}")
    col3.metric("Inventory Total (€)", f"{closest[['Inventory_L1','Inventory_L2','Inventory_L3']].sum():.2f}")
    col4.metric("Transport Total (€)", f"{closest[['Transport_L1','Transport_L2','Transport_L3']].sum():.2f}")

    # ---------------------------------------------
    # FACTORY OPENINGS (f2_2)
    # ---------------------------------------------
    if "f2_2" in df.columns:
        st.markdown("## 🏭 Factory Openings (f2_2)")
        # Show frequency of factory openings under each CO₂%
        pivot_factories = df.groupby(["CO2_percentage", "Product_weight"])["f2_2"].mean().reset_index()
        fig_fact = px.imshow(
            pivot_factories.pivot("Product_weight", "CO2_percentage", "f2_2"),
            aspect="auto",
            color_continuous_scale="Blues",
            title="Factory Opening Heatmap (1=open)",
            labels={"x": "CO₂ %", "y": "Product Weight"}
        )
        st.plotly_chart(fig_fact, use_container_width=True)

        st.dataframe(pivot_factories, use_container_width=True)

    # ---------------------------------------------
    # SENSITIVITY CHARTS
    # ---------------------------------------------
    st.markdown("## 🔍 Sensitivity of Key Costs")

    colA, colB = st.columns(2)

    # Objective vs CO₂ Manufacturing Cost
    fig_obj = px.line(
        subset, x="CO2_CostAtMfg", y="Objective_value", color="CO2_percentage",
        title="Objective Value vs CO₂ Manufacturing Cost",
        markers=True, template="plotly_white"
    )
    colA.plotly_chart(fig_obj, use_container_width=True)

    # Total CO₂ vs Manufacturing Cost
    fig_co2 = px.line(
        subset, x="CO2_CostAtMfg", y="CO2_Total", color="CO2_percentage",
        title="Total CO₂ Emissions vs Manufacturing Cost",
        markers=True, template="plotly_white"
    )
    colB.plotly_chart(fig_co2, use_container_width=True)

    # ---------------------------------------------
    # INVENTORY & TRANSPORT TREND
    # ---------------------------------------------
    st.markdown("## 📦 Inventory and 🚚 Transport Trends")

    subset["Inventory_Total"] = subset[["Inventory_L1", "Inventory_L2", "Inventory_L3"]].sum(axis=1)
    subset["Transport_Total"] = subset[["Transport_L1", "Transport_L2", "Transport_L3"]].sum(axis=1)

    colC, colD = st.columns(2)

    fig_inv = px.line(
        subset, x="CO2_CostAtMfg", y="Inventory_Total", color="CO2_percentage",
        title="Inventory Cost vs CO₂ Manufacturing Cost",
        markers=True, template="plotly_white"
    )
    colC.plotly_chart(fig_inv, use_container_width=True)

    fig_tr = px.line(
        subset, x="CO2_CostAtMfg", y="Transport_Total", color="CO2_percentage",
        title="Transport Cost vs CO₂ Manufacturing Cost",
        markers=True, template="plotly_white"
    )
    colD.plotly_chart(fig_tr, use_container_width=True)

    # ---------------------------------------------
    # RAW DATA VIEW
    # ---------------------------------------------
    with st.expander("📄 Show Full Summary Data"):
        st.dataframe(df, use_container_width=True)

else:
    st.info("👆 Upload the Excel file with a single 'Summary' sheet to start.")
