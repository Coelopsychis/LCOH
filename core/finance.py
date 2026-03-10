from __future__ import annotations

import numpy as np

from core.models import ModelInputs
from core.simulation import compute_operation_kpis
from core.constants import KWH_PER_KG_H2


def annuity_factor(rate: float, years: int) -> float:
    if years <= 0:
        return 0.0
    if rate == 0:
        return 1.0 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def compute_capex(inputs: ModelInputs) -> dict:
    s = inputs.system
    c = inputs.capex

    ely_kw = s.electrolyzer_power_kw
    system_kw = s.system_power_kw

    # Allgemeine CAPEX
    epc_cost = ely_kw * c.epc_eur_per_kw
    bop_cost = ely_kw * c.bop_eur_per_kw
    hochbau_cost = ely_kw * c.hochbau_eur_per_kw
    tiefbau_cost = ely_kw * c.tiefbau_eur_per_kw
    individual_specific_cost = ely_kw * c.individual_specific_eur_per_kw
    individual_fixed_cost = c.individual_fixed_eur

    # Optionale Systeme
    waste_heat_cost = ely_kw * c.waste_heat_system_eur_per_kw if c.waste_heat_enabled else 0.0
    oxygen_cost = ely_kw * c.oxygen_system_eur_per_kw if c.oxygen_enabled else 0.0
    compressor_cost = ely_kw * c.compressor_system_eur_per_kw if c.compression_enabled else 0.0

    # Batteriesystem:
    # installierte Speicherkapazität = Faktor [kWh/kW System] * Systemleistung [kW]
    battery_capacity_kwh = (
        c.battery_capacity_factor_kwh_per_kw * system_kw
        if c.battery_enabled else 0.0
    )
    battery_cost = (
        battery_capacity_kwh * c.battery_invest_eur_per_kwh
        if c.battery_enabled else 0.0
    )

    direct_capex = (
        epc_cost
        + bop_cost
        + hochbau_cost
        + tiefbau_cost
        + individual_specific_cost
        + individual_fixed_cost
        + waste_heat_cost
        + oxygen_cost
        + compressor_cost
        + battery_cost
    )

    replacement_cost = s.electrolyzer_power_kw * c.stack_replacement_specific_eur_per_kw
    
    return {
        "epc_cost_eur": epc_cost,
        "bop_cost_eur": bop_cost,
        "hochbau_cost_eur": hochbau_cost,
        "tiefbau_cost_eur": tiefbau_cost,
        "individual_specific_cost_eur": individual_specific_cost,
        "individual_fixed_cost_eur": individual_fixed_cost,
        "waste_heat_cost_eur": waste_heat_cost,
        "oxygen_cost_eur": oxygen_cost,
        "compressor_cost_eur": compressor_cost,
        "battery_capacity_kwh": battery_capacity_kwh,
        "battery_cost_eur": battery_cost,
        "direct_capex_eur": direct_capex,
        "total_capex_eur": direct_capex,
        "stack_replacement_cost_eur": replacement_cost,
    }


def compute_annualized_capex(inputs: ModelInputs, capex: dict) -> dict:
    s = inputs.system
    c = inputs.capex

    a = annuity_factor(c.discount_rate, s.project_lifetime_years)
    annualized_capex = capex["total_capex_eur"] * a

    replacement_annual_eur = 0.0
    if s.stack_lifetime_years > 0:
        replacement_annual_eur = capex["stack_replacement_cost_eur"] / s.stack_lifetime_years

    return {
        "annuity_factor": a,
        "annualized_capex_eur_per_year": annualized_capex,
        "stack_replacement_eur_per_year": replacement_annual_eur,
    }


def compute_opex(inputs: ModelInputs, capex: dict, annual_h2_kg: float) -> dict:
    o = inputs.opex

    capex_total = capex["total_capex_eur"]

    # 1) Wartung & Instandhaltung
    maintenance = capex_total * o.maintenance_share_of_capex

    # 2) Personalkosten
    personnel = o.personnel_eur_per_year

    # 3) Rückstellungen
    reserve_remaining_plant = capex_total * o.reserve_remaining_plant_share_of_capex
    reserve_decommissioning = capex_total * o.reserve_decommissioning_share_of_capex
    reserves_total = reserve_remaining_plant + reserve_decommissioning

    # 4) Wasser
    # Vereinfachte Annahme:
    # 1 kg H2 benötigt ca. 9 Liter Wasser = 0.009 m³/kg
    water_demand_m3_per_kg_h2 = 0.009
    annual_water_m3 = annual_h2_kg * water_demand_m3_per_kg_h2

    water_cost_per_m3 = (
        o.freshwater_price_eur_per_m3
        + o.freshwater_treatment_price_eur_per_m3
        + o.wastewater_price_eur_per_m3
    )
    water_total = annual_water_m3 * water_cost_per_m3

    # 5) Individuelle OPEX
    individual_opex = capex_total * o.individual_opex_share_of_capex

    total_opex = (
        maintenance
        + personnel
        + reserves_total
        + water_total
        + individual_opex
    )

    return {
        # Wartung
        "maintenance_eur_per_year": maintenance,
        "maintenance_escalation_per_year": o.maintenance_escalation_per_year,

        # Personal
        "personnel_eur_per_year": personnel,
        "personnel_escalation_per_year": o.personnel_escalation_per_year,

        # Rückstellungen
        "reserve_remaining_plant_eur_per_year": reserve_remaining_plant,
        "reserve_decommissioning_eur_per_year": reserve_decommissioning,
        "reserves_total_eur_per_year": reserves_total,
        "reserve_escalation_per_year": o.reserve_escalation_per_year,

        # Wasser
        "annual_water_demand_m3": annual_water_m3,
        "water_cost_per_m3": water_cost_per_m3,
        "water_eur_per_year": water_total,
        "water_escalation_per_year": o.water_escalation_per_year,

        # Individuelle OPEX
        "individual_opex_eur_per_year": individual_opex,
        "individual_opex_escalation_per_year": o.individual_opex_escalation_per_year,

        # Gesamt
        "total_opex_eur_per_year": total_opex,
    }


def compute_lcoh(inputs: ModelInputs, dispatch) -> dict:
    capex = compute_capex(inputs)
    annualized_capex = compute_annualized_capex(inputs, capex)
    op_kpis = compute_operation_kpis(inputs, dispatch)
    opex = compute_opex(inputs, capex, op_kpis["annual_h2_kg"])

    annual_costs = (
        annualized_capex["annualized_capex_eur_per_year"]
        + annualized_capex["stack_replacement_eur_per_year"]
        + opex["total_opex_eur_per_year"]
        + op_kpis["annual_spot_cost_eur"]
    )

    annual_h2_kg = op_kpis["annual_h2_kg"]
    lcoh_eur_per_kg = annual_costs / annual_h2_kg if annual_h2_kg > 0 else np.nan
    lcoh_ct_per_kwh = (
        lcoh_eur_per_kg * KWH_PER_KG_H2
        if np.isfinite(lcoh_eur_per_kg)
        else np.nan
    )

    return {
        **capex,
        **annualized_capex,
        **opex,
        **op_kpis,
        "annual_costs_eur_per_year": annual_costs,
        "lcoh_eur_per_kg": lcoh_eur_per_kg,
        "lcoh_ct_per_kwh": lcoh_ct_per_kwh,
    }