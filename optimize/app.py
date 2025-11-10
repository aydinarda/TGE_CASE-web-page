import os
import streamlit as st
import gurobipy as gp
from SC1F import run_scenario as run_SC1F
from SC2F import run_scenario as run_SC2F

# ================================================================
# 🔐 Load Gurobi WLS credentials securely (from Streamlit secrets)
# ================================================================
for var in ["GRB_WLSACCESSID", "GRB_WLSSECRET", "GRB_LICENSEID"]:
    if var in st.secrets:
        os.environ[var] = st.secrets[var]

# ================================================================
# 🏷️ App layout
# ================================================================
st.set_page_config(page_title="Global Supply Chain Optimization", layout="centered")
st.title("🌍 Global Supply Chain Optimization (Gurobi)")

st.markdown("""
Use this web interface to run optimization scenarios with or without allowing new facility openings.
""")

# ================================================================
# 🧩 Model selection
# ================================================================
model_choice = st.selectbox(
    "Select optimization model:",
    (
        "SC1F – Existing Facilities Only",
        "SC2F – Allow New Facilities",
    )
)

# ================================================================
# 🎛️ Common parameters
# ================================================================
st.subheader("📊 Scenario Parameters")

co2_pct = st.number_input(
    "CO₂ Reduction Target (%)",
    min_value=0.0, max_value=100.0, value=50.0, step=1.0,
    help="Target percentage reduction in CO₂ emissions relative to baseline"
) / 100.0

product_weight = st.number_input(
    "Product Weight (kg)",
    min_value=0.1, max_value=100.0, value=2.58, step=0.1,
    help="Average product weight in kilograms"
)

unit_penaltycost = st.number_input(
    "Unit Penalty Cost (€)",
    min_value=0.0, max_value=10.0, value=1.7, step=0.1,
    help="Penalty cost per unit for unmet demand or deviations"
)

# ================================================================
# ⚙️ Model-specific parameters
# ================================================================
if "SC1F" in model_choice:
    st.subheader("⚙️ Parameters for SC1F (Existing Facilities)")
    co2_cost_per_ton = st.number_input(
        "CO₂ Cost per ton (€)",
        min_value=0.0, max_value=1000.0, value=37.50, step=1.0,
        help="CO₂ cost applied to production and transport (€/ton)"
    )

elif "SC2F" in model_choice:
    st.subheader("⚙️ Parameters for SC2F (Allows New Facilities)")
    co2_cost_per_ton_New = st.number_input(
        "CO₂ Cost per ton (New Facilities) (€)",
        min_value=0.0, max_value=1000.0, value=60.00, step=1.0,
        help="CO₂ cost per ton applied for new facilities"
    )

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
                    unit_penaltycost=unit_penaltycost,
                    print_results="NO"
                )
            else:
                results, model = run_SC2F(
                    CO_2_percentage=co2_pct,
                    product_weight=product_weight,
                    co2_cost_per_ton_New=co2_cost_per_ton_New,
                    unit_penaltycost=unit_penaltycost,
                    print_results="NO"
                )

            st.success("Optimization completed successfully ✅")

            # Objective value
            st.subheader("💰 Objective Value")
            st.metric("Total Cost (€)", f"{results['Objective_value']:,.2f}")

            # CO₂ Breakdown
            st.subheader("🌿 CO₂ Emissions Breakdown (tons)")
            st.json({
                "Air": round(results.get("E_air", 0), 2),
                "Sea": round(results.get("E_sea", 0), 2),
                "Road": round(results.get("E_road", 0), 2),
                "Last-mile": round(results.get("E_lastmile", 0), 2),
                "Production": round(results.get("E_production", 0), 2),
                "Total": round(results.get("CO2_Total", 0), 2),
            })

        except Exception as e:
            st.error(f"Optimization failed: {e}")
