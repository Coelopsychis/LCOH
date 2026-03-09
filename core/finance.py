from __future__ import annotations

import numpy as np

from core.models import ModelInputs
from core.simulation import compute_operation_kpis


def annuity_factor(rate: float, years: int) -> float:
    if years <= 0:
        return 0.0
    if rate == 0:
        return 1.0 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def compute_capex(inputs: ModelInputs) -> dict:
    s = inputs.system
    c = inputs.capex

    base_specific = (
        c.electrolyzer_specific_eur_per_kw
        + c.bop_specific_eur_per_kw
        + c.infrastructure_specific_eur_per_kw
    )

    direct_capex = s.electrolyzer_power_kw * base_specific
    development_cost = direct_capex * c.development_share
    total_capex = direct_capex + development_cost
    replacement_cost = s.electrolyzer_power_kw * c.stack_replacement_specific_eur_per_kw

    return {
        "direct_capex_eur": direct_capex,
        "development_cost_eur": development_cost,
        "total_capex_eur": total_capex,
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

    maintenance = capex["total_capex_eur"] * o.maintenance_share_of_capex
    water = annual_h2_kg * o.water_eur_per_kg_h2
    fixed = o.personnel_eur_per_year + o.other_fixed_opex_eur_per_year

    return {
        "maintenance_eur_per_year": maintenance,
        "water_eur_per_year": water,
        "fixed_opex_eur_per_year": fixed,
        "total_opex_eur_per_year": maintenance + water + fixed,
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
        lcoh_eur_per_kg * inputs.system.kwh_h2_per_kg
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