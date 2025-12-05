# -*- coding: utf-8 -*-
"""
MASTER Model - Multi-Layer Parametric Supply Chain Optimization
Supports parametric selection for all 3 layers with independent mode choices
"""

from gurobipy import Model, GRB, quicksum
import pandas as pd
import numpy as np
from scipy.stats import norm
from helpers import print_flows

def run_scenario_master(
    # --- MASTER FLAGS ---
    use_new_locations=True,
    allow_unmet_demand=True,

    # --- PARAMETRIC LOCATION & MODE SELECTION (ALL LAYERS) ---
    selected_plants=None,           # Layer 1 source
    selected_crossdocks=None,       # Layer 1->2 intermediary / Layer 2 source
    selected_dcs=None,              # Layer 2->3 intermediary / Layer 3 source
    selected_retailers=None,        # Layer 3 demand
    selected_new_locs=None,         # Alternative Layer 2 source
    
    # Parametric modes for each layer
    selected_modes=None,            # Global modes (fallback for layers without specific selection)
    selected_modes_l1=None,         # Layer 1: Plant→Crossdock modes
    selected_modes_l2=None,         # Layer 2: Crossdock→DC modes
    selected_modes_l3=None,         # Layer 3: DC→Retailer modes

    # --- COMMON PARAMETERS ---
    dc_capacity=None,
    demand=None,
    handling_dc=None,
    handling_crossdock=None,
    sourcing_cost=None,
    co2_prod_kg_per_unit=None,
    product_weight=2.58,
    co2_cost_per_ton=37.50,
    co2_cost_per_ton_New=60.00,
    CO2_base=1582.42366689614,
    new_loc_capacity=None,
    new_loc_openingCost=None,
    new_loc_operationCost=None,
    new_loc_CO2=None,
    co2_emission_factor=None,
    dist1_matrix=None,              # Plant → Crossdock distances
    dist2_matrix=None,              # Crossdock → DC distances
    dist2_2_matrix=None,            # NewLoc → DC distances
    dist3_matrix=None,              # DC → Retailer distances
    data=None,
    lastmile_unit_cost=6.25,
    lastmile_CO2_kg=2.68,
    CO_2_percentage=0.5,
    unit_penaltycost=1.7,
    print_results="YES",
    unit_inventory_holdingCost=0.85,
    # --- SCENARIO EVENTS ---
    suez_canal=False,
    oil_crises=False,
    volcano=False,
    trade_war=False,
    tariff_rate=1.0,
    service_level=0.9,
):
    """
    Multi-layer parametric supply chain optimization model.
    
    Layers:
    - Layer 1 (L1): Plants → Crossdocks (modes: selected_modes_l1)
    - Layer 2 (L2): Crossdocks/NewLocs → DCs (modes: selected_modes_l2)
    - Layer 3 (L3): DCs → Retailers (modes: selected_modes_l3)
    """

    # =====================================================
    # DEFAULT DATA
    # =====================================================

    ALL_PLANTS = ["TW", "SHA"]
    ALL_CROSSDOCKS = ["ATVIE", "PLGDN", "FRCDG"]
    ALL_NEW_LOCS = ["HUDTG", "CZMCT", "IEILG", "FIMPF", "PLZCA"]
    ALL_DCS = ["PED", "FR6216", "RIX", "GMZ"]
    ALL_RETAILERS = ["FLUXC", "ALKFM", "KSJER", "GXEQH", "OAHLE", "ISNQE", "NAAVF"]
    ALL_MODES = ["air", "sea", "road"]
    ALL_MODES_L1 = ["air", "sea"]
    ALL_MODES_L2 = ["air", "sea", "road"]
    ALL_MODES_L3 = ["air", "sea", "road"]

    # --- PARAMETRIC SELECTION (defaults to ALL if not specified) ---
    Plants = selected_plants if selected_plants is not None else ALL_PLANTS
    Crossdocks = selected_crossdocks if selected_crossdocks is not None else ALL_CROSSDOCKS
    New_Locs = selected_new_locs if selected_new_locs is not None else ALL_NEW_LOCS
    Dcs = selected_dcs if selected_dcs is not None else ALL_DCS
    Retailers = selected_retailers if selected_retailers is not None else ALL_RETAILERS
    
    # Global modes fallback
    Modes = selected_modes if selected_modes is not None else ALL_MODES
    
    # Layer-specific modes with smart defaults
    ModesL1 = selected_modes_l1 if selected_modes_l1 is not None else [m for m in ALL_MODES_L1 if m in Modes]
    ModesL2 = selected_modes_l2 if selected_modes_l2 is not None else [m for m in ALL_MODES_L2 if m in Modes]
    ModesL3 = selected_modes_l3 if selected_modes_l3 is not None else [m for m in ALL_MODES_L3 if m in Modes]

    # Ensure at least one mode per layer
    if not ModesL1:
        ModesL1 = [ALL_MODES_L1[0]]
    if not ModesL2:
        ModesL2 = [ALL_MODES_L2[0]]
    if not ModesL3:
        ModesL3 = [ALL_MODES_L3[0]]

    # --- COMPLETE DEFAULT DATA ---
    all_demand = {
        "FLUXC": 17000, "ALKFM": 9000, "KSJER": 13000,
        "GXEQH": 19000, "OAHLE": 15000, "ISNQE": 20000, "NAAVF": 18000
    }
    all_dc_capacity = {"PED": 45000, "FR6216": 150000, "RIX": 75000, "GMZ": 100000}
    all_handling_dc = {
        "PED": 4.768269231, "FR6216": 5.675923077,
        "RIX": 4.426038462, "GMZ": 7.0865
    }
    all_handling_crossdock = {
        "ATVIE": 6.533884615, "PLGDN": 4.302269231, "FRCDG": 5.675923077
    }
    all_sourcing_cost = {"TW": 3.343692308, "SHA": 3.423384615}
    all_co2_prod_kg_per_unit = {"TW": 6.3, "SHA": 9.8}
    all_new_loc_capacity = {
        "HUDTG": 37000, "CZMCT": 45500, "IEILG": 46000,
        "FIMPF": 35000, "PLZCA": 16500
    }
    all_new_loc_openingCost = {
        "HUDTG": 7.4e6, "CZMCT": 9.1e6, "IEILG": 9.2e6,
        "FIMPF": 7e6, "PLZCA": 3.3e6
    }
    all_new_loc_operationCost = {
        "HUDTG": 250000, "CZMCT": 305000, "IEILG": 450000,
        "FIMPF": 420000, "PLZCA": 412500
    }
    all_new_loc_CO2 = {
        "HUDTG": 3.2, "CZMCT": 2.8, "IEILG": 4.6,
        "FIMPF": 5.8, "PLZCA": 6.2
    }
    all_co2_emission_factor = {"air": 0.000971, "sea": 0.000027, "road": 0.000076}

    # --- PARAMETRIC FILTER ---
    if demand is None:
        demand = {k: all_demand[k] for k in Retailers}
    if dc_capacity is None:
        dc_capacity = {k: all_dc_capacity[k] for k in Dcs}
    if handling_dc is None:
        handling_dc = {k: all_handling_dc[k] for k in Dcs}
    if handling_crossdock is None:
        handling_crossdock = {k: all_handling_crossdock[k] for k in Crossdocks}
    if sourcing_cost is None:
        sourcing_cost = {k: all_sourcing_cost[k] for k in Plants}
    if co2_prod_kg_per_unit is None:
        co2_prod_kg_per_unit = {k: all_co2_prod_kg_per_unit[k] for k in Plants}
    if new_loc_capacity is None:
        new_loc_capacity = {k: all_new_loc_capacity[k] for k in New_Locs}
    if new_loc_openingCost is None:
        new_loc_openingCost = {k: all_new_loc_openingCost[k] for k in New_Locs}
    if new_loc_operationCost is None:
        new_loc_operationCost = {k: all_new_loc_operationCost[k] for k in New_Locs}
    if new_loc_CO2 is None:
        new_loc_CO2 = {k: all_new_loc_CO2[k] for k in New_Locs}
    if co2_emission_factor is None:
        co2_emission_factor = {k: all_co2_emission_factor[k] for k in Modes}
    
    # Add layer-specific CO2 factors
    for mode in ModesL1:
        if mode not in co2_emission_factor:
            co2_emission_factor[mode] = all_co2_emission_factor.get(mode, 0.000076)
    for mode in ModesL2:
        if mode not in co2_emission_factor:
            co2_emission_factor[mode] = all_co2_emission_factor.get(mode, 0.000076)
    for mode in ModesL3:
        if mode not in co2_emission_factor:
            co2_emission_factor[mode] = all_co2_emission_factor.get(mode, 0.000076)

    service_level_dict = {m: service_level for m in Modes}

    average_distance = 9600
    all_speed = {'air': 800, 'sea': 10, 'road': 40}
    speed = {m: all_speed[m] for m in (ModesL1 + ModesL2 + ModesL3)}
    std_demand = np.std(list(demand.values()))

    if data is None:
        mode_list = list(set(ModesL1 + ModesL2 + ModesL3))
        all_data = {
            "transportation": ["air", "sea", "road"],
            "t (€/kg-km)": [0.0105, 0.0013, 0.0054],
        }
        mode_indices = {m: i for i, m in enumerate(all_data["transportation"])}
        data = {
            "transportation": mode_list,
            "t (€/kg-km)": [all_data["t (€/kg-km)"][mode_indices[m]] for m in mode_list],
        }

    data["h (€/unit)"] = [unit_inventory_holdingCost] * len(set(ModesL1 + ModesL2 + ModesL3))

    product_weight_ton = product_weight / 1000.0

    # =====================================================
    # DISTANCE MATRICES
    # =====================================================

    all_dist1 = pd.DataFrame(
        [[8997.94617146616, 8558.96520835034, 9812.38584027454],
         [8468.71339377354, 7993.62774285959, 9240.26233801075]],
        index=["TW", "SHA"],
        columns=["ATVIE", "PLGDN", "FRCDG"]
    )

    all_dist2 = pd.DataFrame(
        [[220.423995674989, 1019.43140587827, 1098.71652257982, 1262.62587924823],
         [519.161031102087, 1154.87176862626, 440.338211856603, 1855.94939751482],
         [962.668288266132, 149.819604703365, 1675.455462176, 2091.1437090641]],
        index=["ATVIE", "PLGDN", "FRCDG"],
        columns=["PED", "FR6216", "RIX", "GMZ"]
    )

    all_dist2_2 = pd.DataFrame(
        [[367.762425639798, 1216.10262027458, 1098.57245368619, 1120.13248546123],
         [98.034644813461, 818.765381327031, 987.72775809091, 1529.9990581232],
         [1558.60889112091, 714.077816812742, 1949.83469918776, 2854.35402610261],
         [1265.72892702748, 1758.18103997611, 367.698822815676, 2461.59771450036],
         [437.686419974076, 1271.77800922148, 554.373376462774, 1592.14058614186]],
        index=["HUDTG", "CZMCT", "IEILG", "FIMPF", "PLZCA"],
        columns=["PED", "FR6216", "RIX", "GMZ"]
    )

    all_dist3 = pd.DataFrame(
        [[1184.65051865833, 933.730015948432, 557.144058480586, 769.757089072695,
          2147.98445345001, 2315.79621115423, 1590.07662902924],
         [311.994969562194, 172.326685809878, 622.433010022067, 1497.40239816531,
          1387.73696467636, 1585.6370207201, 1984.31926933368],
         [1702.34810062205, 1664.62283033352, 942.985120680279, 222.318687415142,
          2939.50970842422, 3128.54724287652, 713.715034612432],
         [2452.23922908608, 2048.41487682505, 2022.91355628344, 1874.11994156457,
          2774.73634842816, 2848.65086298747, 2806.05576441898]],
        index=["PED", "FR6216", "RIX", "GMZ"],
        columns=["FLUXC", "ALKFM", "KSJER", "GXEQH", "OAHLE", "ISNQE", "NAAVF"]
    )

    dist1 = dist1_matrix if dist1_matrix is not None else all_dist1
    dist2 = dist2_matrix if dist2_matrix is not None else all_dist2
    dist2_2 = dist2_2_matrix if dist2_2_matrix is not None else all_dist2_2
    dist3 = dist3_matrix if dist3_matrix is not None else all_dist3

    # Filter distance matrices to selected locations
    dist1 = dist1.loc[Plants, Crossdocks]
    dist2 = dist2.loc[Crossdocks, Dcs]
    dist2_2 = dist2_2.loc[New_Locs, Dcs]
    dist3 = dist3.loc[Dcs, Retailers]

    # =====================================================
    # GUROBI MODEL
    # =====================================================
    model = Model("Unified_SC_Model_MultiLayer")

    # Decision variables for each layer
    f1 = model.addVars(
        ((p, c, mo) for p in Plants for c in Crossdocks for mo in ModesL1),
        lb=0, name="f1"
    )  # Layer 1: Plant → Crossdock

    f2 = model.addVars(
        ((c, d, mo) for c in Crossdocks for d in Dcs for mo in ModesL2),
        lb=0, name="f2"
    )  # Layer 2: Crossdock → DC

    f2_2 = model.addVars(
        ((c, d, mo) for c in New_Locs for d in Dcs for mo in ModesL2),
        lb=0, name="f2_2"
    )  # Layer 2: NewLoc → DC

    f2_2_bin = model.addVars(New_Locs, vtype=GRB.BINARY, name="f2_2_bin")

    f3 = model.addVars(
        ((d, r, mo) for d in Dcs for r in Retailers for mo in ModesL3),
        lb=0, name="f3"
    )  # Layer 3: DC → Retailer

    v = model.addVars(Retailers, name="v", lb=0)  # Unmet demand

    # =====================================================
    # CO2 CALCULATIONS (LAYER-SPECIFIC)
    # =====================================================

    # Layer 1 CO2 (Plant→Crossdock)
    CO2_tr_L1 = quicksum(
        co2_emission_factor.get(mo, 0.000076) * dist1.loc[p, c] * product_weight_ton * f1[p, c, mo]
        for p in Plants for c in Crossdocks for mo in ModesL1
    )

    # Layer 2 CO2 (Crossdock→DC)
    CO2_tr_L2 = quicksum(
        co2_emission_factor.get(mo, 0.000076) * dist2.loc[c, d] * product_weight_ton * f2[c, d, mo]
        for c in Crossdocks for d in Dcs for mo in ModesL2
    )

    # Layer 2_2 CO2 (NewLoc→DC)
    CO2_tr_L2_2 = quicksum(
        co2_emission_factor.get(mo, 0.000076) * dist2_2.loc[c, d] * product_weight_ton * f2_2[c, d, mo]
        for c in New_Locs for d in Dcs for mo in ModesL2
    )

    # Layer 3 CO2 (DC→Retailer)
    CO2_tr_L3 = quicksum(
        co2_emission_factor.get(mo, 0.000076) * dist3.loc[d, r] * product_weight_ton * f3[d, r, mo]
        for d in Dcs for r in Retailers for mo in ModesL3
    )

    # Production CO2
    CO2_prod_L1 = quicksum(
        co2_prod_kg_per_unit[p] * quicksum(f1[p, c, mo] for c in Crossdocks for mo in ModesL1)
        for p in Plants
    ) / 1000.0

    CO2_prod_L2_2 = quicksum(
        new_loc_CO2[c] * quicksum(f2_2[c, d, mo] for d in Dcs for mo in ModesL2)
        for c in New_Locs
    ) / 1000.0

    LastMile_CO2 = (lastmile_CO2_kg / 1000) * quicksum(
        f3[d, r, mo] for d in Dcs for r in Retailers for mo in ModesL3
    )

    Total_CO2 = (
        CO2_prod_L1 + CO2_prod_L2_2 +
        CO2_tr_L1 + CO2_tr_L2 + CO2_tr_L2_2 + CO2_tr_L3 +
        LastMile_CO2
    )

    # =====================================================
    # COSTS (LAYER-SPECIFIC)
    # =====================================================

    # Sourcing cost
    Cost_Sourcing = quicksum(
        sourcing_cost[p] * quicksum(f1[p, c, mo] for c in Crossdocks for mo in ModesL1)
        for p in Plants
    )

    # Layer 1 transport cost
    Cost_L1_Transport = quicksum(
        data.get("t (€/kg-km)", [0.0105, 0.0013, 0.0054])[["air", "sea", "road"].index(mo) if mo in ["air", "sea", "road"] else 0] * 
        dist1.loc[p, c] * product_weight_ton * f1[p, c, mo]
        for p in Plants for c in Crossdocks for mo in ModesL1
    )

    # Crossdock handling
    Cost_CD_Handling = quicksum(
        handling_crossdock[c] * quicksum(f1[p, c, mo] for p in Plants for mo in ModesL1)
        for c in Crossdocks
    )

    # Layer 2 transport cost
    Cost_L2_Transport = quicksum(
        data.get("t (€/kg-km)", [0.0105, 0.0013, 0.0054])[["air", "sea", "road"].index(mo) if mo in ["air", "sea", "road"] else 0] * 
        dist2.loc[c, d] * product_weight_ton * f2[c, d, mo]
        for c in Crossdocks for d in Dcs for mo in ModesL2
    )

    Cost_L2_2_Transport = quicksum(
        data.get("t (€/kg-km)", [0.0105, 0.0013, 0.0054])[["air", "sea", "road"].index(mo) if mo in ["air", "sea", "road"] else 0] * 
        dist2_2.loc[c, d] * product_weight_ton * f2_2[c, d, mo]
        for c in New_Locs for d in Dcs for mo in ModesL2
    )

    # DC handling
    Cost_DC_Handling = quicksum(
        handling_dc[d] * (quicksum(f2[c, d, mo] for c in Crossdocks for mo in ModesL2) +
                         quicksum(f2_2[c, d, mo] for c in New_Locs for mo in ModesL2))
        for d in Dcs
    )

    # Layer 3 transport cost
    Cost_L3_Transport = quicksum(
        data.get("t (€/kg-km)", [0.0105, 0.0013, 0.0054])[["air", "sea", "road"].index(mo) if mo in ["air", "sea", "road"] else 0] * 
        dist3.loc[d, r] * product_weight_ton * f3[d, r, mo]
        for d in Dcs for r in Retailers for mo in ModesL3
    )

    # Last-mile cost
    Cost_LastMile = lastmile_unit_cost * quicksum(f3[d, r, mo] for d in Dcs for r in Retailers for mo in ModesL3)

    # New facilities
    Cost_NewLoc = quicksum(
        new_loc_openingCost[c] * f2_2_bin[c] + new_loc_operationCost[c] * quicksum(f2_2[c, d, mo] for d in Dcs for mo in ModesL2)
        for c in New_Locs
    )

    # Unmet demand penalty
    Cost_Unmet = unit_penaltycost * quicksum(v[r] for r in Retailers)

    Total_Cost = (
        Cost_Sourcing + Cost_L1_Transport + Cost_CD_Handling +
        Cost_L2_Transport + Cost_L2_2_Transport + Cost_DC_Handling +
        Cost_L3_Transport + Cost_LastMile + Cost_NewLoc + Cost_Unmet
    )

    # =====================================================
    # OBJECTIVE & CONSTRAINTS
    # =====================================================

    # Objective: Minimize cost with CO2 penalty
    model.setObjective(
        Total_Cost + (CO_2_percentage * co2_cost_per_ton * Total_CO2 / 1000),
        GRB.MINIMIZE
    )

    # Flow conservation constraints
    for c in Crossdocks:
        model.addConstr(
            quicksum(f1[p, c, mo] for p in Plants for mo in ModesL1) ==
            quicksum(f2[c, d, mo] for d in Dcs for mo in ModesL2)
        )

    for d in Dcs:
        model.addConstr(
            quicksum(f2[c, d, mo] for c in Crossdocks for mo in ModesL2) +
            quicksum(f2_2[c, d, mo] for c in New_Locs for mo in ModesL2) ==
            quicksum(f3[d, r, mo] for r in Retailers for mo in ModesL3)
        )

    # Demand constraints
    for r in Retailers:
        model.addConstr(
            quicksum(f3[d, r, mo] for d in Dcs for mo in ModesL3) + v[r] >= demand[r]
        )

    # Capacity constraints
    for d in Dcs:
        model.addConstr(
            quicksum(f3[d, r, mo] for r in Retailers for mo in ModesL3) <= dc_capacity[d]
        )

    # New facility opening constraints
    for c in New_Locs:
        model.addConstr(
            quicksum(f2_2[c, d, mo] for d in Dcs for mo in ModesL2) <= new_loc_capacity[c] * f2_2_bin[c]
        )

    # CO2 constraint
    if CO_2_percentage > 0:
        model.addConstr(Total_CO2 <= CO2_base)

    # =====================================================
    # OPTIMIZE
    # =====================================================
    model.optimize()

    # =====================================================
    # EXTRACT RESULTS
    # =====================================================

    results = {
        "Status": model.status,
        "Total_Cost_€": model.objVal if model.status == 2 else 0,
        "CO2_Total": Total_CO2.getValue() if model.status == 2 else 0,
        "Demand_Fulfillment_Rate": 100 * (1 - sum(v[r].X for r in Retailers) / sum(demand.values())) if model.status == 2 else 0,
        
        # Layer-specific CO2
        "CO2_Layer1_Transport": CO2_tr_L1.getValue() if model.status == 2 else 0,
        "CO2_Layer2_Transport": (CO2_tr_L2.getValue() + CO2_tr_L2_2.getValue()) if model.status == 2 else 0,
        "CO2_Layer3_Transport": CO2_tr_L3.getValue() if model.status == 2 else 0,
        "CO2_Production": (CO2_prod_L1.getValue() + CO2_prod_L2_2.getValue()) if model.status == 2 else 0,
        "CO2_LastMile": LastMile_CO2.getValue() if model.status == 2 else 0,
        
        # Layer-specific costs
        "Cost_Layer1": (Cost_Sourcing.getValue() + Cost_L1_Transport.getValue() + Cost_CD_Handling.getValue()) if model.status == 2 else 0,
        "Cost_Layer2": (Cost_L2_Transport.getValue() + Cost_L2_2_Transport.getValue() + Cost_DC_Handling.getValue()) if model.status == 2 else 0,
        "Cost_Layer3": (Cost_L3_Transport.getValue() + Cost_LastMile.getValue()) if model.status == 2 else 0,
        "Cost_NewFacilities": Cost_NewLoc.getValue() if model.status == 2 else 0,
        
        # Selected configurations
        "Selected_Plants": list(Plants),
        "Selected_Crossdocks": list(Crossdocks),
        "Selected_DCs": list(Dcs),
        "Selected_Retailers": list(Retailers),
        "Selected_NewLocs": list(New_Locs),
        "Selected_Modes_L1": list(ModesL1),
        "Selected_Modes_L2": list(ModesL2),
        "Selected_Modes_L3": list(ModesL3),
    }

    if print_results == "YES":
        print("=" * 60)
        print("MULTI-LAYER OPTIMIZATION RESULTS")
        print("=" * 60)
        print(f"Status: {model.status}")
        print(f"Total Cost: €{results['Total_Cost_€']:,.2f}")
        print(f"Total CO2: {results['CO2_Total']:,.2f} kg")
        print(f"Demand Fulfillment: {results['Demand_Fulfillment_Rate']:.1f}%")
        print("\nLayer Configuration:")
        print(f"  L1 Modes: {ModesL1} | {len(Plants)} Plants → {len(Crossdocks)} Crossdocks")
        print(f"  L2 Modes: {ModesL2} | {len(Crossdocks)} Crossdocks → {len(Dcs)} DCs")
        print(f"  L3 Modes: {ModesL3} | {len(Dcs)} DCs → {len(Retailers)} Retailers")
        print("=" * 60)

    return results

if __name__ == "__main__":
    result = run_scenario_master()
    print(result)
