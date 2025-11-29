# -*- coding: utf-8 -*-
"""
Created on Fri Nov 28 15:50:25 2025

@author: LENOVO
"""

# ================================================================
#  merged_app.py (FINAL)
# ================================================================

import os
import random
import re
import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit.components.v1 as components
import gurobipy as gp

from sc1_app import run_sc1
from sc2_app import run_sc2
from Scenario_Setting_For_SC1F import run_scenario as run_SC1F
from Scenario_Setting_For_SC2F import run_scenario as run_SC2F

# ================================================================
# PAGE CONFIG (only once!)
# ================================================================
st.set_page_config(
    page_title="Supply Chain Suite",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================================================================
# SIDEBAR NAVIGATION WITH COLLAPSIBLE GROUPS
# ================================================================
st.sidebar.title("📌 Navigation")

# Collapsible "Factory Model" group
with st.sidebar.expander("🏭 Factory Model", expanded=True):
    factory_choice = st.radio(
        "Select model:",
        [
            "SC1 – Existing Facilities",
            "SC2 – New Facilities"
        ],
        index=None,
        key="factory_radio"
    )

# Collapsible "Optimization" group
with st.sidebar.expander("📊 Optimization", expanded=True):
    opt_choice = st.radio(
        "Select:",
        ["Optimization Dashboard"],
        index=None,
        key="optimization_radio"
    )

# ================================================================
# ROUTING LOGIC
# ================================================================
if factory_choice == "SC1 – Existing Facilities":
    run_sc1()
    st.stop()

elif factory_choice == "SC2 – New Facilities":
    run_sc2()
    st.stop()

elif opt_choice == "Optimization Dashboard":
    pass  # Continue into optimization block below

else:
    st.write("👈 Select a page from the Navigation menu.")
    st.stop()

# ================================================================
# OPTIMIZATION DASHBOARD
# ================================================================

st.title("🌍 Global Supply Chain Optimization (Gurobi)")

# ------------------------------------------------------------
# Google Analytics Injection (safe)
# ------------------------------------------------------------
GA_MEASUREMENT_ID = "G-78BY82MRZ3"

components.html(f"""
<script>
(function() {{
    const targetDoc = window.parent.document;

    const old1 = targetDoc.getElementById("ga-tag");
    const old2 = targetDoc.getElementById("ga-src");
    if (old1) old1.remove();
    if (old2) old2.remove();

    const s1 = targetDoc.createElement('script');
    s1.id = "ga-src";
    s1.async = true;
    s1.src = "https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}";
    targetDoc.head.appendChild(s1);

    const s2 = targetDoc.createElement('script');
    s2.id = "ga-tag";
    s2.innerHTML = `
        window.dataLayer = window.dataLayer || [];
        function gtag() {{ dataLayer.push(arguments); }}
        gtag('js', new Date());
        gtag('config', '{GA_MEASUREMENT_ID}', {{
            send_page_view: true
        }});
    `;
    targetDoc.head.appendChild(s2);

    console.log("GA injected successfully");
}})();
</script>
""", height=0)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def positive_input(label, default):
    """Clean numeric input helper."""
    val_str = st.text_input(label, value=str(default))
    try:
        val = float(val_str)
        return max(val, 0)
    except:
        st.warning(f"{label} must be numeric. Using {default}.")
        return default

# ------------------------------------------------------------
# Mode selection (Normal vs Session)
# ------------------------------------------------------------
mode = st.radio("Select mode:", ["Normal Mode", "Session Mode"])

if "session_step" not in st.session_state:
    st.session_state.session_step = 0

EVENTS = {
    "suez_canal": "🚢 Suez Canal is blocked.",
    "oil_crises": "⛽ Oil crisis increases energy cost.",
    "trade_war": "💼 Trade war increases tariffs.",
}

suez_flag = oil_flag = volcano_flag = trade_flag = False
tariff_rate_used = 1.0

def generate_tariff_rate():
    k = random.uniform(1, 2)
    x_pct = ((k - 1) / k) * 100
    return k, x_pct

# ------------------------------------------------------------
# SESSION MODE LOGIC
# ------------------------------------------------------------
if mode == "Session Mode":

    st.subheader("🎮 Scenario-based Simulation")

    if "remaining_events" not in st.session_state:
        st.session_state.remaining_events = list(EVENTS.keys())

    if st.button("Start / Continue Session"):
        if len(st.session_state.remaining_events) == 0:
            st.success("🎉 All scenarios completed!")
        else:
            chosen = random.choice(st.session_state.remaining_events)
            st.session_state.remaining_events.remove(chosen)
            st.session_state.active_event = chosen

            if chosen == "trade_war":
                k, pct = generate_tariff_rate()
                st.session_state.tariff_rate_random = k
                st.session_state.tariff_x_pct = pct

    if "active_event" in st.session_state:
        ev = st.session_state.active_event
        st.warning(EVENTS[ev])

        if ev == "trade_war":
            st.info(f"Tariffs increased by **{st.session_state.tariff_x_pct:.1f}%**")

        st.text_area("Comment:", placeholder="Your decision reasoning...")

    suez_flag = (st.session_state.get("active_event") == "suez_canal")
    oil_flag = (st.session_state.get("active_event") == "oil_crises")
    volcano_flag = (st.session_state.get("active_event") == "volcano")
    trade_flag = (st.session_state.get("active_event") == "trade_war")
    tariff_rate_used = st.session_state.get("tariff_rate_random", 1.0)

# ------------------------------------------------------------
# Parameter Inputs
# ------------------------------------------------------------
st.subheader("📊 Scenario Parameters")

co2_pct = positive_input("CO₂ Reduction Target (%)", 50.0) / 100
service_level = positive_input("Service Level", 0.9)

model_choice = st.selectbox(
    "Optimization model:",
    ["SC1F – Existing Facilities Only", "SC2F – Allow New Facilities"]
)

if "SC1F" in model_choice:
    co2_cost_per_ton = positive_input("CO₂ Cost per ton (€)", 37.5)
else:
    co2_cost_per_ton_New = positive_input("CO₂ Cost per ton (New Facility)", 60)

# ------------------------------------------------------------
# RUN OPTIMIZATION
# ------------------------------------------------------------
if st.button("Run Optimization"):
    with st.spinner("⚙ Optimizing with Gurobi..."):
        try:
            if "SC1F" in model_choice:
                results, model = run_SC1F(
                    CO_2_percentage=co2_pct,
                    co2_cost_per_ton=co2_cost_per_ton,
                    suez_canal=suez_flag,
                    oil_crises=oil_flag,
                    volcano=volcano_flag,
                    trade_war=trade_flag,
                    tariff_rate=tariff_rate_used,
                    print_results="NO",
                    service_level=service_level
                )
            else:
                results, model = run_SC2F(
                    CO_2_percentage=co2_pct,
                    co2_cost_per_ton_New=co2_cost_per_ton_New,
                    suez_canal=suez_flag,
                    oil_crises=oil_flag,
                    volcano=volcano_flag,
                    trade_war=trade_flag,
                    tariff_rate=tariff_rate_used,
                    print_results="NO",
                    service_level=service_level
                )

            st.success("Optimization complete! ✅")

            # ===========================================
            # Objective + Emissions
            # ===========================================
            st.metric("💰 Objective Value (€)", f"{results['Objective_value']:,.2f}")

            st.subheader("🌿 CO₂ Emissions")
            st.json({
                "Air": results.get("E_air", 0),
                "Sea": results.get("E_sea", 0),
                "Road": results.get("E_road", 0),
                "Last-mile": results.get("E_lastmile", 0),
                "Production": results.get("E_production", 0),
                "Total": results.get("CO2_Total", 0),
            })

            # ===========================================
            # 🌍 MAP (no more pd errors!)
            # ===========================================
            st.markdown("## 🌍 Global Supply Chain Map")

            nodes = [
                ("Plant", 31.23, 121.47, "Shanghai"),
                ("Plant", 22.32, 114.17, "Hong Kong"),
                ("Cross-dock", 48.85, 2.35, "Paris"),
                ("Cross-dock", 50.11, 8.68, "Frankfurt"),
                ("Cross-dock", 37.98, 23.73, "Athens"),
                ("DC", 47.50, 19.04, "Budapest"),
                ("DC", 48.14, 11.58, "Munich"),
                ("DC", 46.95, 7.44, "Bern"),
                ("DC", 45.46, 9.19, "Milan"),
                ("Retail", 55.67, 12.57, "Copenhagen"),
                ("Retail", 53.35, -6.26, "Dublin"),
                ("Retail", 51.50, -0.12, "London"),
                ("Retail", 49.82, 19.08, "Krakow"),
                ("Retail", 45.76, 4.83, "Lyon"),
                ("Retail", 43.30, 5.37, "Marseille"),
                ("Retail", 40.42, -3.70, "Madrid"),
            ]

            locations = pd.DataFrame(nodes, columns=["Type", "Lat", "Lon", "City"])

            # ================================================================
            # 🌍 FULL GLOBAL MAP (with new facilities + events)
            # ================================================================
            
            # New facilities (only if active)
            facility_coords = {
                "HUDTG": (49.61, 6.13, "Luxembourg"),
                "CZMCT": (44.83, 20.42, "Belgrade"),
                "IEILG": (47.09, 16.37, "Graz"),
                "FIMPF": (50.45, 14.50, "Prague"),
                "PLZCA": (42.70, 12.65, "Viterbo"),
            }
            
            for name, (lat, lon, city) in facility_coords.items():
                var = model.getVarByName(f"f2_2_bin[{name}]")
                if var is not None and var.X > 0.5:
                    nodes.append(("New Production Facility", lat, lon, city))
            
            # Build DataFrame
            locations = pd.DataFrame(nodes, columns=["Type", "Lat", "Lon", "City"])
            
            # ================================================================
            # Add EVENT MARKERS to the map
            # ================================================================
            event_nodes = []
            
            if suez_flag:
                event_nodes.append(("Event: Suez Canal Blockade", 30.59, 32.27, "Suez Canal Crisis"))
            
            if volcano_flag:
                event_nodes.append(("Event: Volcano Eruption", 63.63, -19.62, "Volcanic Ash Zone"))
            
            if oil_flag:
                event_nodes.append(("Event: Oil Crisis", 28.60, 47.80, "Oil Supply Shock"))
            
            if trade_flag:
                event_nodes.append(("Event: Trade War", 55.00, 60.00, "Trade War Impact Zone"))
            
            if event_nodes:
                df_events = pd.DataFrame(event_nodes, columns=["Type", "Lat", "Lon", "City"])
                locations = pd.concat([locations, df_events], ignore_index=True)
            
            # ================================================================
            # Marker colors & sizes
            # ================================================================
            color_map = {
                "Plant": "purple",
                "Cross-dock": "dodgerblue",
                "Distribution Centre": "black",
                "Retailer Hub": "red",
                "New Production Facility": "deepskyblue",
            }
            
            color_map.update({
                "Event: Suez Canal Blockade": "gold",
                "Event: Volcano Eruption": "orange",
                "Event: Oil Crisis": "brown",
                "Event: Trade War": "green",
            })
            
            size_map = {
                "Plant": 15,
                "Cross-dock": 14,
                "Distribution Centre": 16,
                "Retailer Hub": 20,
                "New Production Facility": 14,
            }
            
            size_map.update({
                "Event: Suez Canal Blockade": 18,
                "Event: Volcano Eruption": 18,
                "Event: Oil Crisis": 18,
                "Event: Trade War": 18,
            })
            
            # ================================================================
            # Build MAP
            # ================================================================
            fig_map = px.scatter_geo(
                locations,
                lat="Lat",
                lon="Lon",
                color="Type",
                text="City",
                hover_name="City",
                color_discrete_map=color_map,
                projection="natural earth",
                scope="world",
                title="Global Supply Chain Structure",
            )
            
            # marker styling
            for trace in fig_map.data:
                trace.marker.update(
                    size=size_map.get(trace.name, 12),
                    opacity=0.9,
                    line=dict(width=0.5, color="white"),
                )
            
            fig_map.update_geos(
                showcountries=True,
                countrycolor="lightgray",
                showland=True,
                landcolor="rgb(245,245,245)",
                fitbounds="locations",
            )
            
            fig_map.update_layout(
                height=600,
                margin=dict(l=0, r=0, t=40, b=0),
            )
            
            st.plotly_chart(fig_map, use_container_width=True)
            
            
            
            # ================================================================
            # 🏭 PRODUCTION OUTBOUND PIE CHART
            # ================================================================
            st.markdown("## 🏭 Production Outbound Breakdown")
            
            TOTAL_MARKET_DEMAND = 111000
            
            f1_vars = [v for v in model.getVars() if v.VarName.startswith("f1[")]
            f2_2_vars = [v for v in model.getVars() if v.VarName.startswith("f2_2[")]
            
            prod_sources = {}
            
            # Existing plants
            for plant in ["TW", "SHA"]:
                total = sum(v.X for v in f1_vars if v.VarName.startswith(f"f1[{plant},"))
                prod_sources[plant] = total
            
            # New EU facilities
            for fac in ["HUDTG", "CZMCT", "IEILG", "FIMPF", "PLZCA"]:
                total = sum(v.X for v in f2_2_vars if v.VarName.startswith(f"f2_2[{fac},"))
                prod_sources[fac] = total
            
            total_produced = sum(prod_sources.values())
            unmet = max(TOTAL_MARKET_DEMAND - total_produced, 0)
            
            labels = list(prod_sources.keys()) + ["Unmet Demand"]
            values = list(prod_sources.values()) + [unmet]
            
            df_prod = pd.DataFrame({"Source": labels, "Units Produced": values})
            
            fig_prod = px.pie(
                df_prod,
                names="Source",
                values="Units Produced",
                hole=0.3,
                title="Production Share by Source",
            )
            
            color_map = {name: col for name, col in zip(df_prod["Source"], px.colors.qualitative.Set2)}
            color_map["Unmet Demand"] = "lightgrey"
            
            fig_prod.update_traces(
                textinfo="label+percent",
                textfont_size=13,
                marker=dict(colors=[color_map[s] for s in df_prod["Source"]])
            )
            
            fig_prod.update_layout(
                showlegend=True,
                height=400,
                template="plotly_white",
                margin=dict(l=20, r=20, t=40, b=20)
            )
            
            st.plotly_chart(fig_prod, use_container_width=True)
            st.markdown("#### 📦 Production Summary Table")
            st.dataframe(df_prod.round(2), use_container_width=True)
            
            
            
            # ================================================================
            # 🚚 CROSS-DOCK OUTBOUND PIE CHART
            # ================================================================
            st.markdown("## 🚚 Cross-dock Outbound Breakdown")
            
            f2_vars = [v for v in model.getVars() if v.VarName.startswith("f2[")]
            
            crossdocks = ["ATVIE", "PLGDN", "FRCDG"]
            crossdock_flows = {}
            
            for cd in crossdocks:
                total = sum(v.X for v in f2_vars if v.VarName.startswith(f"f2[{cd},"))
                crossdock_flows[cd] = total
            
            if sum(crossdock_flows.values()) == 0:
                st.info("No cross-dock activity.")
            else:
                df_crossdock = pd.DataFrame({
                    "Crossdock": list(crossdock_flows.keys()),
                    "Shipped (units)": list(crossdock_flows.values()),
                })
                df_crossdock["Share (%)"] = df_crossdock["Shipped (units)"] / df_crossdock["Shipped (units)"].sum() * 100
            
                fig_crossdock = px.pie(
                    df_crossdock,
                    names="Crossdock",
                    values="Shipped (units)",
                    hole=0.3,
                    title="Cross-dock Outbound Share"
                )
            
                fig_crossdock.update_layout(
                    showlegend=True,
                    height=400,
                    template="plotly_white",
                    margin=dict(l=20, r=20, t=40, b=20),
                )
            
                st.plotly_chart(fig_crossdock, use_container_width=True)
            
                st.markdown("#### 🚚 Cross-dock Outbound Table")
                st.dataframe(df_crossdock.round(2), use_container_width=True)


        except Exception as e:
            st.error(f"❌ Primary optimization failed: {e}")
            st.warning("⚠ Running fallback model to compute maximum satisfiable demand...")
        
            try:
                # --------------------------------------------------
                # CHOOSE CORRECT FALLBACK MODEL
                # --------------------------------------------------
                if "SC2F" in model_choice:
                    from Scenario_Setting_For_SC2F_uns import run_scenario as run_Uns
                    results_uns, model_uns = run_Uns(
                        CO_2_percentage=co2_pct,
                        co2_cost_per_ton_New=co2_cost_per_ton_New,
                        suez_canal=suez_flag,
                        oil_crises=oil_flag,
                        volcano=volcano_flag,
                        trade_war=trade_flag,
                        tariff_rate=tariff_rate_used,
                        print_results="NO"
                    )
                else:
                    from Scenario_Setting_For_SC1F_uns import run_scenario as run_Uns
                    results_uns, model_uns = run_Uns(
                        CO_2_percentage=co2_pct,
                        co2_cost_per_ton=co2_cost_per_ton,
                        suez_canal=suez_flag,
                        oil_crises=oil_flag,
                        volcano=volcano_flag,
                        trade_war=trade_flag,
                        tariff_rate=tariff_rate_used,
                        print_results="NO"
                    )
        
                # --------------------------------------------------
                # SUCCESS DISPLAY
                # --------------------------------------------------
                st.success("Fallback optimization successful! ✅")

                # ===============================================================
                # 🎯 MAXIMUM SATISFIABLE DEMAND
                # ===============================================================
                st.markdown("## 📦 Maximum Satisfiable Demand (Fallback Model)")
                
                st.metric(
                    "Satisfied Demand (%)",
                    f"{results_uns['Satisfied_Demand_pct'] * 100:.2f}%"
                )
                
                st.metric(
                    "Satisfied Demand (Units)",
                    f"{results_uns['Satisfied_Demand_units']:,.0f}"
                )
                
                # ===============================================================
                # 💰 OBJECTIVE
                # ===============================================================
                st.markdown("## 💰 Objective Value (Excluding Slack Penalty)")
                st.metric(
                    "Objective (€)",
                    f"{results_uns['Objective_value']:,.2f}"
                )
                
                # ===============================================================
                # 🌍 MAP
                # ===============================================================
                st.markdown("## 🌍 Global Supply Chain Map (Fallback Model)")
                
                nodes = [
                    ("Plant", 31.23, 121.47, "Shanghai"),
                    ("Plant", 22.32, 114.17, "Hong Kong"),
                    ("Cross-dock", 48.85, 2.35, "Paris"),
                    ("Cross-dock", 50.11, 8.68, "Frankfurt"),
                    ("Cross-dock", 37.98, 23.73, "Athens"),
                    ("DC", 47.50, 19.04, "Budapest"),
                    ("DC", 48.14, 11.58, "Munich"),
                    ("DC", 46.95, 7.44, "Bern"),
                    ("DC", 45.46, 9.19, "Milan"),
                    ("Retail", 55.67, 12.57, "Copenhagen"),
                    ("Retail", 53.35, -6.26, "Dublin"),
                    ("Retail", 51.50, -0.12, "London"),
                    ("Retail", 49.82, 19.08, "Krakow"),
                    ("Retail", 45.76, 4.83, "Lyon"),
                    ("Retail", 43.30, 5.37, "Marseille"),
                    ("Retail", 40.42, -3.70, "Madrid"),
                ]
                
                locations = pd.DataFrame(nodes, columns=["Type", "Lat", "Lon", "City"])
                
                # Add new facilities from fallback model
                facility_coords = {
                    "HUDTG": (49.61, 6.13, "Luxembourg"),
                    "CZMCT": (44.83, 20.42, "Belgrade"),
                    "IEILG": (47.09, 16.37, "Graz"),
                    "FIMPF": (50.45, 14.50, "Prague"),
                    "PLZCA": (42.70, 12.65, "Viterbo"),
                }
                
                for name, (lat, lon, city) in facility_coords.items():
                    var = model_uns.getVarByName(f"f2_2_bin[{name}]")
                    if var is not None and var.X > 0.5:
                        nodes.append(("New Production Facility", lat, lon, city))
                
                locations = pd.DataFrame(nodes, columns=["Type", "Lat", "Lon", "City"])
                
                event_nodes = []
                
                if suez_flag:
                    event_nodes.append(("Event: Suez Canal Blockade", 30.59, 32.27, "Suez Canal Crisis"))
                if volcano_flag:
                    event_nodes.append(("Event: Volcano Eruption", 63.63, -19.62, "Volcanic Ash Zone"))
                if oil_flag:
                    event_nodes.append(("Event: Oil Crisis", 28.60, 47.80, "Oil Supply Shock"))
                if trade_flag:
                    event_nodes.append(("Event: Trade War", 55.00, 60.00, "Trade War Impact Zone"))
                
                if event_nodes:
                    df_events = pd.DataFrame(event_nodes, columns=["Type", "Lat", "Lon", "City"])
                    locations = pd.concat([locations, df_events], ignore_index=True)
                
                color_map = {
                    "Plant": "purple",
                    "Cross-dock": "dodgerblue",
                    "Distribution Centre": "black",
                    "Retailer Hub": "red",
                    "New Production Facility": "deepskyblue",
                    "Event: Suez Canal Blockade": "gold",
                    "Event: Volcano Eruption": "orange",
                    "Event: Oil Crisis": "brown",
                    "Event: Trade War": "green",
                }
                
                size_map = {
                    "Plant": 15,
                    "Cross-dock": 14,
                    "Distribution Centre": 16,
                    "Retailer Hub": 20,
                    "New Production Facility": 14,
                    "Event: Suez Canal Blockade": 18,
                    "Event: Volcano Eruption": 18,
                    "Event: Oil Crisis": 18,
                    "Event: Trade War": 18,
                }
                
                fig_map = px.scatter_geo(
                    locations,
                    lat="Lat",
                    lon="Lon",
                    color="Type",
                    text="City",
                    hover_name="City",
                    color_discrete_map=color_map,
                    projection="natural earth",
                    scope="world",
                    title="Global Supply Chain Structure (Fallback Model)",
                )
                
                for trace in fig_map.data:
                    trace.marker.update(
                        size=size_map.get(trace.name, 12),
                        opacity=0.9,
                        line=dict(width=0.5, color="white"),
                    )
                
                fig_map.update_geos(
                    showcountries=True,
                    countrycolor="lightgray",
                    showland=True,
                    landcolor="rgb(245,245,245)",
                    fitbounds="locations",
                )
                
                fig_map.update_layout(
                    height=600,
                    margin=dict(l=0, r=0, t=40, b=0),
                )
                
                st.plotly_chart(fig_map, use_container_width=True)
                
                # ===============================================================
                # 🏭 PRODUCTION OUTBOUND PIE CHART
                # ===============================================================
                st.markdown("## 🏭 Production Outbound Breakdown (Fallback Model)")
                
                f1_vars = [v for v in model_uns.getVars() if v.VarName.startswith("f1[")]
                f2_2_vars = [v for v in model_uns.getVars() if v.VarName.startswith("f2_2[")]
                
                prod_sources = {}
                
                # Existing plants
                for plant in ["TW", "SHA"]:
                    total = sum(v.X for v in f1_vars if v.VarName.startswith(f"f1[{plant},"))
                    prod_sources[plant] = total
                
                # New EU facilities
                for fac in ["HUDTG", "CZMCT", "IEILG", "FIMPF", "PLZCA"]:
                    total = sum(v.X for v in f2_2_vars if v.VarName.startswith(f"f2_2[{fac},"))
                    prod_sources[fac] = total
                
                TOTAL_MARKET_DEMAND = 111000
                total_produced = sum(prod_sources.values())
                unmet = max(TOTAL_MARKET_DEMAND - total_produced, 0)
                
                labels = list(prod_sources.keys()) + ["Unmet Demand"]
                values = list(prod_sources.values()) + [unmet]
                
                df_prod = pd.DataFrame({"Source": labels, "Units Produced": values})
                
                fig_prod = px.pie(
                    df_prod,
                    names="Source",
                    values="Units Produced",
                    hole=0.3,
                    title="Production Share by Source (Fallback Model)",
                )
                
                fig_prod.update_traces(
                    textinfo="label+percent",
                    textfont_size=13
                )
                
                st.plotly_chart(fig_prod, use_container_width=True)
                
                st.dataframe(df_prod.round(2), use_container_width=True)
                
                # ===============================================================
                # 🚚 CROSS-DOCK OUTBOUND PIE CHART
                # ===============================================================
                st.markdown("## 🚚 Cross-dock Outbound Breakdown (Fallback Model)")
                
                f2_vars = [v for v in model_uns.getVars() if v.VarName.startswith("f2[")]
                
                crossdocks = ["ATVIE", "PLGDN", "FRCDG"]
                crossdock_flows = {}
                
                for cd in crossdocks:
                    total = sum(v.X for v in f2_vars if v.VarName.startswith(f"f2[{cd},"))
                    crossdock_flows[cd] = total
                
                if sum(crossdock_flows.values()) == 0:
                    st.info("No cross-dock activity.")
                else:
                    df_crossdock = pd.DataFrame({
                        "Crossdock": list(crossdock_flows.keys()),
                        "Shipped (units)": list(crossdock_flows.values()),
                    })
                    df_crossdock["Share (%)"] = (
                        df_crossdock["Shipped (units)"] /
                        df_crossdock["Shipped (units)"].sum()
                    ) * 100
                
                    fig_crossdock = px.pie(
                        df_crossdock,
                        names="Crossdock",
                        values="Shipped (units)",
                        hole=0.3,
                        title="Cross-dock Outbound Share (Fallback Model)"
                    )
                
                    st.plotly_chart(fig_crossdock, use_container_width=True)
                    st.dataframe(df_crossdock.round(2), use_container_width=True)
                
                        
        
            except Exception as e2:
                st.error(f"❌ Fallback model also failed: {e2}")


