import os
import streamlit as st
from SC1F import run_scenario
import gurobipy as gp

# ================================================================
# 🔐 Load Gurobi WLS credentials securely (from Streamlit secrets)
# ================================================================
for var in ["GRB_WLSACCESSID", "GRB_WLSSECRET", "GRB_LICENSEID"]:
    if var in st.secrets:
        os.environ[var] = st.secrets[var]

# ================================================================
# 🏷️ Streamlit Interface
# ================================================================
st.set_page_config(page_title="Global Supply Chain Optimization", layout="centered")
st.title("🌍 Global Supply Chain Optimization (Gurobi)")

st.markdown("""
Enter your scenario parameters below and click **Run Optimization** to execute the model online.
""")

# ================================================================
# 🎛️ User Input Section (each accepts one number)
# ================================================================
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

co2_cost_per_ton = st.number_input(
    "CO₂ Cost per ton (€)", 
    min_value=0.0, max_value=1000.0, value=37.50, step=1.0,
    help="Cost penalty applied per ton of emitted CO₂"
)

unit_penaltycost = st.number_input(
    "Unit Penalty Cost (€)", 
    min_value=0.0, max_value=10.0, value=1.7, step=0.1,
    help="Penalty cost per unit for unmet demand or deviations"
)

# ================================================================
# ▶️ Run Optimization
# ================================================================
if st.button("Run Optimization"):
    with st.spinner("Running Gurobi optimization... Please wait ⏳"):
        try:
            results, model = run_scenario(
                CO_2_percentage=co2_pct,
                product_weight=product_weight,
                co2_cost_per_ton=co2_cost_per_ton,
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
                "Air": round(results["E_air"], 2),
                "Sea": round(results["E_sea"], 2),
                "Road": round(results["E_road"], 2),
                "Last-mile": round(results["E_lastmile"], 2),
                "Production": round(results["E_production"], 2),
                "Total": round(results["CO2_Total"], 2)
            })

        except Exception as e:
            st.error(f"Optimization failed: {e}")
