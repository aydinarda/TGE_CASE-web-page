# -*- coding: utf-8 -*-
"""
Multi-Layer Supply Chain Optimization with Interactive Map Selection
Includes map-based location selection and parametric modes for all layers
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import random
from streamlit import components

# Import the parametric master model
from MASTER import run_scenario_master

# ================================================================
# PAGE CONFIGURATION
# ================================================================
st.set_page_config(
    page_title="Supply Chain Optimization",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================================================================
# LOCATION DATA WITH COORDINATES FOR MAP
# ================================================================
LOCATION_COORDS = {
    # Plants (Layer 1 - Source)
    "TW": {"name": "Taiwan Plant", "lat": 25.0330, "lon": 121.5654, "type": "plant", "layer": 1},
    "SHA": {"name": "Shanghai Plant", "lat": 31.2304, "lon": 121.4737, "type": "plant", "layer": 1},
    
    # Crossdocks (Layer 2)
    "ATVIE": {"name": "Vienna Crossdock", "lat": 48.2082, "lon": 16.3738, "type": "crossdock", "layer": 2},
    "PLGDN": {"name": "Gdańsk Crossdock", "lat": 54.3900, "lon": 18.6453, "type": "crossdock", "layer": 2},
    "FRCDG": {"name": "Friedrichshafen Crossdock", "lat": 47.6560, "lon": 9.1759, "type": "crossdock", "layer": 2},
    
    # Distribution Centers (Layer 3)
    "PED": {"name": "Pécs DC", "lat": 46.0727, "lon": 18.2315, "type": "dc", "layer": 3},
    "FR6216": {"name": "Frankfurt DC", "lat": 50.1109, "lon": 8.6821, "type": "dc", "layer": 3},
    "RIX": {"name": "Riga DC", "lat": 56.9496, "lon": 24.1052, "type": "dc", "layer": 3},
    "GMZ": {"name": "Graz DC", "lat": 47.0707, "lon": 15.4395, "type": "dc", "layer": 3},
    
    # Retailers (Layer 4 - Demand)
    "FLUXC": {"name": "FLUXC Retail", "lat": 52.5200, "lon": 13.4050, "type": "retailer", "layer": 4},
    "ALKFM": {"name": "ALKFM Retail", "lat": 48.8566, "lon": 2.3522, "type": "retailer", "layer": 4},
    "KSJER": {"name": "KSJER Retail", "lat": 50.0755, "lon": 14.4378, "type": "retailer", "layer": 4},
    "GXEQH": {"name": "GXEQH Retail", "lat": 47.5162, "lon": 19.0402, "type": "retailer", "layer": 4},
    "OAHLE": {"name": "OAHLE Retail", "lat": 59.9139, "lon": 10.7522, "type": "retailer", "layer": 4},
    "ISNQE": {"name": "ISNQE Retail", "lat": 54.9973, "lon": 57.5186, "type": "retailer", "layer": 4},
    "NAAVF": {"name": "NAAVF Retail", "lat": 55.7558, "lon": 37.6173, "type": "retailer", "layer": 4},
    
    # New Locations (Layer 5)
    "HUDTG": {"name": "Luxembourg New Hub", "lat": 49.6116, "lon": 6.1319, "type": "new", "layer": 5},
    "CZMCT": {"name": "Belgrade New Hub", "lat": 44.8176, "lon": 20.4633, "type": "new", "layer": 5},
    "IEILG": {"name": "Graz New Hub", "lat": 47.0707, "lon": 15.4395, "type": "new", "layer": 5},
    "FIMPF": {"name": "Prague New Hub", "lat": 50.0755, "lon": 14.4378, "type": "new", "layer": 5},
    "PLZCA": {"name": "Viterbo New Hub", "lat": 42.4305, "lon": 12.1067, "type": "new", "layer": 5},
}

# All available options
ALL_PLANTS = ["TW", "SHA"]
ALL_CROSSDOCKS = ["ATVIE", "PLGDN", "FRCDG"]
ALL_DCS = ["PED", "FR6216", "RIX", "GMZ"]
ALL_RETAILERS = ["FLUXC", "ALKFM", "KSJER", "GXEQH", "OAHLE", "ISNQE", "NAAVF"]
ALL_NEW_LOCS = ["HUDTG", "CZMCT", "IEILG", "FIMPF", "PLZCA"]
ALL_MODES_L1 = ["air", "sea"]
ALL_MODES_L2 = ["air", "sea", "road"]
ALL_MODES_L3 = ["air", "sea", "road"]

# ================================================================
# HELPER FUNCTIONS
# ================================================================

def create_interactive_map(locations_to_show, title="Supply Chain Network Map"):
    """
    Create interactive Plotly map with selectable location markers
    Returns the figure and allows click-based selection
    """
    if not locations_to_show:
        st.warning("No locations to display")
        return None
    
    # Prepare data
    map_data = []
    for loc_code in locations_to_show:
        if loc_code in LOCATION_COORDS:
            loc = LOCATION_COORDS[loc_code]
            map_data.append({
                "code": loc_code,
                "name": loc["name"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "type": loc["type"]
            })
    
    df_map = pd.DataFrame(map_data)
    
    if df_map.empty:
        return None
    
    # Color scheme
    color_map = {
        "plant": "#E74C3C",        # Red
        "crossdock": "#3498DB",    # Blue
        "dc": "#2ECC71",           # Green
        "retailer": "#F39C12",     # Orange
        "new": "#9B59B6"           # Purple
    }
    
    # Create figure
    fig = go.Figure()
    
    # Add traces for each location type
    for loc_type in ["plant", "crossdock", "dc", "retailer", "new"]:
        df_type = df_map[df_map["type"] == loc_type]
        if len(df_type) > 0:
            fig.add_trace(go.Scattergeo(
                lon=df_type["lon"],
                lat=df_type["lat"],
                mode="markers+text",
                text=df_type["code"],
                textposition="top center",
                textfont=dict(size=10, color="black"),
                marker=dict(
                    size=18,
                    color=color_map.get(loc_type, "#95A5A6"),
                    opacity=0.85,
                    line=dict(width=2, color="white"),
                    symbol="circle"
                ),
                name=loc_type.replace("_", " ").title(),
                hovertemplate="<b>%{customdata[0]}</b><br>" +
                            "Name: %{customdata[1]}<br>" +
                            "Lat: %{lat:.4f}<br>Lon: %{lon:.4f}<extra></extra>",
                customdata=df_type[["code", "name"]].values,
                showlegend=True
            ))
    
    # Update layout
    fig.update_layout(
        title=title,
        geo=dict(
            scope="europe",
            projection_type="natural earth",
            showland=True,
            landcolor="rgb(240, 240, 240)",
            coastcolor="rgb(180, 180, 180)",
            countrycolor="rgb(200, 200, 200)",
            showlakes=True,
            lakecolor="rgb(220, 240, 255)",
            showocean=True,
            oceancolor="rgb(240, 250, 255)",
            resolution=50
        ),
        height=500,
        hovermode="closest",
        margin=dict(l=0, r=0, t=40, b=0)
    )
    
    return fig

def positive_input(label, default=100, key=None):
    """Helper for numeric inputs"""
    return st.number_input(label, value=default, min_value=0.0, step=10.0, key=key)

def display_layer_summary(layer_num, source_locs, target_locs, modes):
    """Display a summary of layer configuration"""
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.write(f"**Sources ({len(source_locs)}):**")
        for loc in source_locs[:3]:
            st.caption(f"🔴 {LOCATION_COORDS.get(loc, {}).get('name', loc)}")
        if len(source_locs) > 3:
            st.caption(f"... +{len(source_locs)-3} more")
    
    with col2:
        st.write(f"**Targets ({len(target_locs)}):**")
        for loc in target_locs[:3]:
            st.caption(f"🟢 {LOCATION_COORDS.get(loc, {}).get('name', loc)}")
        if len(target_locs) > 3:
            st.caption(f"... +{len(target_locs)-3} more")
    
    with col3:
        st.write(f"**Modes ({len(modes)}):**")
        for mode in modes:
            if mode == "air":
                st.caption(f"✈️ {mode}")
            elif mode == "sea":
                st.caption(f"🚢 {mode}")
            else:
                st.caption(f"🚚 {mode}")

# ================================================================
# MAIN APPLICATION
# ================================================================

st.title("🌍 Multi-Layer Supply Chain Optimizer")
st.markdown("**Interactive map-based location selection with parametric modes for each layer**")

# Initialize session state
if "selected_plants" not in st.session_state:
    st.session_state.selected_plants = ALL_PLANTS.copy()
if "selected_crossdocks" not in st.session_state:
    st.session_state.selected_crossdocks = ALL_CROSSDOCKS.copy()
if "selected_dcs" not in st.session_state:
    st.session_state.selected_dcs = ALL_DCS.copy()
if "selected_retailers" not in st.session_state:
    st.session_state.selected_retailers = ALL_RETAILERS.copy()
if "selected_new_locs" not in st.session_state:
    st.session_state.selected_new_locs = []
if "selected_modes_l1" not in st.session_state:
    st.session_state.selected_modes_l1 = ALL_MODES_L1.copy()
if "selected_modes_l2" not in st.session_state:
    st.session_state.selected_modes_l2 = ALL_MODES_L2.copy()
if "selected_modes_l3" not in st.session_state:
    st.session_state.selected_modes_l3 = ALL_MODES_L3.copy()

# Sidebar mode selection
st.sidebar.title("📋 Navigation")
page_mode = st.sidebar.radio(
    "Select Page:",
    ["🏠 Home", "📊 Optimization", "🎮 Guessing Game"],
    key="page_mode"
)

# ================================================================
# HOME PAGE
# ================================================================

if page_mode == "🏠 Home":
    st.header("Welcome to Multi-Layer Supply Chain Optimization")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Optimization Mode")
        st.write("""
        - Select locations and modes for each distribution layer
        - View interactive world maps with all facilities
        - Run Gurobi optimization across all layers
        - Analyze costs, emissions, and demand fulfillment
        """)
        if st.button("Go to Optimization →", key="btn_opt", use_container_width=True):
            st.session_state.page_mode = "📊 Optimization"
            st.rerun()
    
    with col2:
        st.subheader("🎮 Guessing Game")
        st.write("""
        - Make educated guesses for each layer
        - Test your supply chain intuition
        - Compare against optimal solutions
        - Learn how optimization improves performance
        """)
        if st.button("Go to Guessing Game →", key="btn_guess", use_container_width=True):
            st.session_state.page_mode = "🎮 Guessing Game"
            st.rerun()
    
    st.markdown("---")
    st.info("""
    **Layer Structure:**
    - **Layer 1**: Plants → Crossdocks (Int'l modes: air, sea)
    - **Layer 2**: Crossdocks → Distribution Centers (modes: air, sea, road)
    - **Layer 3**: DCs → Retailers (modes: air, sea, road)
    
    Each layer has independent mode selection for flexible optimization!
    """)

# ================================================================
# OPTIMIZATION PAGE
# ================================================================

elif page_mode == "📊 Optimization":
    st.header("⚙️ Multi-Layer Scenario Optimization")
    
    # Create tabs for each layer + parameters + results
    tab_l1, tab_l2, tab_l3, tab_params, tab_results = st.tabs([
        "🏭 Layer 1: Plants→Crossdocks",
        "📦 Layer 2: Crossdocks→DCs",
        "🛍️ Layer 3: DCs→Retailers",
        "⚙️ Parameters",
        "📊 Results"
    ])
    
    # ========== LAYER 1 TAB ==========
    with tab_l1:
        st.subheader("Layer 1: Plants to Crossdocks (International Transport)")
        st.markdown("*Select plants as production sources and crossdocks as consolidation points*")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write("### Interactive Map")
            l1_locs = st.session_state.selected_plants + st.session_state.selected_crossdocks
            fig_l1 = create_interactive_map(l1_locs, "Layer 1: Plants & Crossdocks")
            if fig_l1:
                st.plotly_chart(fig_l1, use_container_width=True)
        
        with col2:
            st.write("### Configure Layer 1")
            
            st.markdown("**Plants:**")
            new_plants = st.multiselect(
                "Select Plants",
                ALL_PLANTS,
                default=st.session_state.selected_plants,
                key="opt_l1_plants",
                help="Choose production sources"
            )
            st.session_state.selected_plants = new_plants
            
            st.markdown("**Crossdocks:**")
            new_cds = st.multiselect(
                "Select Crossdocks",
                ALL_CROSSDOCKS,
                default=st.session_state.selected_crossdocks,
                key="opt_l1_crossdocks",
                help="Choose consolidation points"
            )
            st.session_state.selected_crossdocks = new_cds
            
            st.markdown("**Transport Modes (Layer 1):**")
            new_modes_l1 = st.multiselect(
                "Modes for Layer 1",
                ALL_MODES_L1,
                default=st.session_state.selected_modes_l1,
                key="opt_l1_modes",
                help="Air or Sea for international transport"
            )
            st.session_state.selected_modes_l1 = new_modes_l1
        
        display_layer_summary(1, st.session_state.selected_plants, 
                            st.session_state.selected_crossdocks, 
                            st.session_state.selected_modes_l1)
    
    # ========== LAYER 2 TAB ==========
    with tab_l2:
        st.subheader("Layer 2: Crossdocks to Distribution Centers")
        st.markdown("*Choose how goods move from consolidation to regional distribution*")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write("### Interactive Map")
            l2_locs = st.session_state.selected_crossdocks + st.session_state.selected_dcs
            fig_l2 = create_interactive_map(l2_locs, "Layer 2: Crossdocks & DCs")
            if fig_l2:
                st.plotly_chart(fig_l2, use_container_width=True)
        
        with col2:
            st.write("### Configure Layer 2")
            
            st.markdown("**Distribution Centers:**")
            new_dcs = st.multiselect(
                "Select DCs",
                ALL_DCS,
                default=st.session_state.selected_dcs,
                key="opt_l2_dcs",
                help="Regional distribution hubs"
            )
            st.session_state.selected_dcs = new_dcs
            
            st.markdown("**Transport Modes (Layer 2):**")
            new_modes_l2 = st.multiselect(
                "Modes for Layer 2",
                ALL_MODES_L2,
                default=st.session_state.selected_modes_l2,
                key="opt_l2_modes",
                help="Air, Sea, or Road for regional distribution"
            )
            st.session_state.selected_modes_l2 = new_modes_l2
        
        display_layer_summary(2, st.session_state.selected_crossdocks, 
                            st.session_state.selected_dcs, 
                            st.session_state.selected_modes_l2)
    
    # ========== LAYER 3 TAB ==========
    with tab_l3:
        st.subheader("Layer 3: Distribution Centers to Retailers")
        st.markdown("*Configure final-mile delivery to end retailers*")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write("### Interactive Map")
            l3_locs = st.session_state.selected_dcs + st.session_state.selected_retailers
            fig_l3 = create_interactive_map(l3_locs, "Layer 3: DCs & Retailers")
            if fig_l3:
                st.plotly_chart(fig_l3, use_container_width=True)
        
        with col2:
            st.write("### Configure Layer 3")
            
            st.markdown("**Retailers (Demand Points):**")
            new_retailers = st.multiselect(
                "Select Retailers",
                ALL_RETAILERS,
                default=st.session_state.selected_retailers,
                key="opt_l3_retailers",
                help="End markets to serve"
            )
            st.session_state.selected_retailers = new_retailers
            
            st.markdown("**Transport Modes (Layer 3):**")
            new_modes_l3 = st.multiselect(
                "Modes for Layer 3",
                ALL_MODES_L3,
                default=st.session_state.selected_modes_l3,
                key="opt_l3_modes",
                help="Air, Sea, or Road for final delivery"
            )
            st.session_state.selected_modes_l3 = new_modes_l3
            
            st.markdown("**New Facilities:**")
            new_new_locs = st.multiselect(
                "Consider New Locations",
                ALL_NEW_LOCS,
                default=st.session_state.selected_new_locs,
                key="opt_new_locs",
                help="Optional expansion opportunities"
            )
            st.session_state.selected_new_locs = new_new_locs
        
        display_layer_summary(3, st.session_state.selected_dcs, 
                            st.session_state.selected_retailers, 
                            st.session_state.selected_modes_l3)
    
    # ========== PARAMETERS TAB ==========
    with tab_params:
        st.subheader("⚙️ Optimization Parameters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            co2_pct = st.slider("CO₂ Reduction Target (%)", 0, 100, 50, key="opt_co2_pct")
            service_level = st.slider("Service Level", 0.7, 0.99, 0.9, step=0.01, key="opt_svc_level")
        
        with col2:
            model_choice = st.selectbox(
                "Model Type",
                ["SC1F - Existing Facilities", "SC2F - Allow New Facilities"],
                key="opt_model"
            )
            tariff_rate = st.slider("Tariff Rate", 1.0, 2.0, 1.0, step=0.05, key="opt_tariff")
        
        st.markdown("---")
        
        # Run button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 RUN OPTIMIZATION", use_container_width=True, key="opt_run"):
                with st.spinner("⏳ Optimizing multi-layer network..."):
                    try:
                        results = run_scenario_master(
                            use_new_locations=("SC2F" in model_choice),
                            allow_unmet_demand=True,
                            selected_plants=st.session_state.selected_plants if st.session_state.selected_plants else ALL_PLANTS,
                            selected_crossdocks=st.session_state.selected_crossdocks if st.session_state.selected_crossdocks else ALL_CROSSDOCKS,
                            selected_dcs=st.session_state.selected_dcs if st.session_state.selected_dcs else ALL_DCS,
                            selected_retailers=st.session_state.selected_retailers if st.session_state.selected_retailers else ALL_RETAILERS,
                            selected_new_locs=st.session_state.selected_new_locs,
                            selected_modes=st.session_state.selected_modes_l2 + st.session_state.selected_modes_l3,
                            selected_modes_l1=st.session_state.selected_modes_l1,
                            selected_modes_l2=st.session_state.selected_modes_l2,
                            selected_modes_l3=st.session_state.selected_modes_l3,
                            CO_2_percentage=co2_pct / 100.0,
                            service_level=service_level,
                            tariff_rate=tariff_rate
                        )
                        st.session_state.optimization_results = results
                        st.success("✅ Optimization complete!")
                        st.balloons()
                        
                    except Exception as e:
                        st.error(f"❌ Optimization failed: {str(e)}")
    
    # ========== RESULTS TAB ==========
    with tab_results:
        if "optimization_results" in st.session_state:
            results = st.session_state.optimization_results
            
            st.subheader("📊 Results Summary")
            
            # KPI Row
            kpi_cols = st.columns(4)
            with kpi_cols[0]:
                total_cost = results.get("Total_Cost_€", 0)
                st.metric("💰 Total Cost", f"€{total_cost:,.0f}")
            with kpi_cols[1]:
                co2_total = results.get("CO2_Total", 0)
                st.metric("🌱 Total CO₂", f"{co2_total:,.0f} kg")
            with kpi_cols[2]:
                demand_met = results.get("Demand_Fulfillment_Rate", 0)
                st.metric("📦 Demand Met", f"{demand_met:.1f}%")
            with kpi_cols[3]:
                new_facs = len([k for k in results.keys() if "New_Facility" in k and results[k]])
                st.metric("🌟 New Facilities", f"{new_facs}")
            
            st.markdown("---")
            
            # Complete Network Map
            all_locs = (st.session_state.selected_plants + 
                       st.session_state.selected_crossdocks + 
                       st.session_state.selected_dcs + 
                       st.session_state.selected_retailers)
            
            st.write("### Complete Supply Chain Network")
            fig_complete = create_interactive_map(all_locs, "Full Network Visualization")
            if fig_complete:
                st.plotly_chart(fig_complete, use_container_width=True)
            
            st.markdown("---")
            
            # Detailed results
            st.write("### Detailed Configuration")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**Layer 1 - International**")
                st.write(f"Mode 1: {', '.join(st.session_state.selected_modes_l1)}")
                st.write(f"Plants: {len(st.session_state.selected_plants)}")
                st.write(f"Crossdocks: {len(st.session_state.selected_crossdocks)}")
            
            with col2:
                st.write("**Layer 2 - Regional**")
                st.write(f"Modes: {', '.join(st.session_state.selected_modes_l2)}")
                st.write(f"From Crossdocks: {len(st.session_state.selected_crossdocks)}")
                st.write(f"To DCs: {len(st.session_state.selected_dcs)}")
            
            with col3:
                st.write("**Layer 3 - Final-Mile**")
                st.write(f"Modes: {', '.join(st.session_state.selected_modes_l3)}")
                st.write(f"From DCs: {len(st.session_state.selected_dcs)}")
                st.write(f"To Retailers: {len(st.session_state.selected_retailers)}")
        
        else:
            st.info("👈 Run optimization from the Parameters tab to see results!")

# ================================================================
# GUESSING GAME PAGE
# ================================================================

elif page_mode == "🎮 Guessing Game":
    st.header("🎮 Supply Chain Configuration Guessing Game")
    st.markdown("**Make your best guesses for each layer and compare with optimal results!**")
    
    # Create tabs for each layer
    tab_g1, tab_g2, tab_g3, tab_g_params, tab_g_results = st.tabs([
        "🏭 Layer 1 Guess",
        "📦 Layer 2 Guess",
        "🛍️ Layer 3 Guess",
        "⚙️ Your Guesses",
        "🏆 Results"
    ])
    
    # Initialize guess session state
    if "guess_plants" not in st.session_state:
        st.session_state.guess_plants = [ALL_PLANTS[0]]
    if "guess_crossdocks" not in st.session_state:
        st.session_state.guess_crossdocks = [ALL_CROSSDOCKS[0]]
    if "guess_modes_l1" not in st.session_state:
        st.session_state.guess_modes_l1 = ["sea"]
    if "guess_dcs" not in st.session_state:
        st.session_state.guess_dcs = [ALL_DCS[0]]
    if "guess_modes_l2" not in st.session_state:
        st.session_state.guess_modes_l2 = ["road"]
    if "guess_retailers" not in st.session_state:
        st.session_state.guess_retailers = [ALL_RETAILERS[0]]
    if "guess_modes_l3" not in st.session_state:
        st.session_state.guess_modes_l3 = ["road"]
    
    # ========== GUESSING LAYER 1 ==========
    with tab_g1:
        st.subheader("Your Layer 1 Configuration Guess")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            l1_locs = st.session_state.guess_plants + st.session_state.guess_crossdocks
            fig_g1 = create_interactive_map(l1_locs, "Your Layer 1 Guess")
            if fig_g1:
                st.plotly_chart(fig_g1, use_container_width=True)
        
        with col2:
            st.markdown("**Your Guess:**")
            st.session_state.guess_plants = st.multiselect(
                "Which Plants?",
                ALL_PLANTS,
                default=st.session_state.guess_plants,
                key="guess_l1_plants"
            )
            st.session_state.guess_crossdocks = st.multiselect(
                "Which Crossdocks?",
                ALL_CROSSDOCKS,
                default=st.session_state.guess_crossdocks,
                key="guess_l1_cds"
            )
            st.session_state.guess_modes_l1 = st.multiselect(
                "Which Modes (L1)?",
                ALL_MODES_L1,
                default=st.session_state.guess_modes_l1,
                key="guess_l1_modes"
            )
    
    # ========== GUESSING LAYER 2 ==========
    with tab_g2:
        st.subheader("Your Layer 2 Configuration Guess")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            l2_locs = st.session_state.guess_crossdocks + st.session_state.guess_dcs
            fig_g2 = create_interactive_map(l2_locs, "Your Layer 2 Guess")
            if fig_g2:
                st.plotly_chart(fig_g2, use_container_width=True)
        
        with col2:
            st.markdown("**Your Guess:**")
            st.session_state.guess_dcs = st.multiselect(
                "Which DCs?",
                ALL_DCS,
                default=st.session_state.guess_dcs,
                key="guess_l2_dcs"
            )
            st.session_state.guess_modes_l2 = st.multiselect(
                "Which Modes (L2)?",
                ALL_MODES_L2,
                default=st.session_state.guess_modes_l2,
                key="guess_l2_modes"
            )
    
    # ========== GUESSING LAYER 3 ==========
    with tab_g3:
        st.subheader("Your Layer 3 Configuration Guess")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            l3_locs = st.session_state.guess_dcs + st.session_state.guess_retailers
            fig_g3 = create_interactive_map(l3_locs, "Your Layer 3 Guess")
            if fig_g3:
                st.plotly_chart(fig_g3, use_container_width=True)
        
        with col2:
            st.markdown("**Your Guess:**")
            st.session_state.guess_retailers = st.multiselect(
                "Which Retailers?",
                ALL_RETAILERS,
                default=st.session_state.guess_retailers,
                key="guess_l3_retail"
            )
            st.session_state.guess_modes_l3 = st.multiselect(
                "Which Modes (L3)?",
                ALL_MODES_L3,
                default=st.session_state.guess_modes_l3,
                key="guess_l3_modes"
            )
    
    # ========== GUESSING PARAMETERS ==========
    with tab_g_params:
        st.subheader("⚙️ Your Parameter Guesses")
        
        col1, col2 = st.columns(2)
        
        with col1:
            guess_co2_pct = st.slider("CO₂ Target (%)", 0, 100, 50, key="guess_co2_pct")
        with col2:
            guess_svc_level = st.slider("Service Level", 0.7, 0.99, 0.9, step=0.01, key="guess_svc_level")
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📤 SUBMIT YOUR GUESSES", use_container_width=True, key="guess_submit"):
                with st.spinner("Evaluating your guesses..."):
                    try:
                        # Your guess results
                        guess_results = run_scenario_master(
                            selected_plants=st.session_state.guess_plants or ALL_PLANTS,
                            selected_crossdocks=st.session_state.guess_crossdocks or ALL_CROSSDOCKS,
                            selected_dcs=st.session_state.guess_dcs or ALL_DCS,
                            selected_retailers=st.session_state.guess_retailers or ALL_RETAILERS,
                            selected_modes_l1=st.session_state.guess_modes_l1 or ALL_MODES_L1,
                            selected_modes_l2=st.session_state.guess_modes_l2 or ALL_MODES_L2,
                            selected_modes_l3=st.session_state.guess_modes_l3 or ALL_MODES_L3,
                            CO_2_percentage=guess_co2_pct / 100.0,
                            service_level=guess_svc_level
                        )
                        
                        # Optimal results (all options)
                        optimal_results = run_scenario_master(
                            selected_plants=ALL_PLANTS,
                            selected_crossdocks=ALL_CROSSDOCKS,
                            selected_dcs=ALL_DCS,
                            selected_retailers=ALL_RETAILERS,
                            selected_modes_l1=ALL_MODES_L1,
                            selected_modes_l2=ALL_MODES_L2,
                            selected_modes_l3=ALL_MODES_L3,
                            CO_2_percentage=0.5,
                            service_level=0.9
                        )
                        
                        st.session_state.guess_results = guess_results
                        st.session_state.optimal_results = optimal_results
                        st.success("✅ Results ready!")
                        st.balloons()
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
    
    # ========== GUESSING RESULTS ==========
    with tab_g_results:
        if "guess_results" in st.session_state and "optimal_results" in st.session_state:
            guess_res = st.session_state.guess_results
            optimal_res = st.session_state.optimal_results
            
            st.subheader("🏆 Comparison Results")
            
            # KPI Comparison
            kpi_data = pd.DataFrame({
                "Metric": ["Total Cost €", "CO2 Emissions kg", "Demand Fulfillment %"],
                "Your Guess": [
                    guess_res.get("Total_Cost_€", 0),
                    guess_res.get("CO2_Total", 0),
                    guess_res.get("Demand_Fulfillment_Rate", 100)
                ],
                "Optimal": [
                    optimal_res.get("Total_Cost_€", 0),
                    optimal_res.get("CO2_Total", 0),
                    optimal_res.get("Demand_Fulfillment_Rate", 100)
                ]
            })
            
            st.dataframe(kpi_data, use_container_width=True)
            
            # Scoring
            cost_diff = abs(kpi_data.iloc[0]["Your Guess"] - kpi_data.iloc[0]["Optimal"])
            cost_pct = (cost_diff / max(kpi_data.iloc[0]["Optimal"], 1)) * 100
            cost_score = max(0, 100 - cost_pct)
            
            co2_diff = abs(kpi_data.iloc[1]["Your Guess"] - kpi_data.iloc[1]["Optimal"])
            co2_pct = (co2_diff / max(kpi_data.iloc[1]["Optimal"], 1)) * 100
            co2_score = max(0, 100 - co2_pct)
            
            overall_score = (cost_score + co2_score) / 2
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("💰 Cost Accuracy", f"{cost_score:.1f}%")
            with col2:
                st.metric("🌱 CO₂ Accuracy", f"{co2_score:.1f}%")
            with col3:
                st.metric("🏆 Overall Score", f"{overall_score:.1f}%")
            
            if overall_score >= 90:
                st.success("🌟 Outstanding! Expert-level supply chain insight!")
            elif overall_score >= 75:
                st.info("👍 Excellent! You understand the optimization well!")
            elif overall_score >= 60:
                st.info("📚 Good! You're on the right track.")
            elif overall_score >= 40:
                st.warning("📖 Keep learning! Study layer interactions.")
            else:
                st.info("🎓 Great opportunity to learn about supply chain optimization!")
        
        else:
            st.info("👈 Submit your guesses to see the results!")
