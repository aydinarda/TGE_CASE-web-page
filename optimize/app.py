import os
import streamlit as st
import gurobipy as gp

# ================================================================
# 🧩 Safe Imports
# ================================================================
try:
    from SC1F import run_scenario as run_SC1F
    from SC2F import run_scenario as run_SC2F
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
st.markdown("Enter any numeric value (≥ 0) for each parameter below, then run the optimization.")

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
unit_penaltycost = positive_input("Unit Penalty Cost (€)", 1.7)

if "SC1F" in model_choice:
    st.subheader("⚙️ Parameters for SC1F (Existing Facilities)")
    co2_cost_per_ton = positive_input("CO₂ Cost per ton (€)", 37.50)

elif "SC2F" in model_choice:
    st.subheader("⚙️ Parameters for SC2F (Allows New Facilities)")
    co2_cost_per_ton_New = positive_input("CO₂ Cost per ton (New Facilities) (€)", 60.00)

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

        except gp.GurobiError as ge:
            st.error(f"Gurobi Error {ge.errno}: {ge.message}")
        except Exception as e:
            st.error(f"❌ Optimization failed: {e}")
