# -*- coding: utf-8 -*-
"""
MASTER Model - Fully Parametric Supply Chain Optimization
Unifies SC1F_uns (without new locations) and SC2F_uns (with new locations)
Works identically to both reference scenarios depending on use_new_locations flag
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
    selected_plants=None,
    selected_crossdocks=None,
    selected_dcs=None,
    selected_retailers=None,
    selected_new_locs=None,
    
    # Parametric modes for each layer
    selected_modes_l1=None,
    selected_modes_l2=None,
    selected_modes_l3=None,

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
    dist1_matrix=None,
    dist2_matrix=None,
    dist2_2_matrix=None,
    dist3_matrix=None,
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
    Fully parametric multi-layer supply chain optimization.
    Equivalent to SC1F_uns when use_new_locations=False
    Equivalent to SC2F_uns when use_new_locations=True
    """

    # =====================================================
    # DEFAULT DATA
    # =====================================================

    ALL_PLANTS = ["TW", "SHA"]
    ALL_CROSSDOCKS = ["ATVIE", "PLGDN", "FRCDG"]
    ALL_NEW_LOCS = ["HUDTG", "CZMCT", "IEILG", "FIMPF", "PLZCA"]
    ALL_DCS = ["PED", "FR6216", "RIX", "GMZ"]
    ALL_RETAILERS = ["FLUXC", "ALKFM", "KSJER", "GXEQH", "OAHLE", "ISNQE", "NAAVF"]
    ALL_MODES_L1 = ["air", "sea"]
    ALL_MODES_L2 = ["air", "sea", "road"]
    ALL_MODES_L3 = ["air", "sea", "road"]

    # --- PARAMETRIC SELECTION ---
    Plants = selected_plants if selected_plants is not None else ALL_PLANTS
    Crossdocks = selected_crossdocks if selected_crossdocks is not None else ALL_CROSSDOCKS
    New_Locs = (selected_new_locs if selected_new_locs is not None else ALL_NEW_LOCS) if use_new_locations else []
    Dcs = selected_dcs if selected_dcs is not None else ALL_DCS
    Retailers = selected_retailers if selected_retailers is not None else ALL_RETAILERS
    
    ModesL1 = selected_modes_l1 if selected_modes_l1 is not None else ALL_MODES_L1
    ModesL2 = selected_modes_l2 if selected_modes_l2 is not None else ALL_MODES_L2
    ModesL3 = selected_modes_l3 if selected_modes_l3 is not None else ALL_MODES_L3

    # --- DEFAULT VALUES ---
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

    # --- PARAMETRIC FILTERING ---
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
        co2_emission_factor = all_co2_emission_factor
    
    # Setup data frame with transportation costs and inventory parameters
    service_level_dict = {m: service_level for m in ModesL2}
    average_distance = 9600
    speed = {'air': 800, 'sea': 10, 'road': 40}
    std_demand = np.std(list(demand.values()))

    if data is None:
        data = {
            "transportation": ["air", "sea", "road"],
            "t (€/kg-km)": [0.0105, 0.0013, 0.0054],
        }
    
    data["h (€/unit)"] = [unit_inventory_holdingCost] * 3
    
    # LT (days)
    data["LT (days)"] = [
        np.round((average_distance * (1.2 if m == "sea" else 1)) / (speed[m] * 24), 13)
        for m in ["air", "sea", "road"]
    ]
    
    # Z-scores and densities
    z_values = [norm.ppf(service_level) for _ in range(3)]
    phi_values = [norm.pdf(z) for z in z_values]
    
    data["Z-score Φ^-1(α)"] = z_values
    data["Density φ(Φ^-1(α))"] = phi_values
    
    # Safety stock (from reference scenarios)
    data["SS (€/unit)"] = [2109.25627631292, 12055.4037653689, 5711.89299799521]
    
    product_weight_ton = product_weight / 1000.0
    
    df = pd.DataFrame(data).set_index("transportation")
    tau = df["t (€/kg-km)"].to_dict()

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

    # Filter to selected locations
    dist1 = dist1.loc[Plants, Crossdocks]
    dist2 = dist2.loc[Crossdocks, Dcs]
    if use_new_locations and len(New_Locs) > 0:
        dist2_2 = dist2_2.loc[New_Locs, Dcs]
    dist3 = dist3.loc[Dcs, Retailers]

    # =====================================================
    # MODEL
    # =====================================================
    
    model = Model("SC_Master_Model")

    # Layer 1: Plant → Crossdock
    f1 = model.addVars(
        ((p, c, mo) for p in Plants for c in Crossdocks for mo in ModesL1),
        lb=0, name="f1"
    )

    # Layer 2: Crossdock → DC
    f2 = model.addVars(
        ((c, d, mo) for c in Crossdocks for d in Dcs for mo in ModesL2),
        lb=0, name="f2"
    )

    # Layer 2_2: NewLoc → DC (only if use_new_locations=True)
    if use_new_locations and len(New_Locs) > 0:
        f2_2 = model.addVars(
            ((c, d, mo) for c in New_Locs for d in Dcs for mo in ModesL2),
            lb=0, name="f2_2"
        )
        f2_2_bin = model.addVars(New_Locs, vtype=GRB.BINARY, name="f2_2_bin")
    else:
        f2_2 = {}
        f2_2_bin = {}

    # Layer 3: DC → Retailer
    f3 = model.addVars(
        ((d, r, mo) for d in Dcs for r in Retailers for mo in ModesL3),
        lb=0, name="f3"
    )

    # Unmet demand
    v = model.addVars(Retailers, name="v", lb=0)

    # =====================================================
    # CO2 CALCULATIONS
    # =====================================================

    # Transport CO2
    CO2_tr_L1 = quicksum(
        co2_emission_factor[mo] * dist1.loc[p, c] * product_weight_ton * f1[p, c, mo]
        for p in Plants for c in Crossdocks for mo in ModesL1
    )

    CO2_tr_L2 = quicksum(
        co2_emission_factor[mo] * dist2.loc[c, d] * product_weight_ton * f2[c, d, mo]
        for c in Crossdocks for d in Dcs for mo in ModesL2
    )

    if use_new_locations and len(New_Locs) > 0:
        CO2_tr_L2_2 = quicksum(
            co2_emission_factor[mo] * dist2_2.loc[c, d] * product_weight_ton * f2_2[c, d, mo]
            for c in New_Locs for d in Dcs for mo in ModesL2
        )
    else:
        CO2_tr_L2_2 = 0

    CO2_tr_L3 = quicksum(
        co2_emission_factor[mo] * dist3.loc[d, r] * product_weight_ton * f3[d, r, mo]
        for d in Dcs for r in Retailers for mo in ModesL3
    )

    # Production CO2
    CO2_prod_L1 = quicksum(
        co2_prod_kg_per_unit[p] * quicksum(f1[p, c, mo] for c in Crossdocks for mo in ModesL1)
        for p in Plants
    ) / 1000.0

    if use_new_locations and len(New_Locs) > 0:
        CO2_prod_L2_2 = quicksum(
            new_loc_CO2[c] * quicksum(f2_2[c, d, mo] for d in Dcs for mo in ModesL2)
            for c in New_Locs
        ) / 1000.0
    else:
        CO2_prod_L2_2 = 0

    LastMile_CO2 = (lastmile_CO2_kg / 1000) * quicksum(
        f3[d, r, mo] for d in Dcs for r in Retailers for mo in ModesL3
    )

    Total_CO2 = CO2_prod_L1 + CO2_prod_L2_2 + CO2_tr_L1 + CO2_tr_L2 + CO2_tr_L2_2 + CO2_tr_L3 + LastMile_CO2

    # CO2 breakdown by mode (for output)
    CO2_tr_L1_air = quicksum(
        co2_emission_factor["air"] * dist1.loc[p, c] * product_weight_ton * f1[p, c, "air"]
        for p in Plants for c in Crossdocks if "air" in ModesL1
    )
    CO2_tr_L1_sea = quicksum(
        co2_emission_factor["sea"] * dist1.loc[p, c] * product_weight_ton * f1[p, c, "sea"]
        for p in Plants for c in Crossdocks if "sea" in ModesL1
    )
    
    CO2_tr_L2_air = quicksum(
        co2_emission_factor["air"] * dist2.loc[c, d] * product_weight_ton * f2[c, d, "air"]
        for c in Crossdocks for d in Dcs if "air" in ModesL2
    )
    CO2_tr_L2_sea = quicksum(
        co2_emission_factor["sea"] * dist2.loc[c, d] * product_weight_ton * f2[c, d, "sea"]
        for c in Crossdocks for d in Dcs if "sea" in ModesL2
    )
    CO2_tr_L2_road = quicksum(
        co2_emission_factor["road"] * dist2.loc[c, d] * product_weight_ton * f2[c, d, "road"]
        for c in Crossdocks for d in Dcs if "road" in ModesL2
    )

    CO2_tr_L3_air = quicksum(
        co2_emission_factor["air"] * dist3.loc[d, r] * product_weight_ton * f3[d, r, "air"]
        for d in Dcs for r in Retailers if "air" in ModesL3
    )
    CO2_tr_L3_sea = quicksum(
        co2_emission_factor["sea"] * dist3.loc[d, r] * product_weight_ton * f3[d, r, "sea"]
        for d in Dcs for r in Retailers if "sea" in ModesL3
    )
    CO2_tr_L3_road = quicksum(
        co2_emission_factor["road"] * dist3.loc[d, r] * product_weight_ton * f3[d, r, "road"]
        for d in Dcs for r in Retailers if "road" in ModesL3
    )

    # =====================================================
    # COST CALCULATIONS
    # =====================================================

    # Transport costs by layer and mode
    Transport_L1 = {}
    for mo in ModesL1:
        Transport_L1[mo] = quicksum(
            tau[mo] * dist1.loc[p, c] * product_weight * f1[p, c, mo]
            for p in Plants for c in Crossdocks
        )
    Total_Transport_L1 = quicksum(Transport_L1[mo] for mo in ModesL1)

    Transport_L2 = {}
    for mo in ModesL2:
        Transport_L2[mo] = quicksum(
            tau[mo] * dist2.loc[c, d] * product_weight * f2[c, d, mo]
            for c in Crossdocks for d in Dcs
        )
    Total_Transport_L2 = quicksum(Transport_L2[mo] for mo in ModesL2)

    if use_new_locations and len(New_Locs) > 0:
        Transport_L2_2 = {}
        for mo in ModesL2:
            Transport_L2_2[mo] = quicksum(
                tau[mo] * dist2_2.loc[c, d] * product_weight * f2_2[c, d, mo]
                for c in New_Locs for d in Dcs
            )
        Total_Transport_L2_2 = quicksum(Transport_L2_2[mo] for mo in ModesL2)
    else:
        Transport_L2_2 = {}
        Total_Transport_L2_2 = 0

    Transport_L3 = {}
    for mo in ModesL3:
        Transport_L3[mo] = quicksum(
            tau[mo] * dist3.loc[d, r] * product_weight * f3[d, r, mo]
            for d in Dcs for r in Retailers
        )
    Total_Transport_L3 = quicksum(Transport_L3[mo] for mo in ModesL3)

    Total_Transport = Total_Transport_L1 + Total_Transport_L2 + Total_Transport_L2_2 + Total_Transport_L3

    # ================= INVENTORY COST DEFINITIONS =================
    
    # Layer 1
    InvCost_L1 = {}
    for mo in ModesL1:
        InvCost_L1[mo] = (
            quicksum(
                f1[p, c, mo] * df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                for p in Plants for c in Crossdocks
            )
            + quicksum(
                f1[p, c, mo] * df.loc[mo, "SS (€/unit)"] / sum(demand.values())
                for p in Plants for c in Crossdocks
            )
        )
    
    Total_InvCost_L1 = quicksum(InvCost_L1[mo] for mo in ModesL1)

    # Layer 2
    InvCost_L2 = {}
    for mo in ModesL2:
        InvCost_L2[mo] = (
            quicksum(
                f2[c, d, mo] * df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                for c in Crossdocks for d in Dcs
            )
            + quicksum(
                f2[c, d, mo] * df.loc[mo, "SS (€/unit)"] / sum(demand.values())
                for c in Crossdocks for d in Dcs
            )
        )
    
    Total_InvCost_L2 = quicksum(InvCost_L2[mo] for mo in ModesL2)

    # Layer 2_2 (only if new locations)
    if use_new_locations and len(New_Locs) > 0:
        InvCost_L2_2 = {}
        for mo in ModesL2:
            InvCost_L2_2[mo] = (
                quicksum(
                    f2_2[c, d, mo] * df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                    for c in New_Locs for d in Dcs
                )
                + quicksum(
                    f2_2[c, d, mo] * df.loc[mo, "SS (€/unit)"] / sum(demand.values())
                    for c in New_Locs for d in Dcs
                )
            )
        Total_InvCost_L2_2 = quicksum(InvCost_L2_2[mo] for mo in ModesL2)
    else:
        Total_InvCost_L2_2 = 0
    
    Whole_L2 = Total_InvCost_L2 + Total_InvCost_L2_2

    # Layer 3
    InvCost_L3 = {}
    for mo in ModesL3:
        InvCost_L3[mo] = (
            quicksum(
                f3[d, r, mo] * df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                for d in Dcs for r in Retailers
            )
            + quicksum(
                f3[d, r, mo] * df.loc[mo, "SS (€/unit)"] / sum(demand.values())
                for d in Dcs for r in Retailers
            )
        )
    
    Total_InvCost_L3 = quicksum(InvCost_L3[mo] for mo in ModesL3)

    Total_InvCost_Model = Total_InvCost_L1 + Whole_L2 + Total_InvCost_L3

    # ======================== Sourcing & Handling ========================
    
    Sourcing_L1 = quicksum(
        sourcing_cost[p] * quicksum(f1[p, c, mo] for c in Crossdocks for mo in ModesL1)
        for p in Plants
    )

    Handling_L2_existing = quicksum(
        handling_crossdock[c] * quicksum(f2[c, d, mo] for d in Dcs for mo in ModesL2)
        for c in Crossdocks
    )

    Handling_L2 = Handling_L2_existing

    Handling_L3 = quicksum(
        handling_dc[d] * quicksum(f3[d, r, mo] for r in Retailers for mo in ModesL3)
        for d in Dcs
    )

    # ======================== CO2 Costs ========================

    CO2_Mfg = co2_cost_per_ton / 1000 * quicksum(
        co2_prod_kg_per_unit[p] * quicksum(f1[p, c, mo] for c in Crossdocks for mo in ModesL1)
        for p in Plants
    )

    # CO2 cost for new locations (only if use_new_locations=True)
    if use_new_locations and len(New_Locs) > 0:
        CO2Cost_L2_2 = quicksum(
            new_loc_CO2[c] * quicksum(f2_2[c, d, mo] for d in Dcs for mo in ModesL2)
            * (co2_cost_per_ton_New / 1000)
            for c in New_Locs
        )
    else:
        CO2Cost_L2_2 = 0

    # Last-mile cost
    LastMile_Cost = lastmile_unit_cost * quicksum(
        f3[d, r, mo] for d in Dcs for r in Retailers for mo in ModesL3
    )

    # =================== New Location Costs (only if use_new_locations=True) ===================

    if use_new_locations and len(New_Locs) > 0:
        new_loc_totalCost = {
            loc: new_loc_openingCost[loc] + new_loc_operationCost[loc]
            for loc in new_loc_openingCost
        }
        new_loc_unitCost = {loc: (1 / cap) * 100000 for loc, cap in new_loc_capacity.items()}
        
        FixedCost_NewLocs = quicksum(
            new_loc_totalCost[c] * f2_2_bin[c]
            for c in New_Locs
        )

        ProdCost_NewLocs = quicksum(
            new_loc_unitCost[c] * quicksum(f2_2[c, d, mo] for d in Dcs for mo in ModesL2)
            for c in New_Locs
        )

        Cost_NewLocs = FixedCost_NewLocs + ProdCost_NewLocs
    else:
        FixedCost_NewLocs = 0
        ProdCost_NewLocs = 0
        Cost_NewLocs = 0

    # =====================================================
    # CONSTRAINTS
    # =====================================================

    # Demand with slack (allow unmet demand)
    model.addConstrs(
        (
            quicksum(f3[d, r, mo] for d in Dcs for mo in ModesL3) + v[r] == demand[r]
            for r in Retailers
        ),
        name="DemandWithSlack"
    )

    # DC balance
    model.addConstrs(
        (
            quicksum(f2[c, d, mo] for c in Crossdocks for mo in ModesL2)
            + (quicksum(f2_2[c, d, mo] for c in New_Locs for mo in ModesL2) if use_new_locations and len(New_Locs) > 0 else 0)
            == quicksum(f3[d, r, mo] for r in Retailers for mo in ModesL3)
            for d in Dcs
        ),
        name="DCBalance"
    )

    # Crossdock balance
    model.addConstrs(
        (
            quicksum(f1[p, c, mo] for p in Plants for mo in ModesL1) ==
            quicksum(f2[c, d, mo] for d in Dcs for mo in ModesL2)
            for c in Crossdocks
        ),
        name="CrossdockBalance"
    )

    # DC capacity
    model.addConstrs(
        (
            quicksum(f3[d, r, mo] for r in Retailers for mo in ModesL3) <= dc_capacity[d]
            for d in Dcs
        ),
        name="DCCapacity"
    )

    # New facility capacity (only if use_new_locations=True)
    if use_new_locations and len(New_Locs) > 0:
        model.addConstrs(
            (
                quicksum(f2_2[c, d, mo] for d in Dcs for mo in ModesL2)
                <= new_loc_capacity[c] * f2_2_bin[c]
                for c in New_Locs
            ),
            name="NewFacilityCapacity"
        )

    # CO2 constraint
    model.addConstr(
        Total_CO2 <= CO2_base * (1 - CO_2_percentage),
        name="CO2ReductionTarget"
    )

    # =====================================================
    # SCENARIO SETTINGS
    # =====================================================

    # SUEZ CANAL BLOCKADE
    if suez_canal:
        model.addConstrs(
            (f1[p, c, "sea"] == 0 for p in Plants for c in Crossdocks if "sea" in ModesL1),
            name="SeaDamage_f1"
        )

    # OIL CRISES
    if oil_crises:
        Total_Transport = Total_Transport * 1.3
        LastMile_Cost = LastMile_Cost * 1.3

    # VOLCANO ERUPTION
    if volcano:
        if "air" in ModesL1:
            model.addConstrs(
                (f1[p, c, "air"] == 0 for p in Plants for c in Crossdocks),
                name="Volcano_block_f1"
            )
        
        if "air" in ModesL2:
            model.addConstrs(
                (f2[c, d, "air"] == 0 for c in Crossdocks for d in Dcs),
                name="Volcano_block_f2"
            )
        
        if use_new_locations and len(New_Locs) > 0 and "air" in ModesL2:
            model.addConstrs(
                (f2_2[c, d, "air"] == 0 for c in New_Locs for d in Dcs),
                name="Volcano_block_f2_2"
            )
        
        if "air" in ModesL3:
            model.addConstrs(
                (f3[d, r, "air"] == 0 for d in Dcs for r in Retailers),
                name="Volcano_block_f3"
            )

    # TRADE WAR
    if trade_war:
        Sourcing_L1 = Sourcing_L1 * tariff_rate

    # =====================================================
    # OBJECTIVE
    # =====================================================

    M = 1e8
    
    model.setObjective(
        Sourcing_L1 + Handling_L2 + Handling_L3 + LastMile_Cost +
        CO2_Mfg + CO2Cost_L2_2 + Total_Transport + Total_InvCost_Model +
        Cost_NewLocs + M * quicksum(v[r] for r in Retailers),
        GRB.MINIMIZE
    )

    # =====================================================
    # SOLVE
    # =====================================================
    
    model.optimize()

    # =====================================================
    # OUTPUT
    # =====================================================

    f1_matrix = print_flows(f1, Plants, Crossdocks, ModesL1, "f1 (Plant → Crossdock)")
    f2_matrix = print_flows(f2, Crossdocks, Dcs, ModesL2, "f2 (Crossdock → DC)")
    if use_new_locations and len(New_Locs) > 0:
        f2_2_matrix = print_flows(f2_2, New_Locs, Dcs, ModesL2, "f2_2 (NewLoc → DC)")
    f3_matrix = print_flows(f3, Dcs, Retailers, ModesL3, "f3 (DC → Retailer)")

    if print_results == "YES":
        print("Transport L1:", sum(Transport_L1[mo].getValue() for mo in ModesL1))
        print("Transport L2:", sum(Transport_L2[mo].getValue() for mo in ModesL2))
        if use_new_locations and len(New_Locs) > 0:
            print("Transport L2 new:", sum(Transport_L2_2[mo].getValue() for mo in ModesL2))
        print("Transport L3:", sum(Transport_L3[mo].getValue() for mo in ModesL3))

        print("Inventory L1:", Total_InvCost_L1.getValue())
        print("Inventory L2:", Total_InvCost_L2.getValue())
        if use_new_locations and len(New_Locs) > 0:
            print("Inventory L2 new:", Total_InvCost_L2_2.getValue())
        print("Inventory L3:", Total_InvCost_L3.getValue())
        
        print("Fixed Last Mile:", LastMile_Cost.getValue())
        
        print("CO2 Manufacturing at State 1:", CO2_Mfg.getValue())
        if use_new_locations and len(New_Locs) > 0:
            print("CO2 Cost L2_2:", CO2Cost_L2_2.getValue())
        
        print(f"Sourcing_L1: {Sourcing_L1.getValue():,.2f}")
        print(f"Handling_L2_existing: {Handling_L2_existing.getValue():,.2f}")
        print(f"Handling_L2 (total): {Handling_L2.getValue():,.2f}")
        print(f"Handling_L3: {Handling_L3.getValue():,.2f}")
        
        if use_new_locations and len(New_Locs) > 0:
            print("Fixed new locs:", FixedCost_NewLocs.getValue())
            print("Prod new locs:", ProdCost_NewLocs.getValue())

        print("CO2 total:", Total_CO2.getValue())
        print("Total objective:", model.ObjVal)

    E_air = (CO2_tr_L1_air + CO2_tr_L2_air + CO2_tr_L3_air).getValue()
    E_sea = (CO2_tr_L1_sea + CO2_tr_L2_sea + CO2_tr_L3_sea).getValue()
    E_road = (CO2_tr_L2_road + CO2_tr_L3_road).getValue()
    E_lastmile = LastMile_CO2.getValue()
    E_production = CO2_prod_L1.getValue()

    U = sum(v[r].X for r in Retailers)
    D_tot = sum(demand[r] for r in Retailers)
    satisfied_units = D_tot - U
    satisfied_pct = satisfied_units / D_tot if D_tot > 0 else 0

    results = {
        # --- Transport Costs ---
        "Transport_L1": sum(Transport_L1[mo].getValue() for mo in ModesL1),
        "Transport_L2": sum(Transport_L2[mo].getValue() for mo in ModesL2),
        "Transport_L2_new": sum(Transport_L2_2[mo].getValue() for mo in ModesL2) if use_new_locations and len(New_Locs) > 0 else 0,
        "Transport_L3": sum(Transport_L3[mo].getValue() for mo in ModesL3),

        # --- Inventory Costs ---
        "Inventory_L1": Total_InvCost_L1.getValue(),
        "Inventory_L2": Total_InvCost_L2.getValue(),
        "Inventory_L2_new": Total_InvCost_L2_2 if use_new_locations and len(New_Locs) > 0 else 0,
        "Inventory_L3": Total_InvCost_L3.getValue(),

        # --- Last Mile & CO2 ---
        "Fixed_Last_Mile": LastMile_Cost.getValue(),
        "CO2_Cost_L2_2": CO2Cost_L2_2.getValue() if use_new_locations and len(New_Locs) > 0 else 0,
        "CO2_Manufacturing_State1": CO2_Mfg.getValue(),
        "CO2_Total": Total_CO2.getValue(),

        # --- Sourcing & Handling ---
        "Sourcing_L1": Sourcing_L1.getValue(),
        "Handling_L2_existing": Handling_L2_existing.getValue(),
        "Handling_L2_total": Handling_L2.getValue(),
        "Handling_L3": Handling_L3.getValue(),

        # --- New Locations & Production ---
        "FixedCost_NewLocs": FixedCost_NewLocs.getValue() if use_new_locations and len(New_Locs) > 0 else 0,
        "ProdCost_NewLocs": ProdCost_NewLocs.getValue() if use_new_locations and len(New_Locs) > 0 else 0,
        
        # --- Emission Calculations ---
        "E_air": E_air,
        "E_sea": E_sea,
        "E_road": E_road,
        "E_lastmile": E_lastmile,
        "E_production": E_production,

        # --- Objective ---
        "Objective_value": model.ObjVal - M * U if model.status == 2 else 0,
        "Satisfied_Demand_pct": satisfied_pct,
        "Satisfied_Demand_units": satisfied_units
    }

    return results, model


if __name__ == "__main__":
    # Test with new locations (like SC2F_uns)
    result, model = run_scenario_master(use_new_locations=True, print_results="YES")
    print("\n✓ SC2F_uns equivalent test completed")
    
    # Test without new locations (like SC1F_uns)
    result, model = run_scenario_master(use_new_locations=False, print_results="YES")
    print("\n✓ SC1F_uns equivalent test completed")
