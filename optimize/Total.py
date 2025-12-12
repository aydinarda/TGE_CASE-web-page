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
from MASTER import run_scenario_master  # NEW: fully parametric master model
from collections import defaultdict



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
# Helpers (NEW): compute node activity from flows
# ------------------------------------------------------------
EPS = 1e-6

# IMPORTANT: Map displayed City labels -> model facility keys used in variable names
# Adjust these to match YOUR model naming.
CITY_TO_KEYS = {
    # Plants (model keys)
    "Shanghai": ["SHA"],
    "Hong Kong": ["TW"],  # if TW plant is represented by Hong Kong on the map

    # Cross-docks (example mapping; adjust!)
    "Paris": ["FRCDG"],
    "Frankfurt": ["PLGDN"],
    "Athens": ["ATVIE"],

    # DCs (adjust to your actual DC keys!)
    "Budapest": ["PED"],
    "Munich": ["FR6216"],
    "Bern": ["RIX"],
    "Milan": ["GMZ"],

    # Retailers (adjust if your model uses different retailer keys)
    "Copenhagen": ["Copenhagen"],
    "Dublin": ["Dublin"],
    "London": ["London"],
    "Krakow": ["Krakow"],
    "Lyon": ["Lyon"],
    "Marseille": ["Marseille"],
    "Madrid": ["Madrid"],
}

def _parse_inside_brackets(varname: str):
    # "f2[ATVIE,GMZ,air]" -> ["ATVIE","GMZ","air"]
    i = varname.find("[")
    j = varname.rfind("]")
    if i == -1 or j == -1 or j <= i:
        return None
    inside = varname[i+1:j]
    return [x.strip() for x in inside.split(",")]

def compute_key_throughput(model) -> dict:
    """
    Returns dict: facility_key -> total flow touching the node (in+out aggregated)
    Based on f1, f2, f2_2, f3 variable values.
    """
    thr = defaultdict(float)
    for v in model.getVars():
        n = v.VarName

        if n.startswith("f1[") or n.startswith("f2[") or n.startswith("f2_2[") or n.startswith("f3["):
            parts = _parse_inside_brackets(n)
            if not parts or len(parts) < 2:
                continue

            o, d = parts[0], parts[1]
            try:
                x = float(v.X)
            except Exception:
                x = 0.0

            if x > EPS:
                thr[o] += x
                thr[d] += x

    return thr

def city_is_active(city: str, key_thr: dict) -> bool:
    keys = CITY_TO_KEYS.get(city, [])
    return sum(key_thr.get(k, 0.0) for k in keys) > EPS


# ------------------------------------------------------------
# Mode selection (Normal vs Session)
# ------------------------------------------------------------
# Mode selection (Normal vs Session vs Gamification)
# ------------------------------------------------------------
mode = st.radio("Select mode:", ["Normal Mode", "Session Mode", "Gamification Mode"])

if "session_step" not in st.session_state:
    st.session_state.session_step = 0

EVENTS = {
    "suez_canal": "🚢 Suez Canal is blocked.",
    "oil_crises": "⛽ Oil crisis increases energy cost.",
    "trade_war": "💼 Trade war increases tariffs.",
}

# default scenario flags
suez_flag = oil_flag = volcano_flag = trade_flag = False
tariff_rate_used = 1.0

# ------------------------------------------------------------
# SESSION MODE LOGIC (unchanged behaviour)
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

    # derive flags from active event
    suez_flag = (st.session_state.get("active_event") == "suez_canal")
    oil_flag = (st.session_state.get("active_event") == "oil_crises")
    volcano_flag = (st.session_state.get("active_event") == "volcano")
    trade_flag = (st.session_state.get("active_event") == "trade_war")
    tariff_rate_used = st.session_state.get("tariff_rate_random", 1.0)

# ------------------------------------------------------------
# GAMIFICATION MODE LOGIC 
# ------------------------------------------------------------
elif mode == "Gamification Mode":
    st.subheader("🧩 Gamification Mode: Design Your Network")

    st.markdown(
        "Turn facilities and transport modes on/off and see how the optimal network "
        "and emissions change. This uses the parametric `MASTER` model."
    )

    # --- Scenario events as toggles ---
    st.markdown("#### Scenario events")
    col_ev1, col_ev2 = st.columns(2)
    with col_ev1:
        suez_flag = st.checkbox(
            "Suez Canal Blockade (no sea from plants to Europe)",
            value=False,
            key="gm_suez"
        )
        oil_flag = st.checkbox(
            "Oil Crisis (increase all transport costs)",
            value=False,
            key="gm_oil"
        )
    with col_ev2:
        volcano_flag = st.checkbox(
            "Volcanic Eruption (no air shipments)",
            value=False,
            key="gm_volcano"
        )
        trade_flag = st.checkbox(
            "Trade War (more expensive sourcing)",
            value=False,
            key="gm_trade"
        )

    tariff_rate_used = 1.0
    if trade_flag:
        tariff_rate_used = st.slider(
            "Tariff multiplier on sourcing cost",
            min_value=1.0,
            max_value=2.0,
            value=1.3,
            step=0.05,
            help="1.0 = no tariff, 2.0 = sourcing cost doubles",
        )

    # --- Facility activation ---
    st.markdown("#### Facility activation")

    plants_all = ["TW", "SHA"]
    crossdocks_all = ["ATVIE", "PLGDN", "FRCDG"]
    dcs_all = ["PED", "FR6216", "RIX", "GMZ"]
    new_locs_all = ["HUDTG", "CZMCT", "IEILG", "FIMPF", "PLZCA"]

    col_p, col_c, col_d, col_n = st.columns(4)
    with col_p:
        st.caption("Plants")
        gm_active_plants = [
            p for p in plants_all
            if st.checkbox(p, value=True, key=f"gm_pl_{p}")
        ]
    with col_c:
        st.caption("Cross-docks")
        gm_active_crossdocks = [
            c for c in crossdocks_all
            if st.checkbox(c, value=True, key=f"gm_cd_{c}")
        ]
    with col_d:
        st.caption("DCs")
        gm_active_dcs = [
            d for d in dcs_all
            if st.checkbox(d, value=True, key=f"gm_dc_{d}")
        ]
    with col_n:
        st.caption("New production sites")
        gm_active_new_locs = [
            n for n in new_locs_all
            if st.checkbox(n, value=True, key=f"gm_new_{n}")
        ]

    # --- Mode activation ---
    st.markdown("#### Allowed transport modes per layer")

    all_modes = ["air", "sea", "road"]
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        gm_modes_L1 = st.multiselect(
            "Plant → Cross-dock",
            options=all_modes,
            default=["air", "sea"],
            key="gm_modes_L1",
        )
    with col_m2:
        gm_modes_L2 = st.multiselect(
            "Cross-dock / New → DC",
            options=all_modes,
            default=all_modes,
            key="gm_modes_L2",
        )
    with col_m3:
        gm_modes_L3 = st.multiselect(
            "DC → Retailer",
            options=all_modes,
            default=all_modes,
            key="gm_modes_L3",
        )

    # Make sure lists exist even if user deselects everything
    gm_active_plants = gm_active_plants or []
    gm_active_crossdocks = gm_active_crossdocks or []
    gm_active_dcs = gm_active_dcs or []
    gm_active_new_locs = gm_active_new_locs or []
    gm_modes_L1 = gm_modes_L1 or []
    gm_modes_L2 = gm_modes_L2 or []
    gm_modes_L3 = gm_modes_L3 or []

# For Normal Mode we keep the default flags (all False, tariff 1.0)

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
            # 1) Choose which model to run
            if mode == "Gamification Mode":
                # Use the fully parametric MASTER model
                master_kwargs = dict(
                    active_plants=gm_active_plants,
                    active_crossdocks=gm_active_crossdocks,
                    active_new_locs=gm_active_new_locs,
                    active_dcs=gm_active_dcs,
                    active_modes_L1=gm_modes_L1,
                    active_modes_L2=gm_modes_L2,
                    active_modes_L3=gm_modes_L3,
                    CO_2_percentage=co2_pct,
                    suez_canal=suez_flag,
                    oil_crises=oil_flag,
                    volcano=volcano_flag,
                    trade_war=trade_flag,
                    tariff_rate=tariff_rate_used,
                    service_level=service_level,
                    print_results="NO",
                )

                # Use the same CO₂ cost inputs as SC1F/SC2F UI
                if "SC1F" in model_choice:
                    master_kwargs["co2_cost_per_ton"] = co2_cost_per_ton
                else:
                    master_kwargs["co2_cost_per_ton_New"] = co2_cost_per_ton_New

                results, model = run_scenario_master(**master_kwargs)
                
                # ------------------------------------------------------------
                # Benchmarking
                # ------------------------------------------------------------
                try:
                    # Always benchmark against SC2F optimal (Allow New Facilities)
                    benchmark_label = "SC2F Optimal (Allow New Facilities)"
                
                    # Use the same CO₂ price the user entered
                    # - SC1F seçiliyse: co2_cost_per_ton var
                    # - SC2F seçiliyse: co2_cost_per_ton_New var
                    bench_co2_existing = co2_cost_per_ton if "SC1F" in model_choice else co2_cost_per_ton_New
                    bench_co2_new      = co2_cost_per_ton_New if "SC2F" in model_choice else co2_cost_per_ton
                
                    benchmark_results, benchmark_model = run_SC2F(
                        CO_2_percentage=co2_pct,
                        co2_cost_per_ton=bench_co2_existing,
                        co2_cost_per_ton_New=bench_co2_new,
                        suez_canal=suez_flag,
                        oil_crises=oil_flag,
                        volcano=volcano_flag,
                        trade_war=trade_flag,
                        tariff_rate=tariff_rate_used,
                        print_results="NO",
                        service_level=service_level,
                    )
                
                except Exception as _bench_e:
                    benchmark_results = None
                    benchmark_model = None
                    benchmark_label = None
                    st.warning(f"Benchmark run failed (showing only gamification results). Reason: {_bench_e}")
                
                
                

            elif "SC1F" in model_choice:
                # Existing facilities only
                results, model = run_SC1F(
                    CO_2_percentage=co2_pct,
                    co2_cost_per_ton=co2_cost_per_ton,
                    suez_canal=suez_flag,
                    oil_crises=oil_flag,
                    volcano=volcano_flag,
                    trade_war=trade_flag,
                    tariff_rate=tariff_rate_used,
                    print_results="NO",
                    service_level=service_level,
                )
            else:
                # Allow new EU facilities (SC2F)
                results, model = run_SC2F(
                    CO_2_percentage=co2_pct,
                    co2_cost_per_ton_New=co2_cost_per_ton_New,
                    suez_canal=suez_flag,
                    oil_crises=oil_flag,
                    volcano=volcano_flag,
                    trade_war=trade_flag,
                    tariff_rate=tariff_rate_used,
                    print_results="NO",
                    service_level=service_level,
                )


            st.success("Optimization complete! ✅")

            # ===========================================
            # Objective + Emissions
            # ===========================================
            st.metric("💰 Objective Value (€)", f"{results['Objective_value']:,.2f}")

            # ------------------------------------------------------------
            # Show gap vs optimal (only in Gamification Mode)
            # ------------------------------------------------------------
            if mode == "Gamification Mode" and benchmark_results is not None:
                try:
                    stud_obj = float(results.get("Objective_value", 0.0))
                    opt_obj  = float(benchmark_results.get("Objective_value", 0.0))
                    gap = stud_obj - opt_obj
                    gap_pct = (gap / opt_obj * 100.0) if opt_obj != 0 else 0.0
            
                    st.subheader("🏁 Gap vs Optimal")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Your (Gamification) Objective (€)", f"{stud_obj:,.2f}")
                    c2.metric(benchmark_label or "Optimal Objective (€)", f"{opt_obj:,.2f}")
                    c3.metric("Gap (You − Optimal)", f"{gap:,.2f}", delta=f"{gap_pct:+.2f}%")
            
                    with st.expander("See benchmark breakdown"):
                        st.json({
                            "Benchmark": benchmark_label,
                            "Benchmark Objective": opt_obj,
                            "Your Objective": stud_obj,
                            "Absolute Gap": gap,
                            "Gap (%)": gap_pct,
                        })
                except Exception:
                    pass





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
                "DC": "black",
                "Retail": "red",
                "New Production Facility": "deepskyblue",
                "Event: Suez Canal Blockade": "gold",
                "Event: Volcano Eruption": "orange",
                "Event: Oil Crisis": "brown",
                "Event: Trade War": "green",
            }
            
            size_map = {
                "Plant": 15,
                "Cross-dock": 14,
                "DC": 16,
                "Retail": 20,
                "New Production Facility": 14,
                "Event: Suez Canal Blockade": 18,
                "Event: Volcano Eruption": 18,
                "Event: Oil Crisis": 18,
                "Event: Trade War": 18,
            }

            
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
            
            # compute activity once
            key_thr = compute_key_throughput(model)
            
            for trace in fig_map.data:
                trace.marker.update(
                    size=size_map.get(trace.name, 12),
                    line=dict(width=0.5, color="white"),
                )
            
                if trace.name.startswith("Event:") or trace.name == "New Production Facility":
                    trace.marker.update(opacity=0.9)
                    continue
            
                if hasattr(trace, "text") and trace.text is not None:
                    per_point_opacity = [
                        0.9 if city_is_active(city, key_thr) else 0.25
                        for city in trace.text
                    ]
                    trace.marker.update(opacity=per_point_opacity)
                else:
                    trace.marker.update(opacity=0.9)

            
                # Events and New Production Facility -> always bright (unchanged behaviour)
                if trace.name.startswith("Event:") or trace.name == "New Production Facility":
                    trace.marker.update(opacity=0.9)
                    continue
            
                # For other facility types: per-point opacity based on City activity
                # px.scatter_geo puts city labels into trace.text
                if hasattr(trace, "text") and trace.text is not None:
                    per_point_opacity = [
                        0.9 if city_is_active(city, key_thr) else 0.25
                        for city in trace.text
                    ]
                    trace.marker.update(opacity=per_point_opacity)
                else:
                    trace.marker.update(opacity=0.9)

            
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
            # --------------------------------------------------
            # PRIMARY MODEL FAILED
            # --------------------------------------------------
            st.error(f"❌ Primary optimization failed: {e}")

            # In Gamification Mode we DO NOT run SC1F/SC2F_uns,
            # because they ignore the student's facility/mode choices.
            if mode == "Gamification Mode":
                st.warning(
                    "Fallback models are only defined for SC1F/SC2F. "
                    "In Gamification Mode, please adjust your facility / mode "
                    "selection or relax the CO₂ target and try again."
                )

            else:
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
                            print_results="NO",
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
                            print_results="NO",
                        )

                    # --------------------------------------------------
                    # SUCCESS DISPLAY (FALLBACK MODEL)
                    # --------------------------------------------------
                    st.success("Fallback optimization successful! ✅")

                    # ===================================================
                    # 📦 MAXIMUM SATISFIABLE DEMAND
                    # ===================================================
                    st.markdown("## 📦 Maximum Satisfiable Demand (Fallback Model)")

                    st.metric(
                        "Satisfied Demand (%)",
                        f"{results_uns['Satisfied_Demand_pct'] * 100:.2f}%"
                    )

                    st.metric(
                        "Satisfied Demand (Units)",
                        f"{results_uns['Satisfied_Demand_units']:,.0f}"
                    )

                    # ===================================================
                    # 💰 OBJECTIVE
                    # ===================================================
                    st.markdown("## 💰 Objective Value (Excluding Slack Penalty)")
                    st.metric(
                        "Objective (€)",
                        f"{results_uns['Objective_value']:,.2f}"
                    )

                    # ===================================================
                    # 🌍 MAP
                    # ===================================================
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

                    # Event overlays
                    event_nodes = []
                    if suez_flag:
                        event_nodes.append(
                            ("Event: Suez Canal Blockade", 30.59, 32.27, "Suez Canal Crisis")
                        )
                    if volcano_flag:
                        event_nodes.append(
                            ("Event: Volcano Eruption", 63.63, -19.62, "Volcanic Ash Zone")
                        )
                    if oil_flag:
                        event_nodes.append(
                            ("Event: Oil Crisis", 28.60, 47.80, "Oil Supply Shock")
                        )
                    if trade_flag:
                        event_nodes.append(
                            ("Event: Trade War", 55.00, 60.00, "Trade War Impact Zone")
                        )

                    if event_nodes:
                        df_events = pd.DataFrame(event_nodes, columns=["Type", "Lat", "Lon", "City"])
                        locations = pd.concat([locations, df_events], ignore_index=True)

                    color_map = {
                        "Plant": "purple",
                        "Cross-dock": "dodgerblue",
                        "DC": "black",
                        "Retail": "red",
                        "New Production Facility": "deepskyblue",
                        "Event: Suez Canal Blockade": "gold",
                        "Event: Volcano Eruption": "orange",
                        "Event: Oil Crisis": "brown",
                        "Event: Trade War": "green",
                    }

                    size_map = {
                        "Plant": 15,
                        "Cross-dock": 14,
                        "DC": 16,
                        "Retail": 20,
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

                    # ===================================================
                    # 🏭 PRODUCTION OUTBOUND PIE CHART
                    # ===================================================
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
                        textfont_size=13,
                    )

                    st.plotly_chart(fig_prod, use_container_width=True)
                    st.dataframe(df_prod.round(2), use_container_width=True)

                    # ===================================================
                    # 🚚 CROSS-DOCK OUTBOUND PIE CHART
                    # ===================================================
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
                            title="Cross-dock Outbound Share (Fallback Model)",
                        )

                        st.plotly_chart(fig_crossdock, use_container_width=True)
                        st.dataframe(df_crossdock.round(2), use_container_width=True)

                except Exception as e2:
                    st.error(f"❌ Fallback model also failed: {e2}")



