import os
import streamlit as st
import gurobipy as gp
import streamlit.components.v1 as components




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

    console.log("GA injected into TOP WINDOW → OK");

}})();
</script>
""", height=50)


# ================================================================
# 🧩 Safe Imports
# ================================================================
try:
    from Scenario_Setting_For_SC1F import run_scenario as run_SC1F
    from Scenario_Setting_For_SC2F import run_scenario as run_SC2F
except Exception as e:
    st.error(f"❌ Error importing optimization modules: {e}")

# ================================================================
# 🔐 Load Gurobi WLS credentials (from Streamlit secrets)
# ================================================================
for var in ["GRB_WLSACCESSID", "GRB_WLSSECRET", "GRB_LICENSEID"]:
    if var in st.secrets:
        os.environ[var] = st.secrets[var]

# ================================================================
# 🏷️ Layout
# ================================================================
st.set_page_config(page_title="Global Supply Chain Optimization", layout="centered")
st.title("🌍 Global Supply Chain Optimization (Gurobi)")

# ================================================================
# SESSION MODE TOGGLE
# ================================================================
mode = st.radio("Select mode:", ["Normal Mode", "Session Mode"])

if "session_step" not in st.session_state:
    st.session_state.session_step = 0

# ================================================================
# Scenario event definitions
# ================================================================
EVENTS = {
    "suez_canal": "🚢 Suez Canal is blocked due to a crisis.",
    "oil_crises": "⛽ Global oil prices surged due to a new oil crisis.",
    "volcano": "🌋 Volcano eruption blocks all air transportation.",
    "trade_war": "💼 Trade war increases sourcing tariffs.",
}


st.markdown("Enter any numeric value (≥ 0) for each parameter below, then run the optimization.")


components.html(f"""
<script>
(function() {{

    // If inside Streamlit iframe → inject GA into TOP window instead
    const targetDoc = window.parent.document;

    // Remove existing GA scripts (avoid duplicates)
    const old1 = targetDoc.getElementById("ga-tag");
    const old2 = targetDoc.getElementById("ga-src");
    if (old1) old1.remove();
    if (old2) old2.remove();

    // Create GA script (src)
    const s1 = targetDoc.createElement('script');
    s1.id = "ga-src";
    s1.async = true;
    s1.src = "https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}";
    targetDoc.head.appendChild(s1);

    // Create GA config script
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

    console.log("GA injected into TOP WINDOW → OK");

}})();
</script>
""", height=100)


# ================================================================
# 🧩 Model selection
# ================================================================
model_choice = st.selectbox(
    "Select optimization model:",
    ("SC1F – Existing Facilities Only", "SC2F – Allow New Facilities")
)

# ================================================================
# 🧠 Helper function for manual numeric input
# ================================================================
def positive_input(label, default):
    """Takes a text input, validates it as a non-negative float."""
    val_str = st.text_input(label, value=str(default))
    try:
        val = float(val_str)
        if val < 0:
            st.warning(f"{label} must be ≥ 0. Using 0 instead.")
            return 0.0
        return val
    except ValueError:
        st.warning(f"{label} must be numeric. Using default {default}.")
        return default

# ================================================================
# 🎛️ Parameters
# ================================================================
st.subheader("📊 Scenario Parameters")

co2_pct = positive_input("CO₂ Reduction Target (%)", 50.0) / 100.0
product_weight = positive_input("Product Weight (kg)", 2.58)

if "SC1F" in model_choice:
    st.subheader("⚙️ Parameters for SC1F (Existing Facilities)")
    co2_cost_per_ton = positive_input("CO₂ Cost per ton (€)", 37.50)

elif "SC2F" in model_choice:
    st.subheader("⚙️ Parameters for SC2F (Allows New Facilities)")
    co2_cost_per_ton_New = positive_input("CO₂ Cost per ton (New Facilities) (€)", 60.00)



# ================================================================
# SESSION MODE EVENT POPUP LOGIC
# ================================================================
import random

def generate_tariff_rate():
    k = random.uniform(1, 2)   # Float between 1 and 2
    x_pct = ((k - 1) / k) * 100
    return k, x_pct


# ================================================================
# SESSION MODE EVENT POPUP LOGIC (ONE RANDOM EVENT EACH STEP)
# ================================================================
selected_event = None
tariff_rate_random = 1.0
tariff_x_pct = 0.0

if mode == "Session Mode":

    st.subheader("🎮 Scenario-Based Session")

    # Initialize event list only once
    if "remaining_events" not in st.session_state:
        st.session_state.remaining_events = list(EVENTS.keys())

    if st.button("Start / Continue Session"):

        # If finished all events
        if len(st.session_state.remaining_events) == 0:
            st.success("🎉 All scenarios have now been tested! Session complete.")
        else:
            # Choose 1 event at random and remove it
            chosen = random.choice(st.session_state.remaining_events)
            st.session_state.remaining_events.remove(chosen)
            st.session_state.active_event = chosen

            # Special handling for trade war (random tariff_rate)
            if chosen == "trade_war":
                k, x_pct = generate_tariff_rate()
                st.session_state.tariff_rate_random = k
                st.session_state.tariff_x_pct = x_pct

    # Display event (if exists)
    if "active_event" in st.session_state:
        e = st.session_state.active_event
        st.subheader("⚠️ Active Event")
        st.warning(EVENTS[e])

        if e == "trade_war":
            st.info(f"Tariffs are now **{st.session_state.tariff_x_pct:.1f}%** more.")

        st.write("👉 Comment below: What would be the optimal choice?")
        st.text_area("Your comment:")

    # Map event flag
    suez_flag = (st.session_state.get("active_event") == "suez_canal")
    oil_flag = (st.session_state.get("active_event") == "oil_crises")
    volcano_flag = (st.session_state.get("active_event") == "volcano")
    trade_flag = (st.session_state.get("active_event") == "trade_war")
    tariff_rate_used = st.session_state.get("tariff_rate_random", 1.0)

else:
    # Normal mode
    suez_flag = oil_flag = volcano_flag = trade_flag = False
    tariff_rate_used = 1.0



# ================================================================
# ▶️ Run Optimization
# ================================================================


if st.button("Run Optimization"):
    with st.spinner("Running Gurobi optimization... Please wait ⏳"):
        try:
            if "SC1F" in model_choice:
                results, model = run_SC1F(
                    CO_2_percentage=co2_pct,
                    product_weight=product_weight,
                    co2_cost_per_ton=co2_cost_per_ton,
                    print_results="NO",
                    suez_canal=suez_flag,
                    oil_crises=oil_flag,
                    volcano=volcano_flag,
                    trade_war=trade_flag,
                    tariff_rate=tariff_rate_used
                )
            else:
                results, model = run_SC2F(
                    CO_2_percentage=co2_pct,
                    product_weight=product_weight,
                    co2_cost_per_ton_New=co2_cost_per_ton_New,
                    print_results="NO",
                    suez_canal=suez_flag,
                    oil_crises=oil_flag,
                    volcano=volcano_flag,
                    trade_war=trade_flag,
                    tariff_rate=tariff_rate_used
                )


            st.success("Optimization completed successfully ✅")

            # Results
            st.subheader("💰 Objective Value")
            st.metric("Total Cost (€)", f"{results['Objective_value']:,.2f}")

            st.subheader("🌿 CO₂ Emissions Breakdown (tons)")
            st.json({
                "Air": round(results.get("E_air", 0), 2),
                "Sea": round(results.get("E_sea", 0), 2),
                "Road": round(results.get("E_road", 0), 2),
                "Last-mile": round(results.get("E_lastmile", 0), 2),
                "Production": round(results.get("E_production", 0), 2),
                "Total": round(results.get("CO2_Total", 0), 2),
            })
            
            # ================================================================
            # 🌍 GLOBAL SUPPLY CHAIN NETWORK MAP (copied from SC2 dashboard)
            # ================================================================
            import plotly.express as px
            import pandas as pd
            
            st.markdown("## 🌍 Global Supply Chain Structure")
            
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
                "Lat": [47.50, 48.14, 46.95, 45.46],
                "Lon": [19.04, 11.58, 7.44, 9.19]
            })
            
            # --- Retailer Hubs (f3) ---
            retailers = pd.DataFrame({
                "Type": ["Retailer Hub"] * 7,
                "Lat": [55.67, 53.35, 51.50, 49.82, 45.76, 43.30, 40.42],
                "Lon": [12.57, -6.26, -0.12, 19.08, 4.83, 5.37, -3.70]
            })
            
            # --- Detect new facilities from f2_2_bin variables ---
            facility_coords = {
                "HUDTG": (49.61, 6.13),
                "CZMCT": (44.83, 20.42),
                "IEILG": (47.09, 16.37),
                "FIMPF": (50.45, 14.50),
                "PLZCA": (42.70, 12.65)
            }
            
            active_facilities = []
            
            for var in model.getVars():
                if var.VarName.startswith("f2_2_bin") and var.X > 0.5:
                    # extract name inside brackets
                    name = var.VarName[var.VarName.find("[")+1 : var.VarName.find("]")]
                    if name in facility_coords:
                        lat, lon = facility_coords[name]
                        active_facilities.append((name, lat, lon))
            
            if active_facilities:
                new_facilities = pd.DataFrame({
                    "Type": "New Production Facility",
                    "Lat": [lat for _, lat, _ in active_facilities],
                    "Lon": [lon for _, _, lon in active_facilities],
                    "Name": [name for name, _, _ in active_facilities]
                })
            else:
                new_facilities = pd.DataFrame(columns=["Type", "Lat", "Lon", "Name"])
            
            # --- Combine all locations ---
            locations = pd.concat([plants, crossdocks, dcs, retailers, new_facilities])
            
            # --- Color and size mapping ---
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
            
            # --- Build map ---
            fig_map = px.scatter_geo(
                locations,
                lat="Lat",
                lon="Lon",
                color="Type",
                color_discrete_map=color_map,
                projection="natural earth",
                scope="world",
                title="Global Supply Chain Structure"
            )
            
            # Customize
            for trace in fig_map.data:
                trace.marker.update(size=size_map[trace.name], opacity=0.9, line=dict(width=0.5, color='white'))
            
            fig_map.update_geos(
                showcountries=True,
                countrycolor="lightgray",
                showland=True,
                landcolor="rgb(245,245,245)",
                fitbounds="locations"
            )
            fig_map.update_layout(height=550, margin=dict(l=0, r=0, t=40, b=0))
            
            st.plotly_chart(fig_map, use_container_width=True)
            
            # Optional legend
            st.markdown("""
            **Legend:**
            - 🏗️ **Cross-dock**  
            - 🏬 **Distribution Centre**  
            - 🔴 **Retailer Hub**  
            - ⚙️ **New Production Facility**  
            - 🏭 **Plant**
            """)


        except gp.GurobiError as ge:
            st.error(f"Gurobi Error {ge.errno}: {ge.message}")
        except Exception as e:
            st.error(f"❌ This solution was never feasible — even Swiss precision couldn't optimize it! 🇨🇭\n\n{e}")
