from __future__ import annotations

import math
import numpy as np

from core.models import ModelInputs
from core.simulation import compute_operation_kpis
from core.constants import KWH_PER_KG_H2
from core.technical import (
    O2_KG_PER_KG_H2,
    KG_PER_TONNE,
    compute_processing_design,
    compute_stack_schedule,
    compute_average_efficiency,
)


def annuity_factor(rate: float, years: float) -> float:
    """Return the standard annuity factor for a constant annual interest rate."""
    if years <= 0:
        return 0.0
    if rate == 0:
        return 1.0 / years
    return rate * (1.0 + rate) ** years / ((1.0 + rate) ** years - 1.0)


def average_escalated_value(base_value: float, escalation: float, years: int) -> float:
    """
    Return the average nominal value over the project lifetime:

        base / years * (((1 + escalation) ** years - 1) / escalation)

    For zero escalation the base value is returned unchanged.
    """
    if years <= 0:
        return 0.0
    if escalation == 0:
        return base_value
    return base_value / years * (((1.0 + escalation) ** years - 1.0) / escalation)


def compute_capex_subsidy(inputs: ModelInputs, gross_capex_eur: float) -> dict:
    """Calculate total CAPEX subsidy and its straight-line annual equivalent."""
    f = inputs.funding
    ely_kw = inputs.system.electrolyzer_power_kw
    years = inputs.system.project_lifetime_years

    if f.capex_mode == "percentage":
        total = f.capex_percentage * gross_capex_eur
    elif f.capex_mode == "absolute":
        total = f.capex_absolute_eur_per_kw * ely_kw
    else:
        total = 0.0

    annual = total / years if years > 0 else 0.0
    return {
        "capex_subsidy_total_eur": total,
        "capex_subsidy_eur_per_year": annual,
    }


def compute_opex_subsidy(
    inputs: ModelInputs, annual_h2_kg: float, equivalent_full_load_hours: float
) -> float:
    """Calculate the annual OPEX subsidy from the selected funding basis."""
    f = inputs.funding
    if f.opex_mode == "per_kg":
        return annual_h2_kg * f.opex_eur_per_kg_h2
    if f.opex_mode == "per_full_load_hour":
        return equivalent_full_load_hours * f.opex_eur_per_full_load_hour
    return 0.0


def compute_electricity_subsidy(inputs: ModelInputs, op_kpis: dict) -> float:
    """Calculate the annual electricity subsidy from H₂ output or system consumption."""
    f = inputs.funding
    if f.electricity_mode == "per_kg":
        return op_kpis["annual_h2_kg"] * f.electricity_eur_per_kg_h2
    if f.electricity_mode == "per_mwh":
        # The MWh-based subsidy applies to consumed system electricity, not gross procurement.
        return op_kpis["annual_system_mwh"] * f.electricity_eur_per_mwh
    return 0.0


def compute_strompreiskompensation(inputs: ModelInputs, op_kpis: dict) -> dict:
    """Calculate Strompreiskompensation (SPK) from EUA price and eligible consumption."""
    f = inputs.funding
    years = inputs.system.project_lifetime_years

    avg_eua = average_escalated_value(
        f.spk_eua_price_eur_per_tco2, f.spk_price_escalation_per_year, years
    )
    separate_avg = average_escalated_value(
        f.spk_separate_revenue_eur_per_year,
        f.spk_price_escalation_per_year,
        years,
    )

    # Fixed policy factors used by the SPK calculation.
    aid_intensity = 0.75
    co2_factor_t_per_mwh = 0.72
    fallback_factor = (0.8 + (0.8 - 0.0109 * years)) / 2.0
    eligible_consumption_mwh = (
        op_kpis["annual_system_mwh"] * f.spk_power_consumption_factor
    )
    calculated = (
        aid_intensity
        * co2_factor_t_per_mwh
        * avg_eua
        * fallback_factor
        * eligible_consumption_mwh
    )

    if f.spk_mode == "calculator":
        revenue = calculated
    elif f.spk_mode == "separate":
        revenue = separate_avg
    else:
        revenue = 0.0

    return {
        "spk_revenue_eur_per_year": revenue,
        "spk_calculated_revenue_eur_per_year": calculated,
        "spk_separate_average_eur_per_year": separate_avg,
        "spk_average_eua_price_eur_per_tco2": avg_eua,
        "spk_fallback_factor": fallback_factor,
        "spk_eligible_consumption_mwh_per_year": eligible_consumption_mwh,
        "spk_aid_intensity": aid_intensity,
        "spk_co2_factor_t_per_mwh": co2_factor_t_per_mwh,
    }


def compute_capex(
    inputs: ModelInputs, average_efficiency: float | None = None
) -> dict:
    s = inputs.system
    c = inputs.capex
    ely_kw = s.electrolyzer_power_kw
    processing_efficiency = (
        s.avg_efficiency_h2_per_el
        if average_efficiency is None
        else float(average_efficiency)
    )
    design = compute_processing_design(inputs, processing_efficiency)

    electrolyzer_cost = ely_kw * c.electrolyzer_invest_eur_per_kw
    epc_cost = ely_kw * c.epc_eur_per_kw
    bop_cost = ely_kw * c.bop_eur_per_kw
    hochbau_cost = ely_kw * c.hochbau_eur_per_kw
    tiefbau_cost = ely_kw * c.tiefbau_eur_per_kw

    individual_specific_total_eur_per_kw = (
        c.individual_specific_eur_per_kw
        + c.individual_ely_cost_share * c.electrolyzer_invest_eur_per_kw
        + (c.individual_fixed_eur / ely_kw if ely_kw > 0 else 0.0)
    )
    individual_specific_cost = ely_kw * individual_specific_total_eur_per_kw

    waste_heat_cost = (
        ely_kw * c.waste_heat_system_eur_per_kw if c.waste_heat_enabled else 0.0
    )
    oxygen_cost = (
        ely_kw * c.oxygen_system_eur_per_kw if c.oxygen_enabled else 0.0
    )

    h2_treatment_specific = (
        c.compressor_system_eur_per_kw
        if c.compression_enabled
        else c.h2_direct_system_eur_per_kw
    )
    h2_treatment_cost = ely_kw * h2_treatment_specific

    # Battery capacity uses rounded-up installed system power times the capacity factor.
    battery_system_power_kw = (
        float(math.ceil(design["system_power_kw"])) if c.battery_enabled else 0.0
    )
    battery_capacity_kwh = (
        c.battery_capacity_factor_kwh_per_kw * battery_system_power_kw
        if c.battery_enabled
        else 0.0
    )
    battery_cost = (
        battery_capacity_kwh * c.battery_invest_eur_per_kwh + c.battery_fixed_eur
        if c.battery_enabled
        else 0.0
    )

    gross_capex = (
        electrolyzer_cost
        + epc_cost
        + bop_cost
        + hochbau_cost
        + tiefbau_cost
        + individual_specific_cost
        + waste_heat_cost
        + oxygen_cost
        + h2_treatment_cost
        + battery_cost
    )
    capex_subsidy = compute_capex_subsidy(inputs, gross_capex)
    total_capex = gross_capex - capex_subsidy["capex_subsidy_total_eur"]

    return {
        **capex_subsidy,
        "electrolyzer_cost_eur": electrolyzer_cost,
        "epc_cost_eur": epc_cost,
        "bop_cost_eur": bop_cost,
        "hochbau_cost_eur": hochbau_cost,
        "tiefbau_cost_eur": tiefbau_cost,
        "individual_specific_total_eur_per_kw": individual_specific_total_eur_per_kw,
        "individual_specific_cost_eur": individual_specific_cost,
        "individual_fixed_cost_eur": c.individual_fixed_eur,
        "waste_heat_cost_eur": waste_heat_cost,
        "oxygen_cost_eur": oxygen_cost,
        "compressor_cost_eur": h2_treatment_cost if c.compression_enabled else 0.0,
        "h2_direct_system_cost_eur": h2_treatment_cost if not c.compression_enabled else 0.0,
        "h2_treatment_cost_eur": h2_treatment_cost,
        "installed_system_power_kw": design["system_power_kw"],
        "peripheral_power_kw": design["peripheral_power_kw"],
        "h2_compressor_power_kw": design["h2_compressor_power_kw"],
        "oxygen_compressor_power_kw": design["oxygen_compressor_power_kw"],
        "h2_compressor_ideal_kwh_per_t": design["h2_compressor_ideal_kwh_per_t"],
        "h2_compressor_real_kwh_per_t": design["h2_compressor_real_kwh_per_t"],
        "oxygen_compressor_ideal_kwh_per_t": design["oxygen_compressor_ideal_kwh_per_t"],
        "oxygen_compressor_real_kwh_per_t": design["oxygen_compressor_real_kwh_per_t"],
        "battery_system_power_kw": battery_system_power_kw,
        "battery_capacity_kwh": battery_capacity_kwh,
        "battery_cost_eur": battery_cost,
        "direct_capex_eur": gross_capex,
        "gross_capex_eur": gross_capex,
        "total_capex_eur": total_capex,
        "net_capex_eur": total_capex,
        "specific_capex_before_subsidy_eur_per_kw": gross_capex / ely_kw if ely_kw > 0 else np.nan,
        "specific_capex_eur_per_kw": total_capex / ely_kw if ely_kw > 0 else np.nan,
    }


def compute_financing(inputs: ModelInputs, capex: dict) -> dict:
    """Annualize debt and equity separately and report their combined financing cost."""
    s = inputs.system
    c = inputs.capex
    total_capex = capex["total_capex_eur"]

    debt_share = float(np.clip(c.debt_share, 0.0, 1.0))
    equity_share = 1.0 - debt_share

    debt_eur = total_capex * debt_share
    equity_eur = total_capex * equity_share

    debt_annuity = debt_eur * annuity_factor(c.debt_interest_rate, s.project_lifetime_years)
    equity_annuity = equity_eur * annuity_factor(c.equity_interest_rate, s.project_lifetime_years)
    financing_total = debt_annuity + equity_annuity

    # WACC is reported as an informational KPI; it is not used as the LCOH annuity rate.
    wacc = (
        equity_share * c.equity_interest_rate
        + debt_share * c.debt_interest_rate * (1.0 - c.corporate_tax_rate)
    )

    return {
        "debt_share": debt_share,
        "equity_share": equity_share,
        "debt_required_eur": debt_eur,
        "equity_required_eur": equity_eur,
        "debt_annuity_eur_per_year": debt_annuity,
        "equity_annuity_eur_per_year": equity_annuity,
        "financing_eur_per_year": financing_total,
        "wacc": wacc,
        # Compatibility alias used by the existing UI.
        "annuity_factor": np.nan,
        "annualized_capex_eur_per_year": financing_total,
    }


def compute_stack_replacement(inputs: ModelInputs, equivalent_full_load_hours: float) -> dict:
    """Calculate stack replacement count, cost degression and annual financing burden."""
    s = inputs.system
    c = inputs.capex

    project_years = int(s.project_lifetime_years)
    schedule = compute_stack_schedule(inputs, equivalent_full_load_hours)
    replacement_count = schedule["stack_replacement_count"]
    replacement_interval_years = schedule["stack_replacement_interval_years"]

    # Approximate the average replacement-specific cost by applying cost
    # degression to the midpoint of the project lifetime (offset by one year).
    avg_stack_specific = (
        c.stack_replacement_share_of_ely_capex
        * c.electrolyzer_invest_eur_per_kw
        * (1.0 + c.stack_cost_degression_per_year) ** ((project_years - 2.0) / 2.0)
    )
    stack_replacement_total = (
        avg_stack_specific * replacement_count * s.electrolyzer_power_kw
    )

    if stack_replacement_total <= 0 or project_years <= 0:
        stack_annual = 0.0
        reserve_amount = 0.0
        financing_amount = 0.0
    else:
        # Split replacement funding into a reserve accumulated before the
        # representative replacement and financed capital paid afterward.
        reserve_years = project_years / 2.0
        financing_years = project_years - reserve_years
        reserve_amount = stack_replacement_total / (project_years / reserve_years)
        financing_amount = stack_replacement_total - reserve_amount
        financing_annuity = financing_amount * annuity_factor(
            c.stack_financing_interest_rate, financing_years
        )
        stack_total_with_interest = reserve_amount + financing_annuity * financing_years
        stack_annual = stack_total_with_interest / project_years

    return {
        "stack_replacement_count": replacement_count,
        "stack_replacement_interval_years": replacement_interval_years,
        "stack_average_specific_cost_eur_per_kw": avg_stack_specific,
        "stack_replacement_cost_eur": stack_replacement_total,
        "stack_reserve_amount_eur": reserve_amount,
        "stack_financing_amount_eur": financing_amount,
        "stack_replacement_eur_per_year": stack_annual,
    }


def compute_opex(
    inputs: ModelInputs,
    capex: dict,
    annual_h2_kg: float,
    equivalent_full_load_hours: float,
) -> dict:
    """Calculate detailed or lump-sum annual operating expenditure.

    Detailed OPEX is based on CAPEX before CAPEX subsidy. The optional lump-sum
    OPEX is based on CAPEX after CAPEX subsidy.

    A deliberate model convention is retained: an OPEX subsidy reduces LCOH only
    in lump-sum OPEX mode. In detailed mode it is reported in the funding summary
    but is not deducted from annual OPEX.
    """
    o = inputs.opex
    years = inputs.system.project_lifetime_years
    gross_capex = capex["gross_capex_eur"]
    net_capex = capex["total_capex_eur"]

    maintenance = average_escalated_value(
        gross_capex * o.maintenance_share_of_capex,
        o.maintenance_escalation_per_year,
        years,
    )
    personnel = average_escalated_value(
        o.personnel_eur_per_year, o.personnel_escalation_per_year, years
    )
    reserve_remaining_plant = average_escalated_value(
        gross_capex * o.reserve_remaining_plant_share_of_capex,
        o.reserve_escalation_per_year,
        years,
    )
    reserve_decommissioning = average_escalated_value(
        gross_capex * o.reserve_decommissioning_share_of_capex,
        o.reserve_escalation_per_year,
        years,
    )
    reserves_total = reserve_remaining_plant + reserve_decommissioning

    # Water balance assumes 18 kg fresh water and 9 kg wastewater per kg H₂.
    # Water density is treated as 1000 kg/m³.
    freshwater_m3 = annual_h2_kg * 9.0 * 2.0 / 1000.0
    wastewater_m3 = annual_h2_kg * 9.0 / 1000.0
    water_base = (
        freshwater_m3 * o.freshwater_price_eur_per_m3
        + freshwater_m3 * o.freshwater_treatment_price_eur_per_m3
        + wastewater_m3 * o.wastewater_price_eur_per_m3
    )
    water_total = average_escalated_value(
        water_base, o.water_escalation_per_year, years
    )

    individual_opex = average_escalated_value(
        gross_capex * o.individual_opex_share_of_capex,
        o.individual_opex_escalation_per_year,
        years,
    )

    detailed_opex = maintenance + personnel + reserves_total + water_total + individual_opex
    opex_subsidy = compute_opex_subsidy(
        inputs, annual_h2_kg, equivalent_full_load_hours
    )
    lump_sum_before_subsidy = average_escalated_value(
        net_capex * o.lump_sum_share_of_capex,
        o.lump_sum_escalation_per_year,
        years,
    )

    if o.lump_sum_enabled:
        total_opex = lump_sum_before_subsidy - opex_subsidy
        subsidy_applied = opex_subsidy
        calculation_mode = "lump_sum"
    else:
        total_opex = detailed_opex
        subsidy_applied = 0.0
        calculation_mode = "detailed"

    return {
        "opex_calculation_mode": calculation_mode,
        "maintenance_eur_per_year": maintenance,
        "maintenance_escalation_per_year": o.maintenance_escalation_per_year,
        "personnel_eur_per_year": personnel,
        "personnel_escalation_per_year": o.personnel_escalation_per_year,
        "reserve_remaining_plant_eur_per_year": reserve_remaining_plant,
        "reserve_decommissioning_eur_per_year": reserve_decommissioning,
        "reserves_total_eur_per_year": reserves_total,
        "reserve_escalation_per_year": o.reserve_escalation_per_year,
        "annual_freshwater_demand_m3": freshwater_m3,
        "annual_wastewater_m3": wastewater_m3,
        "annual_water_demand_m3": freshwater_m3,
        "water_cost_per_m3": (
            o.freshwater_price_eur_per_m3
            + o.freshwater_treatment_price_eur_per_m3
            + o.wastewater_price_eur_per_m3
        ),
        "water_eur_per_year": water_total,
        "water_escalation_per_year": o.water_escalation_per_year,
        "individual_opex_eur_per_year": individual_opex,
        "individual_opex_escalation_per_year": o.individual_opex_escalation_per_year,
        "detailed_opex_before_subsidy_eur_per_year": detailed_opex,
        "lump_sum_opex_before_subsidy_eur_per_year": lump_sum_before_subsidy,
        "opex_subsidy_calculated_eur_per_year": opex_subsidy,
        "opex_subsidy_applied_eur_per_year": subsidy_applied,
        "total_opex_eur_per_year": total_opex,
    }



def _active_variable_power_surcharges_eur_per_mwh(inputs: ModelInputs, *, electrolyzer: bool) -> dict:
    """Return active variable electricity add-ons in €/MWh.

    Rates entered in ct/kWh are converted with a factor of 10. A component is
    set to zero whenever the corresponding exemption is enabled.
    """
    e = inputs.electricity_costs
    prefix = "electrolyzer" if electrolyzer else "rest"

    components = {
        "grid_fee": e.grid_fee_ct_per_kwh,
        "electricity_tax": e.electricity_tax_ct_per_kwh,
        "concession_fee": e.concession_fee_ct_per_kwh,
        "kwk_levy": e.kwk_levy_ct_per_kwh,
        "stromnev19_levy": e.stromnev19_levy_ct_per_kwh,
        "offshore_levy": e.offshore_levy_ct_per_kwh,
    }
    out = {}
    for name, ct_per_kwh in components.items():
        exempt = getattr(e, f"{prefix}_{name}_exempt")
        out[name] = 0.0 if exempt else float(ct_per_kwh) * 10.0
    return out


def compute_electricity_costs(inputs: ModelInputs, op_kpis: dict) -> dict:
    """Calculate electricity procurement costs, surcharges, demand charges and subsidies."""
    p = inputs.power
    e = inputs.electricity_costs
    years = inputs.system.project_lifetime_years

    # PPA and §13k prices are nominally averaged over the project lifetime.
    # Spot and §7 prices already include cost-side escalation in hourly dispatch.
    annual_baseload_cost = average_escalated_value(
        op_kpis["annual_baseload_cost_eur"], p.baseload_price_escalation_per_year, years
    )
    annual_pv_cost = average_escalated_value(
        op_kpis["annual_pv_ppa_cost_eur"], p.ppa_price_escalation_per_year, years
    )
    annual_wind_cost = average_escalated_value(
        op_kpis["annual_wind_ppa_cost_eur"], p.ppa_price_escalation_per_year, years
    )
    annual_section13k_cost = average_escalated_value(
        op_kpis["annual_section13k_cost_eur"], p.section13k_price_escalation_per_year, years
    )
    annual_section7_cost = op_kpis["annual_section7_cost_eur"]
    annual_spot_purchase_cost = op_kpis["annual_spot_purchase_cost_eur"]

    procurement_cost = (
        annual_baseload_cost
        + annual_pv_cost
        + annual_wind_cost
        + annual_section13k_cost
        + annual_section7_cost
        + annual_spot_purchase_cost
    )

    total_procured_mwh = op_kpis["annual_total_procured_kwh"] / 1000.0
    avg_procurement_price = (
        procurement_cost / total_procured_mwh if total_procured_mwh > 0 else 0.0
    )

    ely_components = _active_variable_power_surcharges_eur_per_mwh(
        inputs, electrolyzer=True
    )
    rest_components = _active_variable_power_surcharges_eur_per_mwh(
        inputs, electrolyzer=False
    )
    ely_variable_surcharge = sum(ely_components.values())
    rest_variable_surcharge = sum(rest_components.values())

    annual_ely_mwh = op_kpis["annual_ely_mwh"]
    annual_rest_mwh = op_kpis["annual_rest_mwh"]

    ely_variable_cost = annual_ely_mwh * ely_variable_surcharge
    rest_variable_cost = annual_rest_mwh * rest_variable_surcharge

    ely_demand_charge = (
        0.0
        if e.electrolyzer_demand_charge_exempt
        else e.electrolyzer_demand_charge_eur_per_kw_month
        * 12.0
        * inputs.system.electrolyzer_power_kw
    )
    rest_max_power_kw = max(
        op_kpis.get("installed_system_power_kw", inputs.system.system_power_kw)
        - inputs.system.electrolyzer_power_kw,
        0.0,
    )
    rest_demand_charge = (
        0.0
        if e.rest_demand_charge_exempt
        else e.rest_demand_charge_eur_per_kw_month * 12.0 * rest_max_power_kw
    )

    ely_demand_specific = (
        ely_demand_charge / annual_ely_mwh if annual_ely_mwh > 0 else 0.0
    )
    rest_demand_specific = (
        rest_demand_charge / annual_rest_mwh if annual_rest_mwh > 0 else 0.0
    )

    ely_addons_cost = ely_variable_cost + ely_demand_charge
    rest_addons_cost = rest_variable_cost + rest_demand_charge
    total_addons_cost = ely_addons_cost + rest_addons_cost
    total_power_cost_gross = procurement_cost + total_addons_cost

    # Privilege savings compare variable electricity charges without exemptions to active charges.
    all_variable_surcharge = (
        e.grid_fee_ct_per_kwh
        + e.electricity_tax_ct_per_kwh
        + e.concession_fee_ct_per_kwh
        + e.kwk_levy_ct_per_kwh
        + e.stromnev19_levy_ct_per_kwh
        + e.offshore_levy_ct_per_kwh
    ) * 10.0
    # The savings KPI covers consumption-based electricity charges only and
    # intentionally excludes separate demand-charge components.
    no_privilege_ely_variable_cost = annual_ely_mwh * all_variable_surcharge
    no_privilege_rest_variable_cost = annual_rest_mwh * all_variable_surcharge
    privilege_savings = (
        no_privilege_ely_variable_cost - ely_variable_cost
        + no_privilege_rest_variable_cost - rest_variable_cost
    )
    total_power_cost_without_privileges = total_power_cost_gross + privilege_savings

    power_subsidy = compute_electricity_subsidy(inputs, op_kpis)
    total_power_cost_after_subsidy = total_power_cost_gross - power_subsidy

    # The configured sales-price escalation applies to both spot and PPA
    # electricity sales.
    annual_spot_sale_revenue = average_escalated_value(
        op_kpis["annual_spot_sale_revenue_eur"],
        p.spot_sale_price_escalation_per_year,
        years,
    )
    average_ppa_sale_price = average_escalated_value(
        p.ppa_sale_price_eur_per_mwh,
        p.spot_sale_price_escalation_per_year,
        years,
    )
    annual_ppa_sale_revenue = (
        op_kpis.get("annual_ppa_sale_kwh", 0.0) / 1000.0 * average_ppa_sale_price
        if p.spot_sale_enabled and p.power_sale_mode == "ppa"
        else 0.0
    )
    annual_power_sale_revenue = annual_spot_sale_revenue + annual_ppa_sale_revenue
    annual_power_sale_mwh = op_kpis.get("annual_power_sale_kwh", 0.0) / 1000.0
    average_power_sale_price = (
        annual_power_sale_revenue / annual_power_sale_mwh
        if annual_power_sale_mwh > 0 else 0.0
    )

    return {
        "annual_baseload_cost_eur": annual_baseload_cost,
        "annual_pv_ppa_cost_eur": annual_pv_cost,
        "annual_wind_ppa_cost_eur": annual_wind_cost,
        "annual_section7_cost_eur": annual_section7_cost,
        "annual_section13k_cost_eur": annual_section13k_cost,
        "annual_spot_purchase_cost_eur": annual_spot_purchase_cost,
        "annual_procurement_cost_eur": procurement_cost,
        "average_procurement_price_eur_per_mwh": avg_procurement_price,
        "ely_grid_fee_eur_per_mwh": ely_components["grid_fee"],
        "ely_electricity_tax_eur_per_mwh": ely_components["electricity_tax"],
        "ely_concession_fee_eur_per_mwh": ely_components["concession_fee"],
        "ely_kwk_levy_eur_per_mwh": ely_components["kwk_levy"],
        "ely_stromnev19_levy_eur_per_mwh": ely_components["stromnev19_levy"],
        "ely_offshore_levy_eur_per_mwh": ely_components["offshore_levy"],
        "rest_grid_fee_eur_per_mwh": rest_components["grid_fee"],
        "rest_electricity_tax_eur_per_mwh": rest_components["electricity_tax"],
        "rest_concession_fee_eur_per_mwh": rest_components["concession_fee"],
        "rest_kwk_levy_eur_per_mwh": rest_components["kwk_levy"],
        "rest_stromnev19_levy_eur_per_mwh": rest_components["stromnev19_levy"],
        "rest_offshore_levy_eur_per_mwh": rest_components["offshore_levy"],
        "ely_variable_power_surcharge_eur_per_mwh": ely_variable_surcharge,
        "rest_variable_power_surcharge_eur_per_mwh": rest_variable_surcharge,
        "ely_demand_charge_eur_per_year": ely_demand_charge,
        "rest_demand_charge_eur_per_year": rest_demand_charge,
        "ely_demand_charge_eur_per_mwh": ely_demand_specific,
        "rest_demand_charge_eur_per_mwh": rest_demand_specific,
        "ely_power_addons_eur_per_year": ely_addons_cost,
        "rest_power_addons_eur_per_year": rest_addons_cost,
        "annual_power_addons_eur": total_addons_cost,
        "annual_power_cost_without_privileges_eur": total_power_cost_without_privileges,
        "privilege_savings_eur_per_year": privilege_savings,
        "electricity_subsidy_eur_per_year": power_subsidy,
        "annual_power_cost_after_subsidy_eur": total_power_cost_after_subsidy,
        "electricity_price_ely_eur_per_mwh": (
            avg_procurement_price + ely_variable_surcharge + ely_demand_specific
        ),
        "electricity_price_rest_eur_per_mwh": (
            avg_procurement_price + rest_variable_surcharge + rest_demand_specific
        ),
        "annual_spot_sale_revenue_eur": annual_spot_sale_revenue,
        "annual_ppa_sale_revenue_eur": annual_ppa_sale_revenue,
        "annual_power_sale_revenue_eur": annual_power_sale_revenue,
        "average_ppa_sale_price_eur_per_mwh": average_ppa_sale_price,
        "average_power_sale_price_eur_per_mwh": average_power_sale_price,
        "annual_power_cost_gross_eur": total_power_cost_gross,
        "annual_power_revenue_eur": annual_power_sale_revenue,
        "annual_power_cost_net_eur": total_power_cost_after_subsidy - annual_power_sale_revenue,
        "annual_spot_cost_eur": annual_spot_purchase_cost,
        "annual_power_costs_eur": total_power_cost_after_subsidy - annual_power_sale_revenue,
    }

def _average_thg_reduction_quota(commissioning_year: int, project_years: int) -> float:
    """Calculate the project-average THG reduction quota used for crediting."""
    if project_years <= 0:
        return 0.0
    if commissioning_year >= 2030:
        return 0.25

    quotas = {2025: 0.106, 2026: 0.121, 2027: 0.146, 2028: 0.176, 2029: 0.211}
    years_until_2030 = max(2030 - commissioning_year, 1)
    pre_2030_sum = sum(
        quota for year, quota in quotas.items() if commissioning_year <= year <= 2029
    )
    # For commissioning before 2030, first average the remaining statutory
    # pre-2030 quotas, then combine that value with 25.1 % for later project
    # years and normalize over the full project lifetime.
    pre_2030_average = pre_2030_sum / years_until_2030
    remaining_years = max(project_years - years_until_2030, 0)
    return (pre_2030_average + remaining_years * 0.251) / project_years


def compute_revenues(inputs: ModelInputs, annual_h2_kg: float, op_kpis: dict) -> dict:
    r = inputs.revenue
    c = inputs.capex
    years = inputs.system.project_lifetime_years

    thg_revenue = 0.0
    thg_reduction_tco2 = 0.0
    if r.thg_enabled and annual_h2_kg > 0:
        reduction_quota = _average_thg_reduction_quota(
            inputs.system.commissioning_year, years
        )
        fossil_baseline = 94.1
        target = (1.0 - reduction_quota) * fossil_baseline
        adjustment_factor = 0.4
        h2_emissions = r.h2_thg_intensity_kgco2_per_gj * adjustment_factor
        credit_factor = 3.0
        reduction_kgco2_per_gj = (target - h2_emissions) * credit_factor
        conversion_per_kg_h2 = 0.1201
        reduction_kgco2_per_kg_h2 = reduction_kgco2_per_gj * conversion_per_kg_h2
        thg_reduction_tco2 = (
            r.mobility_share * annual_h2_kg * reduction_kgco2_per_kg_h2 / 1000.0
        )
        avg_thg_price = average_escalated_value(
            r.thg_price_eur_per_tco2, r.thg_price_escalation_per_year, years
        )
        thg_revenue = thg_reduction_tco2 * avg_thg_price * r.thg_revenue_share

    # Oxygen by-product assumes 8 kg O₂ per kg H₂. Revenue is only enabled when
    # the oxygen system is included in CAPEX.
    annual_oxygen_kg = annual_h2_kg * O2_KG_PER_KG_H2
    annual_oxygen_t = annual_oxygen_kg / KG_PER_TONNE
    avg_oxygen_price = average_escalated_value(
        r.oxygen_price_eur_per_t, r.oxygen_price_escalation_per_year, years
    )
    oxygen_revenue = (
        annual_oxygen_t * avg_oxygen_price if c.oxygen_enabled else 0.0
    )

    # Compressor waste heat is estimated from isentropic specific work and H₂
    # production mass. The O₂ term deliberately uses H₂ mass rather than the
    # O₂/H₂ mass factor; this is a model convention retained for result continuity.
    avg_efficiency = float(op_kpis["average_efficiency_h2_per_el"])
    ely_waste_heat_mwh = (
        op_kpis["annual_ely_kwh"] * max(1.0 - avg_efficiency, 0.0) / 1000.0
    )
    annual_h2_t = annual_h2_kg / KG_PER_TONNE
    h2_compressor_waste_heat_mwh = (
        op_kpis.get("h2_compressor_ideal_kwh_per_t", 0.0)
        / 1000.0
        * annual_h2_t
        * max(1.0 - c.h2_compressor_efficiency, 0.0)
        if c.compression_enabled
        else 0.0
    )
    oxygen_compressor_waste_heat_mwh = (
        op_kpis.get("oxygen_compressor_ideal_kwh_per_t", 0.0)
        / 1000.0
        * annual_h2_t
        * max(1.0 - c.oxygen_compressor_efficiency, 0.0)
        if c.oxygen_enabled
        else 0.0
    )
    total_waste_heat_mwh = (
        ely_waste_heat_mwh
        + h2_compressor_waste_heat_mwh
        + oxygen_compressor_waste_heat_mwh
    )
    usable_waste_heat_mwh = total_waste_heat_mwh * max(r.waste_heat_usable_share, 0.0)
    avg_waste_heat_price = average_escalated_value(
        r.waste_heat_price_eur_per_mwh,
        r.waste_heat_price_escalation_per_year,
        years,
    )
    waste_heat_revenue = (
        usable_waste_heat_mwh * avg_waste_heat_price
        if c.waste_heat_enabled
        else 0.0
    )

    # Electricity-sale revenue is calculated in the electricity-cost module,
    # including the configured sales-side price escalation.
    power_sale_revenue = op_kpis["annual_power_revenue_eur"]

    # Balancing-energy revenue is modeled as an externally estimated annual
    # amount rather than through an hourly reserve-market simulation.
    balancing_energy_revenue = (
        average_escalated_value(
            r.balancing_energy_revenue_eur_per_year,
            r.balancing_energy_escalation_per_year,
            years,
        )
        if r.balancing_energy_enabled else 0.0
    )

    # Two miscellaneous annual revenue positions can escalate independently.
    # A legacy lump-sum field remains readable for older saved configurations but
    # is not exposed in the UI.
    other_revenue_1 = (
        average_escalated_value(
            r.other_revenue_1_eur_per_year,
            r.other_revenue_1_escalation_per_year,
            years,
        )
        if r.other_revenues_enabled else 0.0
    )
    other_revenue_2 = (
        average_escalated_value(
            r.other_revenue_2_eur_per_year,
            r.other_revenue_2_escalation_per_year,
            years,
        )
        if r.other_revenues_enabled else 0.0
    )
    legacy_other_revenue = r.other_revenue_eur_per_year
    other_revenue = other_revenue_1 + other_revenue_2 + legacy_other_revenue

    total_revenue = (
        thg_revenue
        + power_sale_revenue
        + oxygen_revenue
        + waste_heat_revenue
        + balancing_energy_revenue
        + other_revenue
    )

    return {
        "thg_reduction_tco2_per_year": thg_reduction_tco2,
        "thg_revenue_eur_per_year": thg_revenue,
        "annual_oxygen_kg": annual_oxygen_kg,
        "annual_oxygen_t": annual_oxygen_t,
        "average_oxygen_price_eur_per_t": avg_oxygen_price,
        "oxygen_revenue_eur_per_year": oxygen_revenue,
        "ely_waste_heat_mwh_per_year": ely_waste_heat_mwh,
        "h2_compressor_waste_heat_mwh_per_year": h2_compressor_waste_heat_mwh,
        "oxygen_compressor_waste_heat_mwh_per_year": oxygen_compressor_waste_heat_mwh,
        "total_waste_heat_mwh_per_year": total_waste_heat_mwh,
        "usable_waste_heat_mwh_per_year": usable_waste_heat_mwh,
        "average_waste_heat_price_eur_per_mwh": avg_waste_heat_price,
        "waste_heat_revenue_eur_per_year": waste_heat_revenue,
        "power_sale_revenue_eur_per_year": power_sale_revenue,
        "balancing_energy_revenue_eur_per_year": balancing_energy_revenue,
        "other_revenue_1_eur_per_year": other_revenue_1,
        "other_revenue_2_eur_per_year": other_revenue_2,
        "legacy_other_revenue_eur_per_year": legacy_other_revenue,
        "other_revenue_eur_per_year": other_revenue,
        "total_other_revenues_eur_per_year": total_revenue,
    }


def compute_lcoh(inputs: ModelInputs, dispatch) -> dict:
    # Full-load hours determine the stack interval and therefore the average
    # degraded efficiency. build_dispatch() already iterates compressor design
    # against that value; recalculating here keeps the finance path explicit.
    op_base = compute_operation_kpis(
        inputs, dispatch, efficiency_override=inputs.system.avg_efficiency_h2_per_el
    )
    stack = compute_stack_replacement(inputs, op_base["equivalent_full_load_hours"])
    avg_efficiency = compute_average_efficiency(inputs, stack)
    op_kpis = compute_operation_kpis(inputs, dispatch, efficiency_override=avg_efficiency)

    # Battery capacity and CAPEX depend on installed system power, including
    # H₂ and O₂ compressor design loads.
    capex = compute_capex(inputs, average_efficiency=avg_efficiency)
    financing = compute_financing(inputs, capex)
    opex = compute_opex(
        inputs,
        capex,
        op_kpis["annual_h2_kg"],
        op_kpis["equivalent_full_load_hours"],
    )
    electricity = compute_electricity_costs(inputs, op_kpis)
    op_kpis.update(electricity)

    revenues = compute_revenues(inputs, op_kpis["annual_h2_kg"], op_kpis)
    spk = compute_strompreiskompensation(inputs, op_kpis)

    # The funding-summary KPI adds annualized CAPEX support, calculated OPEX and
    # electricity subsidies, privilege savings and SPK. CAPEX support affects
    # LCOH through the reduced financed CAPEX, not through an extra annual deduction.
    annual_funding_total = (
        capex["capex_subsidy_eur_per_year"]
        + opex["opex_subsidy_calculated_eur_per_year"]
        + electricity["electricity_subsidy_eur_per_year"]
        + electricity["privilege_savings_eur_per_year"]
        + spk["spk_revenue_eur_per_year"]
    )

    # LCOH numerator = stack replacement + OPEX + electricity cost after subsidy
    # + financing - SPK - other revenues. CAPEX subsidy is already reflected in
    # the financed CAPEX and must not be deducted again here.
    annual_costs_before_revenues = (
        stack["stack_replacement_eur_per_year"]
        + opex["total_opex_eur_per_year"]
        + electricity["annual_power_cost_after_subsidy_eur"]
        + financing["financing_eur_per_year"]
    )
    annual_costs = (
        annual_costs_before_revenues
        - spk["spk_revenue_eur_per_year"]
        - revenues["total_other_revenues_eur_per_year"]
    )

    annual_h2_kg = op_kpis["annual_h2_kg"]
    lcoh_eur_per_kg = annual_costs / annual_h2_kg if annual_h2_kg > 0 else np.nan
    lcoh_ct_per_kwh = (
        lcoh_eur_per_kg / KWH_PER_KG_H2 * 100.0
        if np.isfinite(lcoh_eur_per_kg)
        else np.nan
    )

    return {
        **capex,
        **financing,
        **stack,
        **opex,
        **op_kpis,
        **revenues,
        **spk,
        "annual_funding_total_eur_per_year": annual_funding_total,
        "average_efficiency_h2_per_el": avg_efficiency,
        "annual_costs_before_revenues_eur_per_year": annual_costs_before_revenues,
        "annual_costs_eur_per_year": annual_costs,
        "lcoh_eur_per_kg": lcoh_eur_per_kg,
        "lcoh_ct_per_kwh": lcoh_ct_per_kwh,
    }
