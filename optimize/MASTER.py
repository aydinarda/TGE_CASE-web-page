# -*- coding: utf-8 -*-
"""
MASTER.py

Fully parametric multi-layer supply-chain optimization model.

- Plants, cross-docks, DCs, and potential new locations can be switched on/off
  via input lists (active_*).
- Transport modes (air / sea / road) can be switched on/off separately
  for each layer (L1, L2, L3).
- Retailers and their demand stay as in the original models.

Returns:
    results: dict with KPIs (objective, CO2 by mode, etc.)
    model:   gurobipy Model instance
"""

from gurobipy import Model, GRB, quicksum
import pandas as pd
import numpy as np
from scipy.stats import norm




def print_flows(flow_vars, O, D, M, title="flow"):
    """
    flow_vars: gurobi var dict like f1[p,c,mo]
    O: origins list
    D: destinations list
    M: modes list (ModesL1 / ModesL2 / ModesL3)
    Returns a pandas DataFrame with sums over modes.
    """
    if not flow_vars:
        return pd.DataFrame(index=O, columns=D).fillna(0.0)

    data = []
    for o in O:
        row = []
        for d in D:
            s = 0.0
            for mo in M:
                v = flow_vars.get((o, d, mo), None)
                if v is not None:
                    try:
                        s += float(v.X)
                    except Exception:
                        pass
            row.append(s)
        data.append(row)

    df = pd.DataFrame(data, index=O, columns=D)
    df.index.name = title
    return df



def run_scenario_master(
    # --- Location selection (None => use full default set) ---
    active_plants=None,
    active_new_locs=None,
    active_crossdocks=None,
    active_dcs=None,

    # --- Mode selection per layer (None => use default) ---
    active_modes_L1=None,   # Plant -> Crossdock
    active_modes_L2=None,   # Crossdock/NewLoc -> DC
    active_modes_L3=None,   # DC -> Retailer

    # --- Data (all optional; sensible defaults where possible) ---
    dc_capacity=None,
    demand=None,
    handling_dc=None,
    handling_crossdock=None,
    sourcing_cost=None,
    co2_prod_kg_per_unit=None,
    product_weight=2.58,           # kg per unit
    co2_cost_per_ton=37.50,        # €/ton for existing mfg CO2
    co2_cost_per_ton_New=60.00,    # €/ton for new loc mfg CO2
    CO2_base=1582.42366689614,     # baseline CO2 (tons) for % reduction
    new_loc_capacity=None,
    new_loc_openingCost=None,
    new_loc_operationCost=None,    # not essential; kept for compatibility
    new_loc_CO2=None,              # kg CO2 per unit at new locations
    co2_emission_factor=None,      # ton CO2 / (ton-km)
    data=None,                     # per-mode cost + inventory meta
    dist1=None,                    # Plant -> Crossdock (km)
    dist2=None,                    # Crossdock -> DC (km)
    dist2_new=None,                # NewLoc -> DC (km)
    dist3=None,                    # DC -> Retailer (km)
    lastmile_unit_cost=6.25,       # €/unit last-mile cost
    lastmile_CO2_kg=2.68,          # kg CO2 per unit last-mile
    CO_2_max=None,                 # direct CO2 cap (tons), if given
    CO_2_percentage=0.5,           # reduction vs CO2_base
    unit_penaltycost=1.7,          # kept for compatibility (unused here)
    unit_inventory_holdingCost=0.85,
    service_level = 0.9,
    
    # NEW: per-new-location switches (None => backward compatible)
    isHUDTG=None,
    isCZMCT=None,
    isIEILG=None,
    isFIMPF=None,
    isPLZCA=None,

    # --- Scenario toggles ---
    suez_canal=False,              # blocks sea on L1
    oil_crises=False,              # increases transport cost
    volcano=False,                 # blocks all air
    trade_war=False,               # increases sourcing cost
    tariff_rate=1.0,               # used with trade_war

    # --- Output verbosity ---
    print_results="YES",
):
    # ======================================================
    # 1. MASTER SETS & DEFAULT NETWORK DATA
    # ======================================================

    # Superset of locations (same IDs as your SC1F/SC2F)
    Plants_all     = ["TW", "SHA"]
    Crossdocks_all = ["ATVIE", "PLGDN", "FRCDG"]
    New_Locs_all   = ["HUDTG", "CZMCT", "IEILG", "FIMPF", "PLZCA"]
    Dcs_all        = ["PED", "FR6216", "RIX", "GMZ"]

    # Default demand (same as in SC2F)
    if demand is None:
        demand = {
            "FLUXC": 17000,
            "ALKFM": 9000,
            "KSJER": 13000,
            "GXEQH": 19000,
            "OAHLE": 15000,
            "ISNQE": 20000,
            "NAAVF": 18000,
        }
    Retailers = list(demand.keys())

    # DC capacities (default)
    if dc_capacity is None:
        dc_capacity = {"PED": 45000, "FR6216": 150000, "RIX": 75000, "GMZ": 100000}

    # Handling costs (€/unit)
    if handling_dc is None:
        handling_dc = {"PED": 4.768269231, "FR6216": 5.675923077,
                       "RIX": 4.426038462, "GMZ": 7.0865}
    if handling_crossdock is None:
        handling_crossdock = {"ATVIE": 6.533884615,
                              "PLGDN": 4.302269231,
                              "FRCDG": 5.675923077}

    # Sourcing & production CO2 at existing plants
    if sourcing_cost is None:
        sourcing_cost = {"TW": 3.343692308, "SHA": 3.423384615}
    if co2_prod_kg_per_unit is None:
        co2_prod_kg_per_unit = {"TW": 6.3, "SHA": 9.8}

    # New location parameters
    if new_loc_capacity is None:
        new_loc_capacity = {
            "HUDTG": 37000, "CZMCT": 45500, "IEILG": 46000,
            "FIMPF": 35000, "PLZCA": 16500,
        }
    if new_loc_openingCost is None:
        new_loc_openingCost = {
            "HUDTG": 7.4e6, "CZMCT": 9.1e6, "IEILG": 9.2e6,
            "FIMPF": 7e6,   "PLZCA": 3.3e6,
        }
    if new_loc_operationCost is None:
        new_loc_operationCost = {
            "HUDTG": 250000, "CZMCT": 305000, "IEILG": 450000,
            "FIMPF": 420000, "PLZCA": 412500,
        }
    if new_loc_CO2 is None:
        new_loc_CO2 = {
            "HUDTG": 3.2, "CZMCT": 2.8, "IEILG": 4.6,
            "FIMPF": 5.8, "PLZCA": 6.2,
        }

    # Transport emission factor (ton CO2 per ton-km)
    if co2_emission_factor is None:
        co2_emission_factor = {"air": 0.000971, "sea": 0.000027, "road": 0.000076}

    # Per-mode transport & inventory meta
    if data is None:
        data = {
            "transportation": ["air", "sea", "road"],
            "t (€/kg-km)":    [0.0105, 0.0013, 0.0054],
        }
    df = pd.DataFrame(data).set_index("transportation")

    # Add holding cost if not present
    if "h (€/unit)" not in df.columns:
        df["h (€/unit)"] = unit_inventory_holdingCost

    # Service level per mode
    service_level = {
        "air": service_level,
        "sea": service_level,
        "road": service_level,
    }

    # Build LT, z, φ, and SS(€/unit) if missing
    if "SS (€/unit)" not in df.columns:
        average_distance = 9600  # rough benchmark
        speed = {"air": 800, "sea": 10, "road": 40}
        std_demand = np.std(list(demand.values()))

        if "LT (days)" not in df.columns:
            df["LT (days)"] = [
                np.round((average_distance * (1.2 if m == "sea" else 1))
                         / (speed[m] * 24), 13)
                for m in df.index
            ]

        z_values = [norm.ppf(service_level[m]) for m in df.index]
        phi_values = [norm.pdf(z) for z in z_values]

        df["Z-score Φ^-1(α)"] = z_values
        df["Density φ(Φ^-1(α))"] = phi_values

        # SS (€/unit) ≈ √(LT+1) * σ * (p + h) * φ(z)
        SS_vals = []
        for m in df.index:
            LT = df.loc[m, "LT (days)"]
            h = df.loc[m, "h (€/unit)"]
            z = df.loc[m, "Z-score Φ^-1(α)"]
            phi_z = df.loc[m, "Density φ(Φ^-1(α))"]
            p = 0.0  # price component omitted; you can plug it later
            SS = np.sqrt(LT + 1) * std_demand * (p + h) * phi_z
            SS_vals.append(SS)
        df["SS (€/unit)"] = SS_vals
    
    
    data["SS (€/unit)"] = [2109.25627631292, 12055.4037653689, 5711.89299799521] # may turn back to above calculation, just keeping hardcoded version for now
    # Shortcut: per-mode variable transport cost in €/kg-km
    tau = {m: df.loc[m, "t (€/kg-km)"] for m in df.index}

    # Distances (km); where missing, we use simple placeholders
    # Plant -> Crossdock (2 x 3)
    if dist1 is None:
        dist1 = pd.DataFrame(
            [[8997.94617146616, 8558.96520835034, 9812.38584027454],
             [8468.71339377354, 7993.62774285959, 9240.26233801075]],
            index=["TW", "SHA"],
            columns=["ATVIE", "PLGDN", "FRCDG"],
        )

    # Crossdock -> DC (3 x 4)
    if dist2 is None:
        dist2 = pd.DataFrame(
            [[220.423995674989, 1019.43140587827, 1098.71652257982, 1262.62587924823],
             [519.161031102087, 1154.87176862626, 440.338211856603, 1855.94939751482],
             [962.668288266132, 149.819604703365, 1675.455462176, 2091.1437090641]],
            index=["ATVIE", "PLGDN", "FRCDG"],
            columns=["PED", "FR6216", "RIX", "GMZ"],
        )

    # NewLoc -> DC (5 x 4)
    if dist2_new is None:
        dist2_new = pd.DataFrame(
            [[367.762425639798, 1216.10262027458, 1098.57245368619, 1120.13248546123],
             [98.034644813461, 818.765381327031, 987.72775809091, 1529.9990581232],
             [1558.60889112091, 714.077816812742, 1949.83469918776, 2854.35402610261],
             [1265.72892702748, 1758.18103997611, 367.698822815676, 2461.59771450036],
             [437.686419974076, 1271.77800922148, 554.373376462774, 1592.14058614186]],
            index=["HUDTG", "CZMCT", "IEILG", "FIMPF", "PLZCA"],
            columns=["PED", "FR6216", "RIX", "GMZ"],
        )

    # DC -> Retailer (4 x 7) — placeholder; feel free to overwrite with true distances
    if dist3 is None:
        dist3 = pd.DataFrame(
            [[1184.65051865833, 933.730015948432, 557.144058480586, 769.757089072695, 2147.98445345001, 2315.79621115423, 1590.07662902924],
             [311.994969562194, 172.326685809878, 622.433010022067, 1497.40239816531, 1387.73696467636, 1585.6370207201, 1984.31926933368],
             [1702.34810062205, 1664.62283033352, 942.985120680279, 222.318687415142, 2939.50970842422, 3128.54724287652, 713.715034612432],
             [2452.23922908608, 2048.41487682505, 2022.91355628344, 1874.11994156457, 2774.73634842816, 2848.65086298747, 2806.05576441898]],
            index=["PED","FR6216","RIX","GMZ"],
            columns=["FLUXC","ALKFM","KSJER","GXEQH","OAHLE","ISNQE","NAAVF"]
        )

    # ======================================================
    # 2. ACTIVE SETS & MODES
    # ======================================================
    
    # Base selection (existing behavior)
    New_Locs_base = New_Locs_all if active_new_locs is None else list(active_new_locs)

    # Locations: if user passes a list, we use that; otherwise full set
    Plants = Plants_all if active_plants is None else list(active_plants)
    # NEW: flags -> location mapping
    newloc_flags = {
        "HUDTG": isHUDTG,
        "CZMCT": isCZMCT,
        "IEILG": isIEILG,
        "FIMPF": isFIMPF,
        "PLZCA": isPLZCA,
    }
    
    # If any flag is explicitly provided (True/False), use flags as the gate.
    if any(v is not None for v in newloc_flags.values()):
        selected = {k for k, v in newloc_flags.items() if bool(v)}
        New_Locs = [n for n in New_Locs_base if n in selected]
    else:
        # Backward compatible: no flags provided => keep old behavior
        New_Locs = list(New_Locs_base)
    Crossdocks = Crossdocks_all if active_crossdocks is None else list(active_crossdocks)
    Dcs = Dcs_all if active_dcs is None else list(active_dcs)

    # Basic mode defaults
    ModesL1_default = ["air", "sea"]
    ModesL2_default = ["air", "sea", "road"]
    ModesL3_default = ["air", "sea", "road"]

    ModesL1 = ModesL1_default if active_modes_L1 is None else list(active_modes_L1)
    ModesL2 = ModesL2_default if active_modes_L2 is None else list(active_modes_L2)
    ModesL3 = ModesL3_default if active_modes_L3 is None else list(active_modes_L3)

    # Volcano: block all air → we keep modes in data but disallow flows via constraints
    if volcano:
        if "air" in ModesL1:
            ModesL1.remove("air")
        if "air" in ModesL2:
            ModesL2.remove("air")
        if "air" in ModesL3:
            ModesL3.remove("air")

    # Global set of modes used anywhere in the model
    Modes = sorted(set(ModesL1) | set(ModesL2) | set(ModesL3))

    # ======================================================
    # 3. SCENARIO IMPACTS ON COST PARAMETERS
    # ======================================================

    # Oil crisis: increase all transport costs
    if oil_crises:
        for m in tau:
            tau[m] *= 1.3

    # Trade war: increase sourcing cost at plants
    if trade_war:
        for p in sourcing_cost:
            sourcing_cost[p] *= tariff_rate

    product_weight_ton = product_weight / 1000.0

    # Simple per-unit variable cost at new locations (derived from capacity)
    new_loc_unitCost = {
        loc: (1.0 / new_loc_capacity[loc]) * 100000.0
        for loc in new_loc_capacity
    }

    # ======================================================
    # 4. MODEL & DECISION VARIABLES
    # ======================================================

    model = Model("MASTER_SC_Model")

    # Flows
    f1 = {}
    if len(Plants) > 0 and len(Crossdocks) > 0 and len(ModesL1) > 0:
        f1 = model.addVars(
            ((p, c, mo) for p in Plants for c in Crossdocks for mo in ModesL1),
            lb=0,
            name="f1",   # Plant → Crossdock
        )

    f2 = {}
    if len(Crossdocks) > 0 and len(Dcs) > 0 and len(ModesL2) > 0:
        f2 = model.addVars(
            ((c, d, mo) for c in Crossdocks for d in Dcs for mo in ModesL2),
            lb=0,
            name="f2",   # Crossdock → DC
        )

    f2_new = {}
    f2_2_bin = {}
    if len(New_Locs) > 0 and len(Dcs) > 0 and len(ModesL2) > 0:
        f2_new = model.addVars(
            ((n, d, mo) for n in New_Locs for d in Dcs for mo in ModesL2),
            lb=0,
            name="f2_2",   # NewLoc → DC
        )
        f2_2_bin = model.addVars(New_Locs, vtype=GRB.BINARY, name="f2_2_bin")
        
        
        

    f3 = {}
    if len(Dcs) > 0 and len(Retailers) > 0 and len(ModesL3) > 0:
        f3 = model.addVars(
            ((d, r, mo) for d in Dcs for r in Retailers for mo in ModesL3),
            lb=0,
            name="f3",   # DC → Retailer
        )

    # ======================================================
    # 5. COST & CO2 EXPRESSIONS
    # ======================================================

    # ---- Transport cost ----
    Transport_L1 = {}
    if f1:
        for mo in ModesL1:
            Transport_L1[mo] = quicksum(
                tau[mo] * dist1.loc[p, c] * product_weight * f1[p, c, mo]
                for p in Plants for c in Crossdocks
            )
    Total_Transport_L1 = quicksum(Transport_L1.values()) if Transport_L1 else 0

    Transport_L2 = {}
    if f2:
        for mo in ModesL2:
            Transport_L2[mo] = quicksum(
                tau[mo] * dist2.loc[c, d] * product_weight * f2[c, d, mo]
                for c in Crossdocks for d in Dcs
            )
    Total_Transport_L2 = quicksum(Transport_L2.values()) if Transport_L2 else 0

    Transport_L2_new = {}
    if f2_new:
        for mo in ModesL2:
            Transport_L2_new[mo] = quicksum(
                tau[mo] * dist2_new.loc[n, d] * product_weight * f2_new[n, d, mo]
                for n in New_Locs for d in Dcs
            )
    Total_Transport_L2_new = quicksum(Transport_L2_new.values()) if Transport_L2_new else 0

    Transport_L3 = {}
    if f3:
        for mo in ModesL3:
            Transport_L3[mo] = quicksum(
                tau[mo] * dist3.loc[d, r] * product_weight * f3[d, r, mo]
                for d in Dcs for r in Retailers
            )
    Total_Transport_L3 = quicksum(Transport_L3.values()) if Transport_L3 else 0

    Total_Transport = (
        Total_Transport_L1 + Total_Transport_L2 +
        Total_Transport_L2_new + Total_Transport_L3
    )

    # Last-mile cost
    LastMile_Cost = 0
    if f3:
        LastMile_Cost = lastmile_unit_cost * quicksum(
            f3[d, r, mo] for d in Dcs for r in Retailers for mo in ModesL3
        )

    # Handling cost
    Handling_L2 = 0
    if f2:
        Handling_L2 = quicksum(
            handling_crossdock[c] * f2[c, d, mo]
            for c in Crossdocks
            for d in Dcs
            for mo in ModesL2
        )

    Handling_L3 = 0
    if f3:
        Handling_L3 = quicksum(
            handling_dc[d] * f3[d, r, mo]
            for d in Dcs
            for r in Retailers
            for mo in ModesL3
        )

    # Sourcing at plants
    Sourcing_L1 = 0
    if f1:
        Sourcing_L1 = quicksum(
            sourcing_cost[p] * f1[p, c, mo]
            for p in Plants
            for c in Crossdocks
            for mo in ModesL1
        )

    # New location variable + fixed cost
    Cost_NewLoc_var = 0
    if f2_new:
        Cost_NewLoc_var = quicksum(
            new_loc_unitCost[n] * f2_new[n, d, mo]
            for n in New_Locs for d in Dcs for mo in ModesL2
        )

    Cost_NewLoc_fixed = 0
    if f2_2_bin:
        Cost_NewLoc_fixed = quicksum(
            new_loc_openingCost[n] * f2_2_bin[n]
            for n in New_Locs
        )

    Cost_NewLocs = Cost_NewLoc_var + Cost_NewLoc_fixed

    # ---- Inventory cost (transit + safety stock proxy, SC1F-style) ----
    total_demand = sum(demand.values())

    # L1: Plant -> Crossdock
    InvCost_L1 = 0
    if f1:
        InvCost_L1 = quicksum(
            f1[p, c, mo] * (
                df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                + df.loc[mo, "SS (€/unit)"] / total_demand
            )
            for p in Plants for c in Crossdocks for mo in ModesL1
        )

    # L2 (existing): Crossdock -> DC
    InvCost_L2 = 0
    if f2:
        InvCost_L2 = quicksum(
            f2[c, d, mo] * (
                df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                + df.loc[mo, "SS (€/unit)"] / total_demand
            )
            for c in Crossdocks for d in Dcs for mo in ModesL2
        )

    # L2 (new plants): New_Loc -> DC
    InvCost_L2_new = 0
    if f2_new:
        InvCost_L2_new = quicksum(
            f2_new[n, d, mo] * (
                df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                + df.loc[mo, "SS (€/unit)"] / total_demand
            )
            for n in New_Locs for d in Dcs for mo in ModesL2
        )

    # L3: DC -> Retailer
    InvCost_L3 = 0
    if f3:
        InvCost_L3 = quicksum(
            f3[d, r, mo] * (
                df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                + df.loc[mo, "SS (€/unit)"] / total_demand
            )
            for d in Dcs for r in Retailers for mo in ModesL3
        )

    Total_InvCost_Model = InvCost_L1 + InvCost_L2 + InvCost_L2_new + InvCost_L3




    # ---- CO2 emissions ----
    # Production at existing plants
    CO2_prod_L1 = 0
    if f1:
        CO2_prod_L1 = quicksum(
            (co2_prod_kg_per_unit[p] / 1000.0) *
            quicksum(f1[p, c, mo] for c in Crossdocks for mo in ModesL1)
            for p in Plants
        )

    # Production at new locations
    CO2_prod_new = 0
    if f2_new:
        CO2_prod_new = quicksum(
            (new_loc_CO2[n] / 1000.0) *
            quicksum(f2_new[n, d, mo] for d in Dcs for mo in ModesL2)
            for n in New_Locs
        )

    # Transport CO2 by layer/mode
    CO2_tr_L1_by_mode = {}
    if f1:
        for mo in ModesL1:
            CO2_tr_L1_by_mode[mo] = quicksum(
                co2_emission_factor[mo] * dist1.loc[p, c] * product_weight_ton * f1[p, c, mo]
                for p in Plants for c in Crossdocks
            )

    CO2_tr_L2_by_mode = {}
    if f2:
        for mo in ModesL2:
            CO2_tr_L2_by_mode[mo] = quicksum(
                co2_emission_factor[mo] * dist2.loc[c, d] * product_weight_ton * f2[c, d, mo]
                for c in Crossdocks for d in Dcs
            )

    CO2_tr_L2_new_by_mode = {}
    if f2_new:
        for mo in ModesL2:
            CO2_tr_L2_new_by_mode[mo] = quicksum(
                co2_emission_factor[mo] * dist2_new.loc[n, d] * product_weight_ton * f2_new[n, d, mo]
                for n in New_Locs for d in Dcs
            )

    CO2_tr_L3_by_mode = {}
    if f3:
        for mo in ModesL3:
            CO2_tr_L3_by_mode[mo] = quicksum(
                co2_emission_factor[mo] * dist3.loc[d, r] * product_weight_ton * f3[d, r, mo]
                for d in Dcs for r in Retailers
            )

    # Summed by layer
    CO2_tr_L1 = quicksum(CO2_tr_L1_by_mode.values()) if CO2_tr_L1_by_mode else 0
    CO2_tr_L2 = quicksum(CO2_tr_L2_by_mode.values()) if CO2_tr_L2_by_mode else 0
    CO2_tr_L2_new = quicksum(CO2_tr_L2_new_by_mode.values()) if CO2_tr_L2_new_by_mode else 0
    CO2_tr_L3 = quicksum(CO2_tr_L3_by_mode.values()) if CO2_tr_L3_by_mode else 0

    # Last-mile CO2
    LastMile_CO2 = 0
    if f3:
        LastMile_CO2 = (lastmile_CO2_kg / 1000.0) * quicksum(
            f3[d, r, mo] for d in Dcs for r in Retailers for mo in ModesL3
        )

    Total_CO2 = CO2_prod_L1 + CO2_prod_new + CO2_tr_L1 + CO2_tr_L2 + CO2_tr_L2_new + CO2_tr_L3 + LastMile_CO2

    # Simple CO2 cost (manufacturing only, like your original)
    CO2_Mfg_existing = co2_cost_per_ton * CO2_prod_L1
    CO2_Mfg_new = co2_cost_per_ton_New * CO2_prod_new
    CO2_Mfg = CO2_Mfg_existing + CO2_Mfg_new

    # ======================================================
    # 6. CONSTRAINTS
    # ======================================================

    # Demand satisfaction
    if f3:
        model.addConstrs(
            (
                quicksum(f3[d, r, mo] for d in Dcs for mo in ModesL3) >= demand[r]
                for r in Retailers
            ),
            name="Demand",
        )

    # DC balance: inbound from crossdocks + new locs == outbound to retailers
    if f3:
        model.addConstrs(
            (
                quicksum(f2[c, d, mo] for c in Crossdocks for mo in ModesL2) +
                quicksum(f2_new[n, d, mo] for n in New_Locs for mo in ModesL2)
                ==
                quicksum(f3[d, r, mo] for r in Retailers for mo in ModesL3)
                for d in Dcs
            ),
            name="DCBalance",
        )

    # Crossdock balance: inbound from plants == outbound to DCs
    if f1 and f2:
        model.addConstrs(
            (
                quicksum(f1[p, c, mo] for p in Plants for mo in ModesL1)
                ==
                quicksum(f2[c, d, mo] for d in Dcs for mo in ModesL2)
                for c in Crossdocks
            ),
            name="CrossdockBalance",
        )

    # DC capacity
    if f3:
        model.addConstrs(
            (
                quicksum(f3[d, r, mo] for r in Retailers for mo in ModesL3)
                <= dc_capacity[d]
                for d in Dcs
            ),
            name="DCCapacity",
        )

    # New location capacity linking to binary open decision
    if f2_new and f2_2_bin:
        model.addConstrs(
            (
                quicksum(f2_new[n, d, mo] for d in Dcs for mo in ModesL2)
                <= new_loc_capacity[n] * f2_2_bin[n]
                for n in New_Locs
            ),
            name="NewLocCapacity",
        )

    # C02 Enforcement

    model.addConstr(
        Total_CO2 <= CO2_base * (1 - CO_2_percentage),
        name="CO2ReductionTarget"
    )

    model.addConstr(quicksum(f2_2_bin[n] for n in New_Locs) == len(New_Locs))


    # Scenario-specific structural constraints

    # SUEZ CANAL BLOCKADE → block sea on L1
    if suez_canal and f1 and ("sea" in ModesL1):
        model.addConstrs(
            (
                f1[p, c, "sea"] == 0
                for p in Plants for c in Crossdocks
            ),
            name="SeaDamage_f1",
        )

    # VOLCANO: block air on all layers (in addition to mode removal above)
    # If user kept 'air' in some Modes* list, we block via constraints.
    if volcano:
        # L1
        if f1 and "air" in ModesL1:
            model.addConstrs(
                (
                    f1[p, c, "air"] == 0
                    for p in Plants for c in Crossdocks
                ),
                name="Volcano_block_f1",
            )
        # L2 (from crossdocks)
        if f2 and "air" in ModesL2:
            model.addConstrs(
                (
                    f2[c, d, "air"] == 0
                    for c in Crossdocks for d in Dcs
                ),
                name="Volcano_block_f2",
            )
        # L2 (from new locs)
        if f2_new and "air" in ModesL2:
            model.addConstrs(
                (
                    f2_new[n, d, "air"] == 0
                    for n in New_Locs for d in Dcs
                ),
                name="Volcano_block_f2_new",
            )
        # L3
        if f3 and "air" in ModesL3:
            model.addConstrs(
                (
                    f3[d, r, "air"] == 0
                    for d in Dcs for r in Retailers
                ),
                name="Volcano_block_f3",
            )

    # ======================================================
    # 7. OBJECTIVE
    # ======================================================

    model.setObjective(
        Sourcing_L1
        + Handling_L2
        + Handling_L3
        + LastMile_Cost
        + CO2_Mfg
        + Total_Transport
        + Total_InvCost_Model
        + Cost_NewLocs,
        GRB.MINIMIZE,
    )

    # ======================================================
    # 8. SOLVE
    # ======================================================

    model.optimize()

        # ------------------------------
    # FLOW MATRICES (UI için)
    # ------------------------------
    f1_matrix   = print_flows(f1, Plants, Crossdocks, ModesL1, "f1 (Plant → Crossdock)")
    f2_matrix   = print_flows(f2, Crossdocks, Dcs, ModesL2, "f2 (Crossdock → DC)")
    f2_2matrix  = print_flows(f2_new, New_Locs, Dcs, ModesL2, "f2 new (New Locs → DC)")
    f3_matrix   = print_flows(f3, Dcs, Retailers, ModesL3, "f3 (DC → Retailer)")

    # ------------------------------
    # COST / CO2 NUMERICS
    # ------------------------------
    def _safe_val(x):
        try:
            return float(x.getValue())
        except Exception:
            try:
                return float(x)
            except Exception:
                return 0.0

    # Transport totals (MASTER.py’de bunlar var)
    T_L1     = _safe_val(Total_Transport_L1)
    T_L2     = _safe_val(Total_Transport_L2)
    T_L2_new = _safe_val(Total_Transport_L2_new)
    T_L3     = _safe_val(Total_Transport_L3)

    # Inventory (MASTER.py’de InvCost_* var)
    I_L1     = _safe_val(InvCost_L1)
    I_L2     = _safe_val(InvCost_L2)
    I_L2_new = _safe_val(InvCost_L2_new)
    I_L3     = _safe_val(InvCost_L3)

    # Last mile
    LM_cost  = _safe_val(LastMile_Cost)

    # Sourcing & Handling (MASTER.py’de Handling_L2_existing yok)
    S_L1     = _safe_val(Sourcing_L1)
    H_L2     = _safe_val(Handling_L2)
    H_L3     = _safe_val(Handling_L3)

    # New locations: variable + fixed
    FixedCost_NewLocs = _safe_val(Cost_NewLoc_fixed)
    ProdCost_NewLocs  = _safe_val(Cost_NewLoc_var)

    # CO2 parçaları (MASTER.py’de hesaplanıyor)
    E_air        = _safe_val((CO2_tr_L1_by_mode.get("air", 0) if 'CO2_tr_L1_by_mode' in locals() else 0) +
                             (CO2_tr_L2_by_mode.get("air", 0) if 'CO2_tr_L2_by_mode' in locals() else 0) +
                             (CO2_tr_L2_new_by_mode.get("air", 0) if 'CO2_tr_L2_new_by_mode' in locals() else 0) +
                             (CO2_tr_L3_by_mode.get("air", 0) if 'CO2_tr_L3_by_mode' in locals() else 0))

    E_sea        = _safe_val((CO2_tr_L1_by_mode.get("sea", 0) if 'CO2_tr_L1_by_mode' in locals() else 0) +
                             (CO2_tr_L2_by_mode.get("sea", 0) if 'CO2_tr_L2_by_mode' in locals() else 0) +
                             (CO2_tr_L2_new_by_mode.get("sea", 0) if 'CO2_tr_L2_new_by_mode' in locals() else 0) +
                             (CO2_tr_L3_by_mode.get("sea", 0) if 'CO2_tr_L3_by_mode' in locals() else 0))

    E_road       = _safe_val((CO2_tr_L2_by_mode.get("road", 0) if 'CO2_tr_L2_by_mode' in locals() else 0) +
                             (CO2_tr_L2_new_by_mode.get("road", 0) if 'CO2_tr_L2_new_by_mode' in locals() else 0) +
                             (CO2_tr_L3_by_mode.get("road", 0) if 'CO2_tr_L3_by_mode' in locals() else 0))

    E_lastmile   = _safe_val(LastMile_CO2)
    E_production = _safe_val(CO2_prod_L1 + CO2_prod_new)

    CO2_total    = _safe_val(Total_CO2)

    if print_results == "YES":
        print("Transport L1:", T_L1)
        print("Transport L2:", T_L2)
        print("Transport L2 new:", T_L2_new)
        print("Transport L3:", T_L3)

        print("Inventory L1:", I_L1)
        print("Inventory L2:", I_L2)
        print("Inventory L2 new:", I_L2_new)
        print("Inventory L3:", I_L3)

        print("Fixed Last Mile:", LM_cost)

        print(f"Sourcing_L1: {S_L1:,.2f}")
        print(f"Handling_L2_total: {H_L2:,.2f}")
        print(f"Handling_L3: {H_L3:,.2f}")

        print("Fixed new locs:", FixedCost_NewLocs)
        print("Prod new locs:", ProdCost_NewLocs)
        print("CO2 total:", CO2_total)
        print("Total objective:", model.ObjVal)

    results = {
        # --- Flow matrices (UI) ---
        "f1_matrix": f1_matrix,
        "f2_matrix": f2_matrix,
        "f2_2matrix": f2_2matrix,
        "f3_matrix": f3_matrix,

        # --- Transport Costs ---
        "Transport_L1": T_L1,
        "Transport_L2": T_L2,
        "Transport_L2_new": T_L2_new,
        "Transport_L3": T_L3,

        # --- Inventory Costs ---
        "Inventory_L1": I_L1,
        "Inventory_L2": I_L2,
        "Inventory_L2_new": I_L2_new,
        "Inventory_L3": I_L3,

        # --- Last Mile ---
        "Fixed_Last_Mile": LM_cost,

        # --- Sourcing & Handling ---
        "Sourcing_L1": S_L1,
        "Handling_L2_existing": H_L2,   # MASTER.py’de ayrı yok; aynı değeri veriyorum
        "Handling_L2_total": H_L2,
        "Handling_L3": H_L3,

        # --- New Locations & Production ---
        "FixedCost_NewLocs": FixedCost_NewLocs,
        "ProdCost_NewLocs": ProdCost_NewLocs,

        # --- Emission Calculations ---
        "E_air": E_air,
        "E_sea": E_sea,
        "E_road": E_road,
        "E_lastmile": E_lastmile,
        "E_production": E_production,
        "CO2_Total": CO2_total,

        # --- Objective ---
        "Objective_value": model.ObjVal,
        "Status": model.Status,
    }

    return results, model

