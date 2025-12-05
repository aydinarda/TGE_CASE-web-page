# -*- coding: utf-8 -*-
"""
Created on Mon Dec  1 16:42:41 2025

@author: LENOVO
"""

# Scenario_Setting_Master_Parametric.py

# -*- coding: utf-8 -*-
"""
Unified master model for SC1F / SC1F_uns / SC2F / SC2F_uns
Use flags:
  - use_new_locations: True/False   → SC2 vs SC1
  - allow_unmet_demand: True/False  → _uns vs normal

PARAMETRIC VERSION: All locations and transportation modes are parametric.
Students can select locations and modes via function parameters.
"""

from gurobipy import Model, GRB, quicksum
import pandas as pd
import numpy as np
from scipy.stats import norm

from helpers import print_flows  # diğerleri gerekirse eklenir


def run_scenario_master(
    # --- MASTER FLAGS ---
    use_new_locations=True,      # True → SC2, False → SC1
    allow_unmet_demand=True,     # True → _uns versiyonlar

    # --- PARAMETRIC LOCATION & MODE SELECTION ---
    selected_plants=None,           # List of plants to use
    selected_crossdocks=None,       # List of crossdocks to use
    selected_dcs=None,              # List of DCs to use
    selected_retailers=None,        # List of retailers to use
    selected_new_locs=None,         # List of new facilities to use
    selected_modes=None,            # List of transportation modes to use
    selected_modes_l1=None,         # List of modes for layer 1 (defaults to subset of selected_modes)

    # --- ORTAK PARAMETRELER ---
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
    # --- SENARYO EVENTLERİ ---
    suez_canal=False,
    oil_crises=False,
    volcano=False,
    trade_war=False,
    tariff_rate=1.0,
    service_level=0.9,
):
    # =====================================================
    # DEFAULT DATA (SC2F'den aynen alındı)
    # =====================================================
    
    # --- ALL AVAILABLE DATA (used as reference) ---
    ALL_PLANTS = ["TW", "SHA"]
    ALL_CROSSDOCKS = ["ATVIE", "PLGDN", "FRCDG"]
    ALL_NEW_LOCS = ["HUDTG", "CZMCT", "IEILG", "FIMPF", "PLZCA"]
    ALL_DCS = ["PED", "FR6216", "RIX", "GMZ"]
    ALL_RETAILERS = ["FLUXC", "ALKFM", "KSJER", "GXEQH", "OAHLE", "ISNQE", "NAAVF"]
    ALL_MODES = ["air", "sea", "road"]
    ALL_MODES_L1 = ["air", "sea"]
    
    # --- PARAMETRIC SELECTION (defaults to ALL if not specified) ---
    Plants = selected_plants if selected_plants is not None else ALL_PLANTS
    Crossdocks = selected_crossdocks if selected_crossdocks is not None else ALL_CROSSDOCKS
    New_Locs = selected_new_locs if selected_new_locs is not None else ALL_NEW_LOCS
    Dcs = selected_dcs if selected_dcs is not None else ALL_DCS
    Retailers = selected_retailers if selected_retailers is not None else ALL_RETAILERS
    Modes = selected_modes if selected_modes is not None else ALL_MODES
    ModesL1 = selected_modes_l1 if selected_modes_l1 is not None else [m for m in ALL_MODES_L1 if m in Modes]
    
    # --- COMPLETE DEFAULT DATA (all locations) ---
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
    
    # --- PARAMETRIC FILTER (extract only selected locations/modes) ---
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

    service_level_dict = {m: service_level for m in Modes}

    average_distance = 9600
    all_speed = {'air': 800, 'sea': 10, 'road': 40}
    speed = {m: all_speed[m] for m in Modes}
    std_demand = np.std(list(demand.values()))

    if data is None:
        # Build data only for selected modes
        all_data = {
            "transportation": ["air", "sea", "road"],
            "t (€/kg-km)": [0.0105, 0.0013, 0.0054],
        }
        # Filter to selected modes
        mode_indices = {m: i for i, m in enumerate(all_data["transportation"])}
        data = {
            "transportation": Modes,
            "t (€/kg-km)": [all_data["t (€/kg-km)"][mode_indices[m]] for m in Modes],
        }

    # Holding cost (hepsi aynı) – adapt to selected modes
    data["h (€/unit)"] = [unit_inventory_holdingCost] * len(Modes)

    # Lead time – adapted to selected modes
    data["LT (days)"] = [
        np.round((average_distance * (1.2 if m == "sea" else 1)) / (speed[m] * 24), 13)
        for m in Modes
    ]

    # Z-score ve yoğunluk
    z_values = [norm.ppf(alpha) for alpha in [service_level_dict[m] for m in Modes]]
    phi_values = [norm.pdf(z) for z in z_values]

    data["Z-score Φ^-1(α)"] = z_values
    data["Density φ(Φ^-1(α))"] = phi_values

    # SS (€/unit) – all modes data, will filter when needed
    all_SS = [2109.25627631292, 12055.4037653689, 5711.89299799521]
    all_modes_list = ["air", "sea", "road"]
    mode_to_ss = {m: all_SS[i] for i, m in enumerate(all_modes_list)}
    data["SS (€/unit)"] = [mode_to_ss[m] for m in Modes]

    product_weight_ton = product_weight / 1000.0

    df = pd.DataFrame(data).set_index("transportation")
    tau = df["t (€/kg-km)"].to_dict()

    new_loc_totalCost = {
        loc: new_loc_openingCost[loc] + new_loc_operationCost[loc]
        for loc in new_loc_openingCost
    }
    new_loc_unitCost = {
        loc: (1 / cap) * 100000
        for loc, cap in new_loc_capacity.items()
    }

    # ===== MESAFELER ===== (SC2F / SC1F ile aynı, all possibilities)
    # Students will use only rows/cols corresponding to selected locations
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
    
    # --- USE PARAMETRIC DISTANCE MATRICES OR DEFAULTS ---
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
    # MODEL
    # =====================================================
    model = Model("Unified_SC_Model")

    # Akış değişkenleri
    f1 = model.addVars(
        ((p, c, mo) for p in Plants for c in Crossdocks for mo in ModesL1),
        lb=0, name="f1"
    )  # Plant → Crossdock

    f2 = model.addVars(
        ((c, d, mo) for c in Crossdocks for d in Dcs for mo in Modes),
        lb=0, name="f2"
    )  # Crossdock → DC

    # Yeni tesis akışları (her zaman tanımla, ama flag ile aç/kapat)
    f2_2 = model.addVars(
        ((c, d, mo) for c in New_Locs for d in Dcs for mo in Modes),
        lb=0, name="f2_2"
    )  # NewLoc → DC

    f2_2_bin = model.addVars(New_Locs, vtype=GRB.BINARY, name="f2_2_bin")

    f3 = model.addVars(
        ((d, r, mo) for d in Dcs for r in Retailers for mo in Modes),
        lb=0, name="f3"
    )  # DC → Retailer

    # Slack değişkenleri (unmet demand)
    v = model.addVars(Retailers, name="v", lb=0)

    # =====================================================
    # CO2 HESAPLARI
    # =====================================================
    # Transport CO2
    CO2_tr_L1 = quicksum(
        co2_emission_factor[mo] * dist1.loc[p, c] * product_weight_ton * f1[p, c, mo]
        for p in Plants for c in Crossdocks for mo in ModesL1
    )

    CO2_tr_L2 = quicksum(
        co2_emission_factor[mo] * dist2.loc[c, d] * product_weight_ton * f2[c, d, mo]
        for c in Crossdocks for d in Dcs for mo in Modes
    )

    CO2_tr_L2_2 = quicksum(
        co2_emission_factor[mo] * dist2_2.loc[c, d] * product_weight_ton * f2_2[c, d, mo]
        for c in New_Locs for d in Dcs for mo in Modes
    )

    CO2_tr_L3 = quicksum(
        co2_emission_factor[mo] * dist3.loc[d, r] * product_weight_ton * f3[d, r, mo]
        for d in Dcs for r in Retailers for mo in Modes
    )

    # Production CO2
    CO2_prod_L1 = quicksum(
        co2_prod_kg_per_unit[p] *
        quicksum(f1[p, c, mo] for c in Crossdocks for mo in ModesL1)
        for p in Plants
    ) / 1000.0

    CO2_prod_L2_2 = quicksum(
        new_loc_CO2[c] * quicksum(f2_2[c, d, mo] for d in Dcs for mo in Modes)
        for c in New_Locs
    ) / 1000.0

    LastMile_CO2 = (lastmile_CO2_kg / 1000) * quicksum(
        f3[d, r, mo] for d in Dcs for r in Retailers for mo in Modes
    )

    Total_CO2 = (
        CO2_prod_L1 + CO2_prod_L2_2 +
        CO2_tr_L1 + CO2_tr_L2 + CO2_tr_L2_2 + CO2_tr_L3 +
        LastMile_CO2
    )

    # Mod bazında ayırımlar (emisyon dağılımı)
    CO2_tr_L1_by_mode = {
        mo: quicksum(
            co2_emission_factor[mo] * dist1.loc[p, c] * product_weight_ton * f1[p, c, mo]
            for p in Plants for c in Crossdocks
        )
        for mo in ModesL1
    }
    
    CO2_tr_L2_by_mode = {
        mo: quicksum(
            co2_emission_factor[mo] * dist2.loc[c, d] * product_weight_ton * f2[c, d, mo]
            for c in Crossdocks for d in Dcs
        )
        for mo in Modes
    }
    
    CO2_tr_L3_by_mode = {
        mo: quicksum(
            co2_emission_factor[mo] * dist3.loc[d, r] * product_weight_ton * f3[d, r, mo]
            for d in Dcs for r in Retailers
        )
        for mo in Modes
    }

    # =====================================================
    # MALİYETLER
    # =====================================================
    # Transport
    Transport_L1 = {
        mo: quicksum(
            tau[mo] * dist1.loc[p, c] * product_weight * f1[p, c, mo]
            for p in Plants for c in Crossdocks
        )
        for mo in ModesL1
    }
    Total_Transport_L1 = quicksum(Transport_L1[mo] for mo in ModesL1)

    Transport_L2 = {
        mo: quicksum(
            tau[mo] * dist2.loc[c, d] * product_weight * f2[c, d, mo]
            for c in Crossdocks for d in Dcs
        )
        for mo in Modes
    }

    Transport_L2_2 = {
        mo: quicksum(
            tau[mo] * dist2_2.loc[c, d] * product_weight * f2_2[c, d, mo]
            for c in New_Locs for d in Dcs
        )
        for mo in Modes
    }

    Total_Transport_L2 = quicksum(Transport_L2[mo] for mo in Modes) + \
        quicksum(Transport_L2_2[mo] for mo in Modes)

    Transport_L3 = {
        mo: quicksum(
            tau[mo] * dist3.loc[d, r] * product_weight * f3[d, r, mo]
            for d in Dcs for r in Retailers
        )
        for mo in Modes
    }
    Total_Transport_L3 = quicksum(Transport_L3[mo] for mo in Modes)

    Total_Transport = Total_Transport_L1 + Total_Transport_L2 + Total_Transport_L3

    # Envanter
    InvCost_L1 = {
        mo: (
            quicksum(
                f1[p, c, mo] * df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                for p in Plants for c in Crossdocks
            )
            + quicksum(
                f1[p, c, mo] * df.loc[mo, "SS (€/unit)"] / sum(demand.values())
                for p in Plants for c in Crossdocks
            )
        )
        for mo in ModesL1
    }
    Total_InvCost_L1 = quicksum(InvCost_L1[mo] for mo in ModesL1)

    InvCost_L2 = {
        mo: (
            quicksum(
                f2[c, d, mo] * df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                for c in Crossdocks for d in Dcs
            )
            + quicksum(
                f2[c, d, mo] * df.loc[mo, "SS (€/unit)"] / sum(demand.values())
                for c in Crossdocks for d in Dcs
            )
        )
        for mo in Modes
    }
    Total_InvCost_L2 = quicksum(InvCost_L2[mo] for mo in Modes)

    InvCost_L2_2 = {
        mo: (
            quicksum(
                f2_2[c, d, mo] * df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                for c in New_Locs for d in Dcs
            )
            + quicksum(
                f2_2[c, d, mo] * df.loc[mo, "SS (€/unit)"] / sum(demand.values())
                for c in New_Locs for d in Dcs
            )
        )
        for mo in Modes
    }
    Total_InvCost_L2_2 = quicksum(InvCost_L2_2[mo] for mo in Modes)

    InvCost_L3 = {
        mo: (
            quicksum(
                f3[d, r, mo] * df.loc[mo, "LT (days)"] * df.loc[mo, "h (€/unit)"]
                for d in Dcs for r in Retailers
            )
            + quicksum(
                f3[d, r, mo] * df.loc[mo, "SS (€/unit)"] / sum(demand.values())
                for d in Dcs for r in Retailers
            )
        )
        for mo in Modes
    }
    Total_InvCost_L3 = quicksum(InvCost_L3[mo] for mo in Modes)

    Total_InvCost_Model = Total_InvCost_L1 + Total_InvCost_L2 + Total_InvCost_L2_2 + Total_InvCost_L3

    # Sourcing & handling
    Sourcing_L1 = quicksum(
        sourcing_cost[p] *
        quicksum(f1[p, c, mo] for c in Crossdocks for mo in ModesL1)
        for p in Plants
    )

    Handling_L2_existing = quicksum(
        handling_crossdock[c] *
        quicksum(f2[c, d, mo] for d in Dcs for mo in Modes)
        for c in Crossdocks
    )
    Handling_L2 = Handling_L2_existing

    Handling_L3 = quicksum(
        handling_dc[d] *
        quicksum(f3[d, r, mo] for r in Retailers for mo in Modes)
        for d in Dcs
    )

    # CO2 maliyetleri
    CO2_Mfg = co2_cost_per_ton / 1000 * quicksum(
        co2_prod_kg_per_unit[p] *
        quicksum(f1[p, c, mo] for c in Crossdocks for mo in ModesL1)
        for p in Plants
    )

    CO2Cost_L2_2 = quicksum(
        new_loc_CO2[c] *
        quicksum(f2_2[c, d, mo] for d in Dcs for mo in Modes) *
        (co2_cost_per_ton_New / 1000)
        for c in New_Locs
    )

    LastMile_Cost = lastmile_unit_cost * quicksum(
        f3[d, r, mo] for d in Dcs for r in Retailers for mo in Modes
    )

    # Yeni tesis sabit + değişken maliyeti
    FixedCost_NewLocs = quicksum(
        new_loc_totalCost[c] * f2_2_bin[c]
        for c in New_Locs
    )
    ProdCost_NewLocs = quicksum(
        new_loc_unitCost[c] *
        quicksum(f2_2[c, d, mo] for d in Dcs for mo in Modes)
        for c in New_Locs
    )
    Cost_NewLocs = FixedCost_NewLocs + ProdCost_NewLocs

    # =====================================================
    # KISITLAR
    # =====================================================

    # Talep kısıtı: equality + opsiyonel slack
    if allow_unmet_demand:
        model.addConstrs(
            (quicksum(f3[d, r, mo] for d in Dcs for mo in Modes) + v[r] == demand[r]
             for r in Retailers),
            name="DemandWithSlack"
        )
    else:
        model.addConstrs(
            (quicksum(f3[d, r, mo] for d in Dcs for mo in Modes) == demand[r]
             for r in Retailers),
            name="DemandNoSlack"
        )
        model.addConstrs((v[r] == 0 for r in Retailers), name="NoUnmetDemand")

    # DC balansı
    model.addConstrs(
        (
            quicksum(f2[c, d, mo] for c in Crossdocks for mo in Modes) +
            quicksum(f2_2[c, d, mo] for c in New_Locs for mo in Modes)
            == quicksum(f3[d, r, mo] for r in Retailers for mo in Modes)
            for d in Dcs
        ),
        name="DCBalance"
    )

    # Crossdock balansı
    model.addConstrs(
        (quicksum(f1[p, c, mo] for p in Plants for mo in ModesL1) ==
         quicksum(f2[c, d, mo] for d in Dcs for mo in Modes)
         for c in Crossdocks),
        name="CrossdockBalance"
    )

    # Yeni tesis kapasite
    model.addConstrs(
        (
            quicksum(f2_2[c, d, mo] for d in Dcs for mo in Modes)
            <= new_loc_capacity[c] * f2_2_bin[c]
            for c in New_Locs
        ),
        name="NewFacilityCapacity"
    )

    # DC kapasite
    model.addConstrs(
        (
            quicksum(f3[d, r, mo] for r in Retailers for mo in Modes)
            <= dc_capacity[d]
            for d in Dcs
        ),
        name="DCCapacity"
    )

    # CO2 hedefi
    model.addConstr(
        Total_CO2 <= CO2_base * (1 - CO_2_percentage),
        name="CO2ReductionTarget"
    )

    # Eğer yeni tesisler açılmasın isteniyorsa → komple kapat
    if not use_new_locations:
        model.addConstrs((f2_2_bin[c] == 0 for c in New_Locs), name="NoNewLocBin")
        model.addConstrs(
            (f2_2[c, d, mo] == 0
             for c in New_Locs for d in Dcs for mo in Modes),
            name="NoNewLocFlows"
        )

    # =====================================================
    # SCENARIO: EVENTS
    # =====================================================

    # Suez kanal krizi → sea layer-1 kapalı
    if suez_canal:
        model.addConstrs(
            (f1[p, c, "sea"] == 0
             for p in Plants for c in Crossdocks),
            name="SeaDamage_f1"
        )

    # Oil crisis → tüm transport + last-mile 1.3x
    if oil_crises:
        Total_Transport = Total_Transport * 1.3
        LastMile_Cost = LastMile_Cost * 1.3

    # Volcano → tüm air modları kapalı
    if volcano:
        # L1
        model.addConstrs(
            (f1[p, c, "air"] == 0
             for p in Plants for c in Crossdocks),
            name="Volcano_block_f1"
        )
        # L2
        model.addConstrs(
            (f2[c, d, "air"] == 0
             for c in Crossdocks for d in Dcs),
            name="Volcano_block_f2"
        )
        # L2_2 (new loc)
        model.addConstrs(
            (f2_2[c, d, "air"] == 0
             for c in New_Locs for d in Dcs),
            name="Volcano_block_f2_2"
        )
        # L3
        model.addConstrs(
            (f3[d, r, "air"] == 0
             for d in Dcs for r in Retailers),
            name="Volcano_block_f3"
        )

    # Trade war → sourcing cost ↑
    if trade_war:
        Sourcing_L1 = Sourcing_L1 * tariff_rate

    # Big-M cezası
    M = 1e8 if allow_unmet_demand else 0
    penalty_term = M * quicksum(v[r] for r in Retailers)

    # =====================================================
    # OBJECTIVE
    # =====================================================
    model.setObjective(
        Sourcing_L1
        + Handling_L2
        + Handling_L3
        + LastMile_Cost
        + CO2_Mfg
        + Total_Transport
        + Total_InvCost_Model
        + CO2Cost_L2_2
        + Cost_NewLocs
        + penalty_term,
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
    f2_matrix = print_flows(f2, Crossdocks, Dcs, Modes, "f2 (Crossdock → DC)")
    f2_2_matrix = print_flows(f2_2, New_Locs, Dcs, Modes, "f2_2 (NewLoc → DC)")
    f3_matrix = print_flows(f3, Dcs, Retailers, Modes, "f3 (DC → Retailer)")

    if print_results == "YES":
        print("Transport L1:", sum(Transport_L1[mo].getValue() for mo in ModesL1))
        print("Transport L2:", sum(Transport_L2[mo].getValue() for mo in Modes))
        print("Transport L2 new:", sum(Transport_L2_2[mo].getValue() for mo in Modes))
        print("Transport L3:", sum(Transport_L3[mo].getValue() for mo in Modes))

        print("Inventory L1:", Total_InvCost_L1.getValue())
        print("Inventory L2:", Total_InvCost_L2.getValue())
        print("Inventory L2 new:", Total_InvCost_L2_2.getValue())
        print("Inventory L3:", Total_InvCost_L3.getValue())

        print("Fixed Last Mile:", LastMile_Cost.getValue())
        print("CO2 Cost L2_2:", CO2Cost_L2_2.getValue())
        print("CO2 Manufacturing:", CO2_Mfg.getValue())

        print("Sourcing_L1:", Sourcing_L1.getValue())
        print("Handling_L2_existing:", Handling_L2_existing.getValue())
        print("Handling_L2 (total):", Handling_L2.getValue())
        print("Handling_L3:", Handling_L3.getValue())

        print("Fixed new locs:", FixedCost_NewLocs.getValue())
        print("Prod new locs:", ProdCost_NewLocs.getValue())
        print("CO2 total:", Total_CO2.getValue())
        print("Total objective:", model.ObjVal)

    # Emission breakdown by mode (adapted to selected modes)
    E_by_mode = {}
    for mo in Modes:
        e_val = 0
        if mo in CO2_tr_L1_by_mode:
            e_val += CO2_tr_L1_by_mode[mo].getValue()
        if mo in CO2_tr_L2_by_mode:
            e_val += CO2_tr_L2_by_mode[mo].getValue()
        if mo in CO2_tr_L3_by_mode:
            e_val += CO2_tr_L3_by_mode[mo].getValue()
        E_by_mode[mo] = e_val

    E_lastmile = LastMile_CO2.getValue()
    E_production = CO2_prod_L1.getValue()

    U = sum(v[r].X for r in Retailers)
    D_tot = sum(demand[r] for r in Retailers)
    satisfied_units = D_tot - U
    satisfied_pct = satisfied_units / D_tot if D_tot > 0 else 1.0

    # Öğrenci value-gap hesapları için penalty'i geri çıkarılmış "ekonomik" objective
    adjusted_objective = model.ObjVal - penalty_term.getValue() if allow_unmet_demand else model.ObjVal

    results = {
        "Transport_L1": sum(Transport_L1[mo].getValue() for mo in ModesL1),
        "Transport_L2": sum(Transport_L2[mo].getValue() for mo in Modes),
        "Transport_L2_new": sum(Transport_L2_2[mo].getValue() for mo in Modes),
        "Transport_L3": sum(Transport_L3[mo].getValue() for mo in Modes),

        "Inventory_L1": Total_InvCost_L1.getValue(),
        "Inventory_L2": Total_InvCost_L2.getValue(),
        "Inventory_L2_new": Total_InvCost_L2_2.getValue(),
        "Inventory_L3": Total_InvCost_L3.getValue(),

        "Fixed_Last_Mile": LastMile_Cost.getValue(),
        "CO2_Cost_L2_2": CO2Cost_L2_2.getValue(),
        "CO2_Manufacturing": CO2_Mfg.getValue(),
        "CO2_Total": Total_CO2.getValue(),

        "Sourcing_L1": Sourcing_L1.getValue(),
        "Handling_L2_existing": Handling_L2_existing.getValue(),
        "Handling_L2_total": Handling_L2.getValue(),
        "Handling_L3": Handling_L3.getValue(),

        "FixedCost_NewLocs": FixedCost_NewLocs.getValue(),
        "ProdCost_NewLocs": ProdCost_NewLocs.getValue(),

        "E_by_mode": E_by_mode,
        "E_lastmile": E_lastmile,
        "E_production": E_production,

        "Objective_value": adjusted_objective,
        "Satisfied_Demand_pct": satisfied_pct,
        "Satisfied_Demand_units": satisfied_units,
        "Unmet_Demand_units": U,

        "Selected_Plants": Plants,
        "Selected_Crossdocks": Crossdocks,
        "Selected_DCs": Dcs,
        "Selected_Retailers": Retailers,
        "Selected_New_Locs": New_Locs,
        "Selected_Modes": Modes,
        "Selected_Modes_L1": ModesL1,
    }

    return results, model
