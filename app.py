from __future__ import annotations

from dataclasses import asdict
import json

import numpy as np
import pandas as pd
import streamlit as st

from widgets import percent_slider
from help_texts import HELP

from core.models import (
    SystemInputs,
    CapexInputs,
    OpexInputs,
    PowerInputs,
    ElectricityCostInputs,
    RevenueInputs,
    FundingInputs,
    ModelInputs,
)
from core.timeseries import (
    make_demo_timeseries,
    validate_timeseries,
    parse_timeseries_text,
    timeseries_to_text,
)
from core.simulation import build_dispatch
from core.finance import compute_lcoh
from core.sensitivity import (
    EXCEL_SENSITIVITY_PARAMETERS,
    PARAMETER_BY_KEY,
    DEFAULT_SENSITIVITY_RANGE_PERCENT,
    DEFAULT_SENSITIVITY_POINTS,
    DEFAULT_SENSITIVITY_PARAMETER,
    compute_sensitivity_curve,
    compute_tornado,
)
from core.reporting import (
    lcoh_bridge,
    positive_cost_distribution,
    revenue_distribution,
    utilization_duration_curve,
)

import plotly.graph_objects as go

import locale

locale.setlocale(locale.LC_ALL, "de_DE.UTF-8")

def de_number(value, decimals=2):
    if value is None:
        return "-"
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.set_page_config(page_title="Berechnungstool LCOH", layout="wide")


PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}


def render_plotly(fig: go.Figure) -> None:
    """Render all application charts with one common Plotly/Streamlit setup."""
    fig.update_layout(
        font=dict(size=13),
        hoverlabel=dict(namelength=-1),
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        theme="streamlit",
        config=PLOTLY_CONFIG,
    )


# ============================================================
# Session-State Initialisierung
# ============================================================

# Sensitivitäts-UI: Defaults kommen zentral aus core.sensitivity.
#
# Die Versionsnummer ist absichtlich getrennt vom allgemeinen ``ui_initialized``.
# Streamlit merkt sich Widget-Werte anhand ihres Keys auch über Source-Reruns hinweg.
# Eine neue Version erzwingt deshalb genau einmal die gewünschten Defaults und
# verhindert, dass alte Slider-Zustände (z. B. 5 % / 5 Punkte) weiterleben.
SENSITIVITY_UI_STATE_VERSION = 2
SENSITIVITY_RANGE_WIDGET_KEY = "sensitivity_range_percent_widget_v2"
SENSITIVITY_POINTS_WIDGET_KEY = "sensitivity_points_widget_v2"


def ensure_sensitivity_ui_state() -> None:
    """Migrate and validate the sensitivity UI state.

    The migration runs once per sensitivity-UI version. This is stronger than
    merely checking whether a value is valid: an old value of 5 is technically
    valid, but it must not override the new intended initial defaults of
    ±30 % and 13 points after updating the app.
    """
    valid_ranges = set(range(5, 81, 5))
    valid_points = set(range(5, 32, 2))
    valid_parameters = {p.key for p in EXCEL_SENSITIVITY_PARAMETERS}

    if st.session_state.get("_sensitivity_ui_state_version") != SENSITIVITY_UI_STATE_VERSION:
        st.session_state.sensitivity_range_percent = DEFAULT_SENSITIVITY_RANGE_PERCENT
        st.session_state.sensitivity_points = DEFAULT_SENSITIVITY_POINTS
        st.session_state.sensitivity_parameter = DEFAULT_SENSITIVITY_PARAMETER

        # Remove values belonging to the new version in case a partially run
        # session already created them. The widgets will then initialize from
        # the canonical defaults below.
        st.session_state.pop(SENSITIVITY_RANGE_WIDGET_KEY, None)
        st.session_state.pop(SENSITIVITY_POINTS_WIDGET_KEY, None)
        st.session_state._sensitivity_ui_state_version = SENSITIVITY_UI_STATE_VERSION

    if st.session_state.get("sensitivity_range_percent") not in valid_ranges:
        st.session_state.sensitivity_range_percent = DEFAULT_SENSITIVITY_RANGE_PERCENT
    if st.session_state.get("sensitivity_points") not in valid_points:
        st.session_state.sensitivity_points = DEFAULT_SENSITIVITY_POINTS
    if st.session_state.get("sensitivity_parameter") not in valid_parameters:
        st.session_state.sensitivity_parameter = DEFAULT_SENSITIVITY_PARAMETER


def init_ui_state() -> None:
    # Run this migration on every rerun, even for sessions initialized by an
    # older version of the app.
    ensure_sensitivity_ui_state()

    if "ui_initialized" in st.session_state:
        return

    # Defaults aus Dataclasses
    s = SystemInputs()
    c = CapexInputs()
    o = OpexInputs()
    p = PowerInputs()
    ec = ElectricityCostInputs()
    f = FundingInputs()

    # System
    st.session_state.commissioning_year = s.commissioning_year
    st.session_state.project_lifetime_years = s.project_lifetime_years
    st.session_state.electrolyzer_power_kw = s.electrolyzer_power_kw
    st.session_state.peripheral_power_fraction = s.peripheral_power_fraction * 100
    st.session_state.min_load_fraction = s.min_load_fraction * 100
    st.session_state.avg_efficiency_h2_per_el = s.avg_efficiency_h2_per_el * 100
    st.session_state.stack_lifetime_hours = s.stack_lifetime_hours
    st.session_state.degradation_per_year = s.degradation_per_year * 100

    # CAPEX
    st.session_state.electrolyzer_invest_eur_per_kw = c.electrolyzer_invest_eur_per_kw
    st.session_state.epc_eur_per_kw = c.epc_eur_per_kw
    st.session_state.bop_eur_per_kw = c.bop_eur_per_kw
    st.session_state.hochbau_eur_per_kw = c.hochbau_eur_per_kw
    st.session_state.tiefbau_eur_per_kw = c.tiefbau_eur_per_kw
    st.session_state.individual_specific_eur_per_kw = c.individual_specific_eur_per_kw
    st.session_state.individual_ely_cost_share = c.individual_ely_cost_share * 100
    st.session_state.individual_fixed_eur = c.individual_fixed_eur

    st.session_state.waste_heat_enabled = c.waste_heat_enabled
    st.session_state.waste_heat_system_eur_per_kw = c.waste_heat_system_eur_per_kw

    st.session_state.oxygen_enabled = c.oxygen_enabled
    st.session_state.oxygen_system_eur_per_kw = c.oxygen_system_eur_per_kw

    st.session_state.compression_enabled = c.compression_enabled
    st.session_state.compressor_system_eur_per_kw = c.compressor_system_eur_per_kw
    st.session_state.h2_direct_system_eur_per_kw = c.h2_direct_system_eur_per_kw
    st.session_state.h2_processed_share = c.h2_processed_share * 100
    st.session_state.h2_compressor_outlet_pressure_bar = c.h2_compressor_outlet_pressure_bar
    st.session_state.h2_compressor_inlet_temperature_c = c.h2_compressor_inlet_temperature_c
    st.session_state.h2_compressor_inlet_pressure_bar = c.h2_compressor_inlet_pressure_bar
    st.session_state.h2_compressor_efficiency = c.h2_compressor_efficiency * 100
    st.session_state.oxygen_compressor_outlet_pressure_bar = c.oxygen_compressor_outlet_pressure_bar
    st.session_state.oxygen_compressor_inlet_temperature_c = c.oxygen_compressor_inlet_temperature_c
    st.session_state.oxygen_compressor_inlet_pressure_bar = c.oxygen_compressor_inlet_pressure_bar
    st.session_state.oxygen_compressor_efficiency = c.oxygen_compressor_efficiency * 100

    st.session_state.battery_enabled = c.battery_enabled
    st.session_state.battery_capacity_factor_kwh_per_kw = c.battery_capacity_factor_kwh_per_kw
    st.session_state.battery_power_kw = c.battery_power_kw
    st.session_state.battery_invest_eur_per_kwh = c.battery_invest_eur_per_kwh
    st.session_state.battery_fixed_eur = c.battery_fixed_eur

    st.session_state.stack_replacement_share_of_ely_capex = c.stack_replacement_share_of_ely_capex * 100
    st.session_state.stack_cost_degression_per_year = c.stack_cost_degression_per_year * 100
    st.session_state.stack_financing_interest_rate = c.stack_financing_interest_rate * 100
    st.session_state.debt_share = c.debt_share * 100
    st.session_state.debt_interest_rate = c.debt_interest_rate * 100
    st.session_state.equity_interest_rate = c.equity_interest_rate * 100
    st.session_state.corporate_tax_rate = c.corporate_tax_rate * 100

    # OPEX
    st.session_state.lump_sum_enabled = o.lump_sum_enabled
    st.session_state.lump_sum_share_of_capex = o.lump_sum_share_of_capex * 100
    st.session_state.lump_sum_escalation_per_year = o.lump_sum_escalation_per_year * 100

    st.session_state.maintenance_share_of_capex = o.maintenance_share_of_capex * 100
    st.session_state.maintenance_escalation_per_year = o.maintenance_escalation_per_year * 100

    st.session_state.personnel_eur_per_year = o.personnel_eur_per_year
    st.session_state.personnel_escalation_per_year = o.personnel_escalation_per_year * 100

    st.session_state.reserve_remaining_plant_share_of_capex = o.reserve_remaining_plant_share_of_capex * 100
    st.session_state.reserve_decommissioning_share_of_capex = o.reserve_decommissioning_share_of_capex * 100
    st.session_state.reserve_escalation_per_year = o.reserve_escalation_per_year * 100

    st.session_state.freshwater_price_eur_per_m3 = o.freshwater_price_eur_per_m3
    st.session_state.freshwater_treatment_price_eur_per_m3 = o.freshwater_treatment_price_eur_per_m3
    st.session_state.wastewater_price_eur_per_m3 = o.wastewater_price_eur_per_m3
    st.session_state.water_escalation_per_year = o.water_escalation_per_year * 100

    st.session_state.individual_opex_share_of_capex = o.individual_opex_share_of_capex * 100
    st.session_state.individual_opex_escalation_per_year = o.individual_opex_escalation_per_year * 100

    # Power
    st.session_state.baseload_enabled = p.baseload_enabled
    st.session_state.baseload_kw = p.baseload_kw
    st.session_state.baseload_price_eur_per_mwh = p.baseload_price_eur_per_mwh
    st.session_state.baseload_price_escalation_per_year = p.baseload_price_escalation_per_year * 100

    st.session_state.ppa_pv_enabled = p.ppa_pv_enabled
    st.session_state.ppa_pv_capacity_kw = p.ppa_pv_capacity_kw
    st.session_state.ppa_pv_price_eur_per_mwh = p.ppa_pv_price_eur_per_mwh

    st.session_state.ppa_wind_enabled = p.ppa_wind_enabled
    st.session_state.ppa_wind_capacity_kw = p.ppa_wind_capacity_kw
    st.session_state.ppa_wind_price_eur_per_mwh = p.ppa_wind_price_eur_per_mwh

    st.session_state.ppa_price_escalation_per_year = p.ppa_price_escalation_per_year * 100

    # §7 / §13k
    st.session_state.section7_enabled = p.section7_enabled
    st.session_state.section7_include_negative_prices = p.section7_include_negative_prices
    st.session_state.section7_co2_price_mode = (
        "Jahresdaten" if p.section7_co2_price_mode == "timeseries" else "Eigener Wert"
    )
    st.session_state.section7_co2_price_eur_per_t = p.section7_co2_price_eur_per_t
    st.session_state.section7_co2_price_escalation_per_year = p.section7_co2_price_escalation_per_year * 100
    st.session_state.section13k_enabled = p.section13k_enabled
    st.session_state.section13k_price_eur_per_mwh = p.section13k_price_eur_per_mwh
    st.session_state.section13k_price_escalation_per_year = p.section13k_price_escalation_per_year * 100

    st.session_state.spot_purchase_enabled = p.spot_purchase_enabled
    st.session_state.spot_purchase_price_limit_enabled = p.spot_purchase_price_limit_enabled
    st.session_state.spot_purchase_price_limit_eur_per_mwh = p.spot_purchase_price_limit_eur_per_mwh
    st.session_state.spot_price_escalation_per_year = p.spot_price_escalation_per_year * 100
    st.session_state.spot_sale_enabled = p.spot_sale_enabled
    st.session_state.power_sale_mode = "Spotmarkt" if p.power_sale_mode == "spot" else "PPA"
    st.session_state.ppa_sale_price_eur_per_mwh = p.ppa_sale_price_eur_per_mwh
    st.session_state.spot_sale_price_limit_enabled = p.spot_sale_price_limit_enabled
    st.session_state.spot_sale_min_price_eur_per_mwh = p.spot_sale_min_price_eur_per_mwh
    st.session_state.spot_sale_price_escalation_per_year = p.spot_sale_price_escalation_per_year * 100

    # Stromnebenkosten / Privilegierungen (Excel Blatt 5)
    for name in (
        "grid_fee_ct_per_kwh",
        "electricity_tax_ct_per_kwh",
        "concession_fee_ct_per_kwh",
        "kwk_levy_ct_per_kwh",
        "stromnev19_levy_ct_per_kwh",
        "offshore_levy_ct_per_kwh",
        "electrolyzer_grid_fee_exempt",
        "electrolyzer_electricity_tax_exempt",
        "electrolyzer_concession_fee_exempt",
        "electrolyzer_kwk_levy_exempt",
        "electrolyzer_stromnev19_levy_exempt",
        "electrolyzer_offshore_levy_exempt",
        "rest_grid_fee_exempt",
        "rest_electricity_tax_exempt",
        "rest_concession_fee_exempt",
        "rest_kwk_levy_exempt",
        "rest_stromnev19_levy_exempt",
        "rest_offshore_levy_exempt",
        "electrolyzer_demand_charge_eur_per_kw_month",
        "rest_demand_charge_eur_per_kw_month",
        "electrolyzer_demand_charge_exempt",
        "rest_demand_charge_exempt",
    ):
        st.session_state[name] = getattr(ec, name)

    # Förderungen & Strompreiskompensation (Excel C167:C193)
    st.session_state.capex_subsidy_mode = {
        "none": "Ohne", "percentage": "Prozentual", "absolute": "Absolut"
    }[f.capex_mode]
    st.session_state.capex_subsidy_percentage = f.capex_percentage * 100
    st.session_state.capex_subsidy_absolute_eur_per_kw = f.capex_absolute_eur_per_kw
    st.session_state.opex_subsidy_mode = {
        "none": "Ohne", "per_kg": "Pro kg", "per_full_load_hour": "Pro Volllaststunde"
    }[f.opex_mode]
    st.session_state.opex_subsidy_eur_per_kg_h2 = f.opex_eur_per_kg_h2
    st.session_state.opex_subsidy_eur_per_full_load_hour = f.opex_eur_per_full_load_hour
    st.session_state.electricity_subsidy_mode = {
        "none": "Ohne", "per_kg": "Pro kg", "per_mwh": "Pro MWh Strom"
    }[f.electricity_mode]
    st.session_state.electricity_subsidy_eur_per_kg_h2 = f.electricity_eur_per_kg_h2
    st.session_state.electricity_subsidy_eur_per_mwh = f.electricity_eur_per_mwh
    st.session_state.spk_mode = {
        "none": "Ohne", "calculator": "Rechner", "separate": "Separat"
    }[f.spk_mode]
    st.session_state.spk_eua_price_eur_per_tco2 = f.spk_eua_price_eur_per_tco2
    st.session_state.spk_power_consumption_factor = f.spk_power_consumption_factor
    st.session_state.spk_price_escalation_per_year = f.spk_price_escalation_per_year * 100
    st.session_state.spk_separate_revenue_eur_per_year = f.spk_separate_revenue_eur_per_year

    # Erlöse (Excel THG-Quote)
    r = RevenueInputs()
    st.session_state.thg_enabled = r.thg_enabled
    st.session_state.thg_price_eur_per_tco2 = r.thg_price_eur_per_tco2
    st.session_state.mobility_share = r.mobility_share * 100
    st.session_state.thg_revenue_share = r.thg_revenue_share * 100
    st.session_state.h2_thg_intensity_kgco2_per_gj = r.h2_thg_intensity_kgco2_per_gj
    st.session_state.thg_price_escalation_per_year = r.thg_price_escalation_per_year * 100
    st.session_state.oxygen_price_eur_per_t = r.oxygen_price_eur_per_t
    st.session_state.oxygen_price_escalation_per_year = r.oxygen_price_escalation_per_year * 100
    st.session_state.waste_heat_price_eur_per_mwh = r.waste_heat_price_eur_per_mwh
    st.session_state.waste_heat_usable_share = r.waste_heat_usable_share * 100
    st.session_state.waste_heat_price_escalation_per_year = r.waste_heat_price_escalation_per_year * 100
    st.session_state.balancing_energy_enabled = r.balancing_energy_enabled
    st.session_state.balancing_energy_revenue_eur_per_year = r.balancing_energy_revenue_eur_per_year
    st.session_state.balancing_energy_escalation_per_year = r.balancing_energy_escalation_per_year * 100
    st.session_state.other_revenues_enabled = r.other_revenues_enabled
    st.session_state.other_revenue_1_eur_per_year = r.other_revenue_1_eur_per_year
    st.session_state.other_revenue_1_escalation_per_year = r.other_revenue_1_escalation_per_year * 100
    st.session_state.other_revenue_2_eur_per_year = r.other_revenue_2_eur_per_year
    st.session_state.other_revenue_2_escalation_per_year = r.other_revenue_2_escalation_per_year * 100

    demo_ts = make_demo_timeseries()
    st.session_state.timeseries_df = demo_ts.copy()
    st.session_state.pv_profile_text = timeseries_to_text(demo_ts["pv_kwh_per_kw"])
    st.session_state.wind_profile_text = timeseries_to_text(demo_ts["wind_kwh_per_kw"])
    st.session_state.spot_price_text = timeseries_to_text(demo_ts["day_ahead_eur_per_mwh"])
    st.session_state.co2_price_text = timeseries_to_text(demo_ts["co2_eur_per_t"])
    st.session_state.section13k_profile_text = timeseries_to_text(demo_ts["section13k_kwh"])

    # Weitere Zustände
    st.session_state.result_bundle = None
    st.session_state.sensitivity_range_percent = DEFAULT_SENSITIVITY_RANGE_PERCENT
    st.session_state.sensitivity_points = DEFAULT_SENSITIVITY_POINTS
    st.session_state.sensitivity_parameter = DEFAULT_SENSITIVITY_PARAMETER
    st.session_state.ui_initialized = True


def build_model_inputs_from_ui() -> ModelInputs:
    system = SystemInputs(
        commissioning_year=int(st.session_state.commissioning_year),
        project_lifetime_years=int(st.session_state.project_lifetime_years),
        electrolyzer_power_kw=float(st.session_state.electrolyzer_power_kw),
        peripheral_power_fraction=float(st.session_state.peripheral_power_fraction) / 100.0,
        min_load_fraction=float(st.session_state.min_load_fraction) / 100,
        avg_efficiency_h2_per_el=float(st.session_state.avg_efficiency_h2_per_el) / 100,
        stack_lifetime_hours=float(st.session_state.stack_lifetime_hours),
        degradation_per_year=float(st.session_state.degradation_per_year) / 100.0,
    )

    capex = CapexInputs(
        electrolyzer_invest_eur_per_kw=float(st.session_state.electrolyzer_invest_eur_per_kw),
        epc_eur_per_kw=float(st.session_state.epc_eur_per_kw),
        bop_eur_per_kw=float(st.session_state.bop_eur_per_kw),
        hochbau_eur_per_kw=float(st.session_state.hochbau_eur_per_kw),
        tiefbau_eur_per_kw=float(st.session_state.tiefbau_eur_per_kw),
        individual_specific_eur_per_kw=float(st.session_state.individual_specific_eur_per_kw),
        individual_ely_cost_share=float(st.session_state.individual_ely_cost_share) / 100.0,
        individual_fixed_eur=float(st.session_state.individual_fixed_eur),

        waste_heat_enabled=bool(st.session_state.waste_heat_enabled),
        waste_heat_system_eur_per_kw=float(st.session_state.waste_heat_system_eur_per_kw),

        oxygen_enabled=bool(st.session_state.oxygen_enabled),
        oxygen_system_eur_per_kw=float(st.session_state.oxygen_system_eur_per_kw),

        compression_enabled=bool(st.session_state.compression_enabled),
        compressor_system_eur_per_kw=float(st.session_state.compressor_system_eur_per_kw),
        h2_direct_system_eur_per_kw=float(st.session_state.h2_direct_system_eur_per_kw),
        h2_processed_share=float(st.session_state.h2_processed_share) / 100.0,
        h2_compressor_outlet_pressure_bar=float(st.session_state.h2_compressor_outlet_pressure_bar),
        h2_compressor_inlet_temperature_c=float(st.session_state.h2_compressor_inlet_temperature_c),
        h2_compressor_inlet_pressure_bar=float(st.session_state.h2_compressor_inlet_pressure_bar),
        h2_compressor_efficiency=float(st.session_state.h2_compressor_efficiency) / 100.0,
        oxygen_compressor_outlet_pressure_bar=float(st.session_state.oxygen_compressor_outlet_pressure_bar),
        oxygen_compressor_inlet_temperature_c=float(st.session_state.oxygen_compressor_inlet_temperature_c),
        oxygen_compressor_inlet_pressure_bar=float(st.session_state.oxygen_compressor_inlet_pressure_bar),
        oxygen_compressor_efficiency=float(st.session_state.oxygen_compressor_efficiency) / 100.0,

        battery_enabled=bool(st.session_state.battery_enabled),
        battery_capacity_factor_kwh_per_kw=float(st.session_state.battery_capacity_factor_kwh_per_kw),
        battery_power_kw=float(st.session_state.battery_power_kw),
        battery_invest_eur_per_kwh=float(st.session_state.battery_invest_eur_per_kwh),
        battery_fixed_eur=float(st.session_state.battery_fixed_eur),

        stack_replacement_share_of_ely_capex=float(st.session_state.stack_replacement_share_of_ely_capex) / 100.0,
        stack_cost_degression_per_year=float(st.session_state.stack_cost_degression_per_year) / 100.0,
        stack_financing_interest_rate=float(st.session_state.stack_financing_interest_rate) / 100.0,
        debt_share=float(st.session_state.debt_share) / 100.0,
        debt_interest_rate=float(st.session_state.debt_interest_rate) / 100.0,
        equity_interest_rate=float(st.session_state.equity_interest_rate) / 100.0,
        corporate_tax_rate=float(st.session_state.corporate_tax_rate) / 100.0,
    )

    opex = OpexInputs(
        lump_sum_enabled=bool(st.session_state.lump_sum_enabled),
        lump_sum_share_of_capex=float(st.session_state.lump_sum_share_of_capex) / 100.0,
        lump_sum_escalation_per_year=float(st.session_state.lump_sum_escalation_per_year) / 100.0,

        maintenance_share_of_capex=float(st.session_state.maintenance_share_of_capex) / 100.0,
        maintenance_escalation_per_year=float(st.session_state.maintenance_escalation_per_year) / 100.0,

        personnel_eur_per_year=float(st.session_state.personnel_eur_per_year),
        personnel_escalation_per_year=float(st.session_state.personnel_escalation_per_year) / 100.0,

        reserve_remaining_plant_share_of_capex=float(st.session_state.reserve_remaining_plant_share_of_capex) / 100.0,
        reserve_decommissioning_share_of_capex=float(st.session_state.reserve_decommissioning_share_of_capex) / 100.0,
        reserve_escalation_per_year=float(st.session_state.reserve_escalation_per_year) / 100.0,

        freshwater_price_eur_per_m3=float(st.session_state.freshwater_price_eur_per_m3),
        freshwater_treatment_price_eur_per_m3=float(st.session_state.freshwater_treatment_price_eur_per_m3),
        wastewater_price_eur_per_m3=float(st.session_state.wastewater_price_eur_per_m3),
        water_escalation_per_year=float(st.session_state.water_escalation_per_year) / 100.0,

        individual_opex_share_of_capex=float(st.session_state.individual_opex_share_of_capex) / 100.0,
        individual_opex_escalation_per_year=float(st.session_state.individual_opex_escalation_per_year) / 100.0,
    )

    power = PowerInputs(
        baseload_enabled=bool(st.session_state.baseload_enabled),
        baseload_kw=float(st.session_state.baseload_kw),
        baseload_price_eur_per_mwh=float(st.session_state.baseload_price_eur_per_mwh),
        baseload_price_escalation_per_year=float(st.session_state.baseload_price_escalation_per_year) / 100.0,

        ppa_pv_enabled=bool(st.session_state.ppa_pv_enabled),
        ppa_pv_capacity_kw=float(st.session_state.ppa_pv_capacity_kw),
        ppa_pv_price_eur_per_mwh=float(st.session_state.ppa_pv_price_eur_per_mwh),

        ppa_wind_enabled=bool(st.session_state.ppa_wind_enabled),
        ppa_wind_capacity_kw=float(st.session_state.ppa_wind_capacity_kw),
        ppa_wind_price_eur_per_mwh=float(st.session_state.ppa_wind_price_eur_per_mwh),

        ppa_price_escalation_per_year=float(st.session_state.ppa_price_escalation_per_year) / 100.0,

        section7_enabled=bool(st.session_state.section7_enabled),
        section7_include_negative_prices=bool(st.session_state.section7_include_negative_prices),
        section7_co2_price_mode=(
            "timeseries" if st.session_state.section7_co2_price_mode == "Jahresdaten" else "fixed"
        ),
        section7_co2_price_eur_per_t=float(st.session_state.section7_co2_price_eur_per_t),
        section7_co2_price_escalation_per_year=float(st.session_state.section7_co2_price_escalation_per_year) / 100.0,
        section13k_enabled=bool(st.session_state.section13k_enabled),
        section13k_price_eur_per_mwh=float(st.session_state.section13k_price_eur_per_mwh),
        section13k_price_escalation_per_year=float(st.session_state.section13k_price_escalation_per_year) / 100.0,

        spot_purchase_enabled=bool(st.session_state.spot_purchase_enabled),
        spot_purchase_price_limit_enabled=bool(st.session_state.spot_purchase_price_limit_enabled),
        spot_purchase_price_limit_eur_per_mwh=float(st.session_state.spot_purchase_price_limit_eur_per_mwh),
        spot_price_escalation_per_year=float(st.session_state.spot_price_escalation_per_year) / 100.0,

        spot_sale_enabled=bool(st.session_state.spot_sale_enabled),
        power_sale_mode="spot" if st.session_state.power_sale_mode == "Spotmarkt" else "ppa",
        ppa_sale_price_eur_per_mwh=float(st.session_state.ppa_sale_price_eur_per_mwh),
        spot_sale_price_limit_enabled=bool(st.session_state.spot_sale_price_limit_enabled),
        spot_sale_min_price_eur_per_mwh=float(st.session_state.spot_sale_min_price_eur_per_mwh),
        spot_sale_price_escalation_per_year=float(st.session_state.spot_sale_price_escalation_per_year) / 100.0,
    )

    electricity_costs = ElectricityCostInputs(
        grid_fee_ct_per_kwh=float(st.session_state.grid_fee_ct_per_kwh),
        electricity_tax_ct_per_kwh=float(st.session_state.electricity_tax_ct_per_kwh),
        concession_fee_ct_per_kwh=float(st.session_state.concession_fee_ct_per_kwh),
        kwk_levy_ct_per_kwh=float(st.session_state.kwk_levy_ct_per_kwh),
        stromnev19_levy_ct_per_kwh=float(st.session_state.stromnev19_levy_ct_per_kwh),
        offshore_levy_ct_per_kwh=float(st.session_state.offshore_levy_ct_per_kwh),
        electrolyzer_grid_fee_exempt=bool(st.session_state.electrolyzer_grid_fee_exempt),
        electrolyzer_electricity_tax_exempt=bool(st.session_state.electrolyzer_electricity_tax_exempt),
        electrolyzer_concession_fee_exempt=bool(st.session_state.electrolyzer_concession_fee_exempt),
        electrolyzer_kwk_levy_exempt=bool(st.session_state.electrolyzer_kwk_levy_exempt),
        electrolyzer_stromnev19_levy_exempt=bool(st.session_state.electrolyzer_stromnev19_levy_exempt),
        electrolyzer_offshore_levy_exempt=bool(st.session_state.electrolyzer_offshore_levy_exempt),
        rest_grid_fee_exempt=bool(st.session_state.rest_grid_fee_exempt),
        rest_electricity_tax_exempt=bool(st.session_state.rest_electricity_tax_exempt),
        rest_concession_fee_exempt=bool(st.session_state.rest_concession_fee_exempt),
        rest_kwk_levy_exempt=bool(st.session_state.rest_kwk_levy_exempt),
        rest_stromnev19_levy_exempt=bool(st.session_state.rest_stromnev19_levy_exempt),
        rest_offshore_levy_exempt=bool(st.session_state.rest_offshore_levy_exempt),
        electrolyzer_demand_charge_eur_per_kw_month=float(st.session_state.electrolyzer_demand_charge_eur_per_kw_month),
        rest_demand_charge_eur_per_kw_month=float(st.session_state.rest_demand_charge_eur_per_kw_month),
        electrolyzer_demand_charge_exempt=bool(st.session_state.electrolyzer_demand_charge_exempt),
        rest_demand_charge_exempt=bool(st.session_state.rest_demand_charge_exempt),
    )

    funding = FundingInputs(
        capex_mode={
            "Ohne": "none", "Prozentual": "percentage", "Absolut": "absolute"
        }[st.session_state.capex_subsidy_mode],
        capex_percentage=float(st.session_state.capex_subsidy_percentage) / 100.0,
        capex_absolute_eur_per_kw=float(st.session_state.capex_subsidy_absolute_eur_per_kw),
        opex_mode={
            "Ohne": "none", "Pro kg": "per_kg", "Pro Volllaststunde": "per_full_load_hour"
        }[st.session_state.opex_subsidy_mode],
        opex_eur_per_kg_h2=float(st.session_state.opex_subsidy_eur_per_kg_h2),
        opex_eur_per_full_load_hour=float(st.session_state.opex_subsidy_eur_per_full_load_hour),
        electricity_mode={
            "Ohne": "none", "Pro kg": "per_kg", "Pro MWh Strom": "per_mwh"
        }[st.session_state.electricity_subsidy_mode],
        electricity_eur_per_kg_h2=float(st.session_state.electricity_subsidy_eur_per_kg_h2),
        electricity_eur_per_mwh=float(st.session_state.electricity_subsidy_eur_per_mwh),
        spk_mode={
            "Ohne": "none", "Rechner": "calculator", "Separat": "separate"
        }[st.session_state.spk_mode],
        spk_eua_price_eur_per_tco2=float(st.session_state.spk_eua_price_eur_per_tco2),
        spk_power_consumption_factor=float(st.session_state.spk_power_consumption_factor),
        spk_price_escalation_per_year=float(st.session_state.spk_price_escalation_per_year) / 100.0,
        spk_separate_revenue_eur_per_year=float(st.session_state.spk_separate_revenue_eur_per_year),
    )

    revenue = RevenueInputs(
        thg_enabled=bool(st.session_state.thg_enabled),
        thg_price_eur_per_tco2=float(st.session_state.thg_price_eur_per_tco2),
        mobility_share=float(st.session_state.mobility_share) / 100.0,
        thg_revenue_share=float(st.session_state.thg_revenue_share) / 100.0,
        h2_thg_intensity_kgco2_per_gj=float(st.session_state.h2_thg_intensity_kgco2_per_gj),
        thg_price_escalation_per_year=float(st.session_state.thg_price_escalation_per_year) / 100.0,
        oxygen_price_eur_per_t=float(st.session_state.oxygen_price_eur_per_t),
        oxygen_price_escalation_per_year=float(st.session_state.oxygen_price_escalation_per_year) / 100.0,
        waste_heat_price_eur_per_mwh=float(st.session_state.waste_heat_price_eur_per_mwh),
        waste_heat_usable_share=float(st.session_state.waste_heat_usable_share) / 100.0,
        waste_heat_price_escalation_per_year=float(st.session_state.waste_heat_price_escalation_per_year) / 100.0,
        balancing_energy_enabled=bool(st.session_state.balancing_energy_enabled),
        balancing_energy_revenue_eur_per_year=float(st.session_state.balancing_energy_revenue_eur_per_year),
        balancing_energy_escalation_per_year=float(st.session_state.balancing_energy_escalation_per_year) / 100.0,
        other_revenues_enabled=bool(st.session_state.other_revenues_enabled),
        other_revenue_1_eur_per_year=float(st.session_state.other_revenue_1_eur_per_year),
        other_revenue_1_escalation_per_year=float(st.session_state.other_revenue_1_escalation_per_year) / 100.0,
        other_revenue_2_eur_per_year=float(st.session_state.other_revenue_2_eur_per_year),
        other_revenue_2_escalation_per_year=float(st.session_state.other_revenue_2_escalation_per_year) / 100.0,
    )

    return ModelInputs(
        system=system, capex=capex, opex=opex, power=power, revenue=revenue,
        electricity_costs=electricity_costs, funding=funding,
    )

def read_numeric_csv_series(uploaded_file, expected_length: int = 8760) -> np.ndarray:
    df = pd.read_csv(uploaded_file)
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if not numeric_cols:
        raise ValueError("CSV enthält keine numerische Spalte.")

    values = df[numeric_cols[0]].to_numpy(dtype=float)

    if len(values) != expected_length:
        raise ValueError(f"Es wurden {len(values)} Werte gefunden, erwartet werden {expected_length}.")

    if np.any(~np.isfinite(values)):
        raise ValueError("Die Zeitreihe enthält ungültige Werte.")

    return values

init_ui_state()


# ============================================================
# Sidebar
# ============================================================


if st.sidebar.button("Berechnung starten", type="primary", use_container_width=True):
    try:
        model_inputs = build_model_inputs_from_ui()
        dispatch_df = build_dispatch(model_inputs, st.session_state.timeseries_df)
        results = compute_lcoh(model_inputs, dispatch_df)

        st.session_state.result_bundle = {
            "inputs": model_inputs,
            "dispatch": dispatch_df,
            "results": results,
        }
    except Exception as e:
        st.sidebar.error(f"Fehler: {e}")

st.sidebar.title("Key Performance Indicators")
st.sidebar.divider()

if st.session_state.result_bundle is None:
    st.sidebar.info("Noch keine Ergebnisse verfügbar.")
else:
    r = st.session_state.result_bundle["results"]
    st.sidebar.metric("LCOH", f"{de_number(r['lcoh_eur_per_kg'], 2)} €/kg")
    st.sidebar.metric("H₂-Produktion", f"{de_number(r['annual_h2_kg'] / 1000.0, 0)} t/a")
    st.sidebar.metric("Volllaststunden", f"{de_number(r['equivalent_full_load_hours'], 0)} h/a")
    st.sidebar.metric(
        "Strompreis Elektrolyseur",
        f"{de_number(r['electricity_price_ely_eur_per_mwh'], 2)} €/MWh",
    )


# ============================================================
# Hauptlayout
# ============================================================

st.title("Berechnungstool LCOH")
st.caption(
    "Tool zur Berechnung von Wasserstoffgestehungskosten (Levelised Cost of Hydrogen)"
)

tabs = st.tabs(
    [
        "1) System",
        "2) CAPEX",
        "3) OPEX",
        "4) Strom & Zeitreihen",
        "5) Förderungen",
        "6) Ergebnisse",
        "7) Sensitivität",
    ]
)


# ============================================================
# Tab 1: System
# ============================================================

with tabs[0]:
    st.subheader("Systemparameter")

    with st.expander("Allgemeine Projektparameter", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.number_input(
                "Inbetriebnahmejahr",
                min_value=2000,
                max_value=2100,
                step=1,
                key="commissioning_year",
            )

        with c2:
            st.number_input(
                "Projektlaufzeit [a]",
                min_value=1,
                max_value=50,
                step=1,
                key="project_lifetime_years",
            )

    with st.expander("Leistungsdaten", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.number_input(
                "Elektrolyseurleistung [kW]",
                min_value=1.0,
                max_value=1_000_000.0,
                step=100.0,
                key="electrolyzer_power_kw",
            )

        with c2:
            st.slider(
                "Stromverbrauch Peripherie [% vom Ely-Verbrauch]",
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                key="peripheral_power_fraction",
                help=HELP["peripheral_power_fraction"],
            )
            st.caption(
                f"Berechnete Systemleistung: "
                f"{st.session_state.electrolyzer_power_kw * (1 + st.session_state.peripheral_power_fraction / 100):,.0f} kW"
            )

        with c3:
            percent_slider(
                "Mindestlast",
                key="min_load_fraction",
                help=HELP["min_load_fraction"],
            )

    with st.expander("Wirkungsgrad & Degradation", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            percent_slider(
                "Nennwirkungsgrad Elektrolyse η",
                key="avg_efficiency_h2_per_el",
                help=HELP["avg_efficiency_h2_per_el"],
            )

        with c2:
            st.number_input(
                "Stack-Lebensdauer [h]",
                min_value=1_000.0,
                max_value=500_000.0,
                step=1_000.0,
                key="stack_lifetime_hours",
                help=HELP["stack_lifetime_hours"],
            )

        with c3:
            percent_slider(
                "Degradation pro Jahr [%‑Punkte/a]",
                key="degradation_per_year",
                help=HELP["degradation_per_year"],
            )


# ============================================================
# Tab 2: CAPEX
# ============================================================

with tabs[1]:
    st.subheader("CAPEX & Finanzierung")

    with st.expander("Allgemeine CAPEX", expanded=True):
        c1, c2 = st.columns(2)

        with c1:
            st.number_input(
                "Spez. Investitionskosten Elektrolyseur [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="electrolyzer_invest_eur_per_kw",
                help=HELP["electrolyzer_invest_eur_per_kw"],
            )
            st.number_input(
                "Engineering, Procurement & Construction [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="epc_eur_per_kw",
            )
            st.number_input(
                "Hochbau [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="hochbau_eur_per_kw",
            )
            st.number_input(
                "Individuelle CAPEX pro Leistung [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="individual_specific_eur_per_kw",
            )
            st.slider(
                "Individuelle CAPEX [% der Ely-Kosten]",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
                key="individual_ely_cost_share",
            )

        with c2:
            st.number_input(
                "Peripherie / Balance of Plant [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="bop_eur_per_kw",
                help=HELP["bop_eur_per_kw"],
            )
            st.number_input(
                "Tiefbau [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="tiefbau_eur_per_kw",
            )
            st.number_input(
                "Individuelle CAPEX pauschal [€]",
                min_value=0.0,
                max_value=1_000_000_000.0,
                step=10_000.0,
                key="individual_fixed_eur",
            )

    with st.expander("Abwärme", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.checkbox(
                "Abwärme nutzbar", key="waste_heat_enabled",
                help=HELP["waste_heat_enabled"],
            )
            st.number_input(
                "Abwärmesystemkosten [€/kW]",
                min_value=0.0, max_value=100_000.0, step=10.0,
                key="waste_heat_system_eur_per_kw",
                disabled=not st.session_state.waste_heat_enabled,
            )
        with c2:
            st.number_input(
                "Verkaufspreis Abwärme [€/MWh]",
                min_value=0.0, max_value=10_000.0, step=1.0,
                key="waste_heat_price_eur_per_mwh",
                disabled=not st.session_state.waste_heat_enabled,
            )
            st.slider(
                "Nutzbarer Anteil Abwärme [%]", 0.0, 100.0, 1.0,
                key="waste_heat_usable_share",
                disabled=not st.session_state.waste_heat_enabled,
            )
        with c3:
            st.slider(
                "Preisentwicklung Abwärme [%/a]", -20.0, 30.0, 0.5,
                key="waste_heat_price_escalation_per_year",
                disabled=not st.session_state.waste_heat_enabled,
                help=HELP["price_escalation"],
            )

    with st.expander("Sauerstoff", expanded=False):
        st.checkbox(
            "Sauerstoff nutzbar und aufbereiten", key="oxygen_enabled",
            help=HELP["oxygen_enabled"],
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input(
                "Sauerstoffsystemkosten [€/kW]",
                min_value=0.0, max_value=100_000.0, step=10.0,
                key="oxygen_system_eur_per_kw",
                disabled=not st.session_state.oxygen_enabled,
            )
            st.number_input(
                "Verdichterdruck O₂ [bar]", min_value=0.01, max_value=2_000.0, step=1.0,
                key="oxygen_compressor_outlet_pressure_bar",
                disabled=not st.session_state.oxygen_enabled,
            )
        with c2:
            st.number_input(
                "Eingangsdruck O₂ [bar]", min_value=0.01, max_value=1_000.0, step=1.0,
                key="oxygen_compressor_inlet_pressure_bar",
                disabled=not st.session_state.oxygen_enabled,
            )
            st.number_input(
                "Eintrittstemperatur O₂ [°C]", min_value=-250.0, max_value=1_000.0, step=1.0,
                key="oxygen_compressor_inlet_temperature_c",
                disabled=not st.session_state.oxygen_enabled,
            )
            st.slider(
                "Wirkungsgrad O₂-Kompressor [%]", 1.0, 100.0, 1.0,
                key="oxygen_compressor_efficiency",
                disabled=not st.session_state.oxygen_enabled,
            )
        with c3:
            st.number_input(
                "Verkaufspreis Sauerstoff [€/t]", min_value=0.0, max_value=100_000.0, step=1.0,
                key="oxygen_price_eur_per_t",
                disabled=not st.session_state.oxygen_enabled,
            )
            st.slider(
                "Preisentwicklung Sauerstoff [%/a]", -20.0, 30.0, 0.5,
                key="oxygen_price_escalation_per_year",
                disabled=not st.session_state.oxygen_enabled,
                help=HELP["price_escalation"],
            )

    with st.expander("H₂-Aufbereitung", expanded=False):
        st.checkbox(
            "H₂ wird verdichtet", key="compression_enabled",
            help=HELP["h2_processing"],
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input(
                "Direktsystemkosten [€/kW]", min_value=0.0, max_value=100_000.0, step=10.0,
                key="h2_direct_system_eur_per_kw", disabled=st.session_state.compression_enabled,
            )
            st.number_input(
                "Verdichtersystemkosten [€/kW]", min_value=0.0, max_value=100_000.0, step=10.0,
                key="compressor_system_eur_per_kw", disabled=not st.session_state.compression_enabled,
            )
            st.slider(
                "Anteil des jährlich produzierten H₂ zur Verdichtung [%]", 0.0, 100.0, 1.0,
                key="h2_processed_share", disabled=not st.session_state.compression_enabled,
            )
        with c2:
            st.number_input(
                "Verdichterdruck H₂ [bar]", min_value=0.01, max_value=2_000.0, step=1.0,
                key="h2_compressor_outlet_pressure_bar", disabled=not st.session_state.compression_enabled,
            )
            st.number_input(
                "Eingangsdruck H₂ [bar]", min_value=0.01, max_value=1_000.0, step=1.0,
                key="h2_compressor_inlet_pressure_bar", disabled=not st.session_state.compression_enabled,
            )
        with c3:
            st.number_input(
                "Eintrittstemperatur H₂ [°C]", min_value=-250.0, max_value=1_000.0, step=1.0,
                key="h2_compressor_inlet_temperature_c", disabled=not st.session_state.compression_enabled,
            )
            st.slider(
                "Wirkungsgrad H₂-Kompressor [%]", 1.0, 100.0, 1.0,
                key="h2_compressor_efficiency", disabled=not st.session_state.compression_enabled,
            )

    with st.expander("Batteriesystem", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.checkbox("Batteriesystem wird genutzt", key="battery_enabled")
            st.number_input(
                "Faktor für Speicherkapazität [kWh pro kW Systemleistung]",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
                key="battery_capacity_factor_kwh_per_kw",
                disabled=not st.session_state.battery_enabled,
            )
        with c2:
            st.number_input(
                "Installierte Eingangsleistung [kW]",
                min_value=0.0,
                max_value=1_000_000.0,
                step=100.0,
                key="battery_power_kw",
                disabled=not st.session_state.battery_enabled,
            )
            st.number_input(
                "Investitionskosten [€/kWh]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="battery_invest_eur_per_kwh",
                disabled=not st.session_state.battery_enabled,
            )
            st.number_input(
                "Sonstige Batteriekosten [€]",
                min_value=0.0,
                max_value=1_000_000_000.0,
                step=10_000.0,
                key="battery_fixed_eur",
                disabled=not st.session_state.battery_enabled,
            )

    with st.expander("Stacktausch & Finanzierung", expanded=True):
        st.markdown("**Stacktausch**")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.slider(
                "Kosten Stacktausch [% der Ely-Investitionskosten]",
                min_value=0.0, max_value=100.0, step=1.0,
                key="stack_replacement_share_of_ely_capex",
                help=HELP["stack_replacement_share"],
            )
        with c2:
            st.slider(
                "Kostendegression Stack [%/a]",
                min_value=-20.0, max_value=20.0, step=0.5,
                key="stack_cost_degression_per_year",
                help=HELP["stack_cost_degression"],
            )
        with c3:
            st.slider(
                "Zins Stackfinanzierung [%/a]",
                min_value=0.0, max_value=30.0, step=0.5,
                key="stack_financing_interest_rate",
            )

        st.markdown("**Projektfinanzierung**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.slider("Fremdkapitalquote [%]", 0.0, 100.0, 1.0, key="debt_share")
        with c2:
            st.slider("Zins Fremdkapital [%/a]", 0.0, 30.0, 0.5, key="debt_interest_rate")
        with c3:
            st.slider(
                "Kalkulatorischer Zins Eigenkapital [%/a]", 0.0, 30.0, 0.5,
                key="equity_interest_rate", help=HELP["equity_interest_rate"],
            )
        with c4:
            st.slider("Unternehmenssteuersatz (WACC) [%]", 0.0, 60.0, 1.0, key="corporate_tax_rate")

# ============================================================
# Tab 3: OPEX
# ============================================================

with tabs[2]:
    st.subheader("OPEX")

    with st.expander("OPEX pauschal (Alternative zur Detailrechnung)", expanded=False):
        st.checkbox(
            "OPEX Total als pauschalen User Input verwenden",
            key="lump_sum_enabled",
            help=HELP["opex_lump_sum"],
        )
        c1, c2 = st.columns(2)
        with c1:
            st.slider(
                "OPEX Total [% von CAPEX nach CAPEX-Förderung]",
                min_value=0.0, max_value=25.0, step=0.05,
                key="lump_sum_share_of_capex",
                disabled=not st.session_state.lump_sum_enabled,
                format="%.2f",
            )
        with c2:
            st.slider(
                "Preisentwicklung OPEX pauschal [%/a]",
                min_value=-20.0, max_value=30.0, step=0.05,
                key="lump_sum_escalation_per_year",
                disabled=not st.session_state.lump_sum_enabled,
                format="%.2f",
                help=HELP["price_escalation"],
            )
        if st.session_state.lump_sum_enabled:
            st.info(
                "Die detaillierten OPEX-Eingaben darunter werden weiterhin angezeigt, "
                "aber für OPEX Total nicht verwendet. Dies entspricht der Excel-Umschaltung."
            )

    with st.expander("Wartung & Instandhaltung", expanded=True):
        c1, c2 = st.columns(2)

        with c1:
            st.slider(
                "Gesamt Wartung & Instandhaltung [% von CAPEX Total]",
                min_value=0.0,
                max_value=10.0,
                step=0.05,
                key="maintenance_share_of_capex",
                format="%.2f",
            )

        with c2:
            st.slider(
                "Preisentwicklung pro Jahr [%]",
                min_value=0.0,
                max_value=10.0,
                step=0.05,
                key="maintenance_escalation_per_year",
                format="%.2f",
            )

    with st.expander("Personalkosten", expanded=True):
        c1, c2 = st.columns(2)

        with c1:
            st.number_input(
                "Gesamt Personalkosten abzgl. W&I [€ / a]",
                min_value=0.0,
                max_value=100_000_000.0,
                step=1_000.0,
                key="personnel_eur_per_year",
            )

        with c2:
            st.slider(
                "Preisentwicklung pro Jahr [%]",
                min_value=0.0,
                max_value=10.0,
                step=0.05,
                key="personnel_escalation_per_year",
                format="%.2f",
            )

    with st.expander("Rückstellungen (ohne Stacktausch)", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.slider(
                "Ersatzinvest. Restliche Anlage [% von CAPEX Total]",
                min_value=0.0,
                max_value=10.0,
                step=0.05,
                key="reserve_remaining_plant_share_of_capex",
                format="%.2f",
            )

        with c2:
            st.slider(
                "Rückbau [% von CAPEX Total]",
                min_value=0.0,
                max_value=10.0,
                step=0.05,
                key="reserve_decommissioning_share_of_capex",
                format="%.2f",
            )

        with c3:
            st.slider(
                "Preisentwicklung pro Jahr [%]",
                min_value=0.0,
                max_value=10.0,
                step=0.05,
                key="reserve_escalation_per_year",
                format="%.2f",
            )

    with st.expander("Wasser", expanded=True):
        c1, c2 = st.columns(2)

        with c1:
            st.number_input(
                "Preis Frischwasser [€ / m³]",
                min_value=0.0,
                max_value=1_000.0,
                step=0.1,
                key="freshwater_price_eur_per_m3",
            )
            st.number_input(
                "Preis Aufbereitung Frischwasser [€ / m³]",
                min_value=0.0,
                max_value=1_000.0,
                step=0.1,
                key="freshwater_treatment_price_eur_per_m3",
            )

        with c2:
            st.number_input(
                "Preis Abwasser [€ / m³]",
                min_value=0.0,
                max_value=1_000.0,
                step=0.1,
                key="wastewater_price_eur_per_m3",
            )
            st.slider(
                "Preisentwicklung pro Jahr [%]",
                min_value=0.0,
                max_value=10.0,
                step=0.05,
                key="water_escalation_per_year",
                format="%.2f",
            )

    with st.expander("Individuelle OPEX", expanded=True):
        c1, c2 = st.columns(2)

        with c1:
            st.slider(
                "Individuelle OPEX [% von CAPEX Total]",
                min_value=0.0,
                max_value=10.0,
                step=0.05,
                key="individual_opex_share_of_capex",
                format="%.2f",
            )

        with c2:
            st.slider(
                "Preisentwicklung pro Jahr [%]",
                min_value=0.0,
                max_value=10.0,
                step=0.05,
                key="individual_opex_escalation_per_year",
                format="%.2f",
            )


    with st.expander("Weitere Einnahmen – THG-Quote", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.checkbox("THG-Quote berücksichtigen", key="thg_enabled", help=HELP["thg_quote"])
            st.number_input(
                "Preis THG-Quote [€/t CO₂]", min_value=0.0, max_value=10_000.0, step=10.0,
                key="thg_price_eur_per_tco2", disabled=not st.session_state.thg_enabled,
            )
        with c2:
            st.slider(
                "Anteil H₂ für Mobilitätssektor [%]", 0.0, 100.0, 1.0,
                key="mobility_share", disabled=not st.session_state.thg_enabled,
            )
            st.slider(
                "Anteil an THG-Einnahmen [%]", 0.0, 100.0, 1.0,
                key="thg_revenue_share", disabled=not st.session_state.thg_enabled,
            )
        with c3:
            st.number_input(
                "THG-Intensität grüner H₂ [kg CO₂/GJ]", min_value=0.0, max_value=100.0, step=0.5,
                key="h2_thg_intensity_kgco2_per_gj", disabled=not st.session_state.thg_enabled,
            )
            st.slider(
                "Preisentwicklung THG-Quote [%/a]", -20.0, 30.0, 0.5,
                key="thg_price_escalation_per_year", disabled=not st.session_state.thg_enabled,
                help=HELP["price_escalation"],
            )

    with st.expander("Weitere Einnahmen – Regelenergie", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.checkbox(
                "Regelenergie berücksichtigen",
                key="balancing_energy_enabled",
                help=HELP.get("balancing_energy"),
            )
        with c2:
            st.number_input(
                "Kalkulierter Ertrag [€/a]",
                min_value=0.0, max_value=1_000_000_000.0, step=10_000.0,
                key="balancing_energy_revenue_eur_per_year",
                disabled=not st.session_state.balancing_energy_enabled,
            )
        with c3:
            st.slider(
                "Jährliche Preissteigerung [%/a]",
                -20.0, 30.0, 0.5,
                key="balancing_energy_escalation_per_year",
                disabled=not st.session_state.balancing_energy_enabled,
                help=HELP["price_escalation"],
            )
        st.caption(
            "Wie Excel Rev. 8: Regelenergie wird nicht stündlich simuliert, sondern über einen extern kalkulierten Jahresertrag abgebildet."
        )

    with st.expander("Weitere Einnahmen – Sonstige", expanded=False):
        st.checkbox(
            "Sonstige Einnahmen berücksichtigen",
            key="other_revenues_enabled",
            help=HELP.get("other_revenues"),
        )
        c1, c2 = st.columns(2)
        with c1:
            st.number_input(
                "Sonstige Einnahmen 1 [€/a]",
                min_value=0.0, max_value=1_000_000_000.0, step=10_000.0,
                key="other_revenue_1_eur_per_year",
                disabled=not st.session_state.other_revenues_enabled,
            )
            st.slider(
                "Preisentwicklung Sonstige 1 [%/a]",
                -20.0, 30.0, 0.5,
                key="other_revenue_1_escalation_per_year",
                disabled=not st.session_state.other_revenues_enabled,
                help=HELP["price_escalation"],
            )
        with c2:
            st.number_input(
                "Sonstige Einnahmen 2 [€/a]",
                min_value=0.0, max_value=1_000_000_000.0, step=10_000.0,
                key="other_revenue_2_eur_per_year",
                disabled=not st.session_state.other_revenues_enabled,
            )
            st.slider(
                "Preisentwicklung Sonstige 2 [%/a]",
                -20.0, 30.0, 0.5,
                key="other_revenue_2_escalation_per_year",
                disabled=not st.session_state.other_revenues_enabled,
                help=HELP["price_escalation"],
            )


# ============================================================
# Tab 4: Strom & Zeitreihen
# ============================================================

with tabs[3]:
    st.subheader("Stromversorgung & Zeitreihen")

    # ------------------------------------------------------------
    # Baseload-PPA
    # ------------------------------------------------------------
    with st.expander("Baseload-PPA", expanded=False):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.checkbox("Baseload-PPA wird genutzt", key="baseload_enabled")

        with c2:
            st.number_input(
                "Baseload-PPA Leistung [kW]",
                min_value=0.0,
                max_value=1_000_000.0,
                step=100.0,
                key="baseload_kw",
                disabled=not st.session_state.baseload_enabled,
            )

        with c3:
            st.number_input(
                "Strompreis Baseload-PPA [€/MWh]",
                min_value=0.0,
                max_value=1_000.0,
                step=1.0,
                key="baseload_price_eur_per_mwh",
                disabled=not st.session_state.baseload_enabled,
            )

        st.slider(
            "Preisentwicklung Strompreis pro Jahr [%]",
            min_value=0.0,
            max_value=20.0,
            step=0.1,
            key="baseload_price_escalation_per_year",
            format="%.1f",
            disabled=not st.session_state.baseload_enabled,
        )

    # ------------------------------------------------------------
    # Pay-as-produced PPAs
    # ------------------------------------------------------------
    with st.expander("Pay-as-Produced PPAs", expanded=False):
        st.markdown("#### PV-PPA")
        c1, c2, c3 = st.columns(3)

        with c1:
            st.checkbox("PV-PPA wird genutzt", key="ppa_pv_enabled")

        with c2:
            st.number_input(
                "PV-PPA Leistung [kW]",
                min_value=0.0,
                max_value=1_000_000.0,
                step=100.0,
                key="ppa_pv_capacity_kw",
                disabled=not st.session_state.ppa_pv_enabled,
            )

        with c3:
            st.number_input(
                "PV-PPA Preis [€/MWh]",
                min_value=0.0,
                max_value=1_000.0,
                step=1.0,
                key="ppa_pv_price_eur_per_mwh",
                disabled=not st.session_state.ppa_pv_enabled,
            )

        st.markdown("#### Wind-PPA")
        c4, c5, c6 = st.columns(3)

        with c4:
            st.checkbox("Wind-PPA wird genutzt", key="ppa_wind_enabled")

        with c5:
            st.number_input(
                "Wind-PPA Leistung [kW]",
                min_value=0.0,
                max_value=1_000_000.0,
                step=100.0,
                key="ppa_wind_capacity_kw",
                disabled=not st.session_state.ppa_wind_enabled,
            )

        with c6:
            st.number_input(
                "Wind-PPA Preis [€/MWh]",
                min_value=0.0,
                max_value=1_000.0,
                step=1.0,
                key="ppa_wind_price_eur_per_mwh",
                disabled=not st.session_state.ppa_wind_enabled,
            )

        st.slider(
            "Preisentwicklung Strompreise pro Jahr [%]",
            min_value=0.0,
            max_value=20.0,
            step=0.1,
            key="ppa_price_escalation_per_year",
            format="%.1f",
        )

    # ------------------------------------------------------------
    # §7 nach 37. BImSchV
    # ------------------------------------------------------------
    with st.expander("§7 nach 37. BImSchV", expanded=False):
        st.caption(
            "Excel-kompatible stündliche Beschaffung nach §7 Abs. 3. Die Quelle wird vor §13k "
            "und vor dem unspezifischen Spotmarktbezug eingesetzt, wenn der Börsenpreis die "
            "aus CO₂-Preis und Spotpreisgrenze abgeleitete Schwelle nicht überschreitet."
        )
        c1, c2 = st.columns(2)
        with c1:
            st.checkbox(
                "Strombezug nach §7 aktivieren",
                key="section7_enabled",
                help=HELP["section7"],
            )
        with c2:
            st.checkbox(
                "Negative Börsenpreise berücksichtigen",
                key="section7_include_negative_prices",
                disabled=not st.session_state.section7_enabled,
                help=HELP["section7_negative_prices"],
            )

        c3, c4 = st.columns(2)
        with c3:
            st.selectbox(
                "CO₂-Preis",
                options=["Jahresdaten", "Eigener Wert"],
                key="section7_co2_price_mode",
                disabled=not st.session_state.section7_enabled,
            )
        with c4:
            st.number_input(
                "Eigener CO₂-Preis [€/t CO₂]",
                min_value=0.0,
                max_value=5_000.0,
                step=1.0,
                key="section7_co2_price_eur_per_t",
                disabled=(
                    not st.session_state.section7_enabled
                    or st.session_state.section7_co2_price_mode != "Eigener Wert"
                ),
            )

        st.slider(
            "Preisentwicklung CO₂ [%/a]",
            min_value=-20.0,
            max_value=30.0,
            step=0.5,
            key="section7_co2_price_escalation_per_year",
            disabled=not st.session_state.section7_enabled,
            help=HELP["price_escalation"],
        )

        if st.session_state.section7_co2_price_mode == "Jahresdaten":
            c5, c6 = st.columns([1, 2])
            with c5:
                if st.button("Excel-CO₂-Daten laden", key="co2_demo_btn"):
                    demo_df = make_demo_timeseries()
                    st.session_state.co2_price_text = timeseries_to_text(demo_df["co2_eur_per_t"])
            with c6:
                co2_upload = st.file_uploader(
                    "CO₂-Jahresdaten als CSV [€/t CO₂]",
                    type=["csv"],
                    key="co2_price_csv",
                )
                if co2_upload is not None and st.button("CO₂-CSV übernehmen", key="co2_csv_btn"):
                    try:
                        values = read_numeric_csv_series(co2_upload)
                        if np.any(values < 0):
                            raise ValueError("CO₂-Preise dürfen nicht negativ sein.")
                        st.session_state.co2_price_text = timeseries_to_text(values)
                        st.success("CO₂-CSV in Textfeld übernommen.")
                    except Exception as e:
                        st.error(f"CO₂-CSV konnte nicht gelesen werden: {e}")

            st.text_area(
                "CO₂-Preis: eine Zahl pro Stunde [€/t CO₂]",
                key="co2_price_text",
                height=180,
            )
            try:
                co2_values = parse_timeseries_text(
                    st.session_state.co2_price_text, expected_length=8760
                )
                if np.any(co2_values < 0):
                    raise ValueError("CO₂-Preise dürfen nicht negativ sein.")
                st.session_state.timeseries_df["co2_eur_per_t"] = co2_values
                st.success("CO₂-Zeitreihe gültig.")
                st.caption(
                    f"8760 Werte | min = {co2_values.min():.2f} €/t | "
                    f"max = {co2_values.max():.2f} €/t | Mittelwert = {co2_values.mean():.2f} €/t"
                )
            except Exception as e:
                st.error(f"Fehler in der CO₂-Zeitreihe: {e}")

    # ------------------------------------------------------------
    # §13k Nutzen statt Abregeln
    # ------------------------------------------------------------
    with st.expander('§13k EnWG – "Nutzen statt Abregeln"', expanded=False):
        st.caption(
            "Die stündlich verfügbare §13k-Menge wird nach PPA und §7, aber vor Batterie/Spotmarkt "
            "eingesetzt. Der Preis wird wie im Excel als eigener Arbeitspreis mit Preisentwicklung geführt."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.checkbox(
                "§13k-Strombezug aktivieren",
                key="section13k_enabled",
                help=HELP["section13k"],
            )
        with c2:
            st.number_input(
                "Strompreis §13k [€/MWh]",
                min_value=-500.0,
                max_value=5_000.0,
                step=1.0,
                key="section13k_price_eur_per_mwh",
                disabled=not st.session_state.section13k_enabled,
            )
        with c3:
            st.slider(
                "Preisentwicklung [%/a]",
                min_value=-20.0,
                max_value=30.0,
                step=0.5,
                key="section13k_price_escalation_per_year",
                disabled=not st.session_state.section13k_enabled,
                help=HELP["price_escalation"],
            )

        c4, c5 = st.columns([1, 2])
        with c4:
            if st.button("Excel-§13k-Daten laden", key="section13k_demo_btn"):
                demo_df = make_demo_timeseries()
                st.session_state.section13k_profile_text = timeseries_to_text(
                    demo_df["section13k_kwh"]
                )
        with c5:
            section13k_upload = st.file_uploader(
                "§13k-Jahresdaten als CSV [kWh/h]",
                type=["csv"],
                key="section13k_csv",
            )
            if section13k_upload is not None and st.button(
                "§13k-CSV übernehmen", key="section13k_csv_btn"
            ):
                try:
                    values = read_numeric_csv_series(section13k_upload)
                    if np.any(values < 0):
                        raise ValueError("§13k-Verfügbarkeiten dürfen nicht negativ sein.")
                    st.session_state.section13k_profile_text = timeseries_to_text(values)
                    st.success("§13k-CSV in Textfeld übernommen.")
                except Exception as e:
                    st.error(f"§13k-CSV konnte nicht gelesen werden: {e}")

        st.text_area(
            "Verfügbare §13k-Leistung: eine Zahl pro Stunde [kWh/h]",
            key="section13k_profile_text",
            height=180,
        )
        try:
            section13k_values = parse_timeseries_text(
                st.session_state.section13k_profile_text, expected_length=8760
            )
            if np.any(section13k_values < 0):
                raise ValueError("§13k-Verfügbarkeiten dürfen nicht negativ sein.")
            st.session_state.timeseries_df["section13k_kwh"] = section13k_values
            st.success("§13k-Zeitreihe gültig.")
            st.caption(
                f"8760 Werte | {np.sum(section13k_values > 0):.0f} Stunden mit Angebot | "
                f"Jahresangebot = {section13k_values.sum()/1000:.0f} MWh"
            )
        except Exception as e:
            st.error(f"Fehler in der §13k-Zeitreihe: {e}")

    # ------------------------------------------------------------
    # Stromnebenkosten und Privilegierungen
    # ------------------------------------------------------------
    with st.expander("Stromnebenkosten & Privilegierungen", expanded=False):
        st.caption(
            "Die Werte und die getrennten Befreiungsstatus für Elektrolyseur und Restverbrauch "
            "entsprechen dem Aufbau von Excel-Blatt 5. Eine aktivierte Befreiung setzt den jeweiligen "
            "Kostenbestandteil auf 0 €/MWh."
        )
        h1, h2, h3, h4 = st.columns([1.7, 1.2, 1.0, 1.0])
        h1.markdown("**Kostenbestandteil**")
        h2.markdown("**Satz [ct/kWh]**")
        h3.markdown("**Befreiung Ely**")
        h4.markdown("**Befreiung Rest**")

        surcharge_rows = [
            ("Netzentgelt", "grid_fee_ct_per_kwh", "grid_fee"),
            ("Stromsteuer", "electricity_tax_ct_per_kwh", "electricity_tax"),
            ("Konzessionsabgabe", "concession_fee_ct_per_kwh", "concession_fee"),
            ("KWK-Aufschlag", "kwk_levy_ct_per_kwh", "kwk_levy"),
            ("StromNEV-§19", "stromnev19_levy_ct_per_kwh", "stromnev19_levy"),
            ("Offshore-Netzumlage", "offshore_levy_ct_per_kwh", "offshore_levy"),
        ]
        for label, value_key, exemption_key in surcharge_rows:
            c1, c2, c3, c4 = st.columns([1.7, 1.2, 1.0, 1.0])
            c1.write(label)
            with c2:
                st.number_input(
                    label,
                    min_value=0.0,
                    max_value=100.0,
                    step=0.001,
                    key=value_key,
                    label_visibility="collapsed",
                )
            with c3:
                st.checkbox(
                    f"Ely {label}",
                    key=f"electrolyzer_{exemption_key}_exempt",
                    label_visibility="collapsed",
                )
            with c4:
                st.checkbox(
                    f"Rest {label}",
                    key=f"rest_{exemption_key}_exempt",
                    label_visibility="collapsed",
                )

        st.divider()
        st.markdown("**Leistungspreis**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.number_input(
                "Leistungspreis Elektrolyseur [€/kW·Monat]",
                min_value=0.0,
                max_value=10_000.0,
                step=0.1,
                key="electrolyzer_demand_charge_eur_per_kw_month",
            )
        with c2:
            st.checkbox(
                "Befreiung Leistungspreis Ely",
                key="electrolyzer_demand_charge_exempt",
            )
        with c3:
            st.number_input(
                "Leistungspreis Rest [€/kW·Monat]",
                min_value=0.0,
                max_value=10_000.0,
                step=0.1,
                key="rest_demand_charge_eur_per_kw_month",
            )
        with c4:
            st.checkbox(
                "Befreiung Leistungspreis Rest",
                key="rest_demand_charge_exempt",
            )

    # ------------------------------------------------------------
    # PV-Profil
    # ------------------------------------------------------------
    with st.expander("PV-Profil", expanded=False):
        c1, c2 = st.columns([1, 2])

        with c1:
            if st.button("PV-Demo-Profil laden", key="pv_demo_btn"):
                demo_df = make_demo_timeseries()
                st.session_state.pv_profile_text = timeseries_to_text(demo_df["pv_kwh_per_kw"])

        with c2:
            pv_upload = st.file_uploader("PV-Profil als CSV", type=["csv"], key="pv_profile_csv")
            if pv_upload is not None and st.button("PV-CSV übernehmen", key="pv_csv_btn"):
                try:
                    values = read_numeric_csv_series(pv_upload)
                    if np.any(values < 0) or np.any(values > 1):
                        raise ValueError("PV-Profilwerte müssen zwischen 0 und 1 liegen.")
                    st.session_state.pv_profile_text = timeseries_to_text(values)
                    st.success("PV-CSV in Textfeld übernommen.")
                except Exception as e:
                    st.error(f"PV-CSV konnte nicht gelesen werden: {e}")

        st.text_area(
            "PV-Profil: eine Zahl pro Stunde (0 bis 1)",
            key="pv_profile_text",
            height=220,
        )

        try:
            pv_values = parse_timeseries_text(st.session_state.pv_profile_text, expected_length=8760)
            if np.any(pv_values < 0) or np.any(pv_values > 1):
                raise ValueError("Alle PV-Werte müssen zwischen 0 und 1 liegen.")

            st.session_state.timeseries_df["pv_kwh_per_kw"] = pv_values

            st.success("PV-Profil gültig.")
            st.caption(
                f"8760 Werte | min = {pv_values.min():.3f} | "
                f"max = {pv_values.max():.3f} | Mittelwert = {pv_values.mean():.3f}"
            )
        except Exception as e:
            st.error(f"Fehler im PV-Profil: {e}")

    # ------------------------------------------------------------
    # Wind-Profil
    # ------------------------------------------------------------
    with st.expander("Wind-Profil", expanded=False):
        c1, c2 = st.columns([1, 2])

        with c1:
            if st.button("Wind-Demo-Profil laden", key="wind_demo_btn"):
                demo_df = make_demo_timeseries()
                st.session_state.wind_profile_text = timeseries_to_text(demo_df["wind_kwh_per_kw"])

        with c2:
            wind_upload = st.file_uploader("Wind-Profil als CSV", type=["csv"], key="wind_profile_csv")
            if wind_upload is not None and st.button("Wind-CSV übernehmen", key="wind_csv_btn"):
                try:
                    values = read_numeric_csv_series(wind_upload)
                    if np.any(values < 0) or np.any(values > 1):
                        raise ValueError("Wind-Profilwerte müssen zwischen 0 und 1 liegen.")
                    st.session_state.wind_profile_text = timeseries_to_text(values)
                    st.success("Wind-CSV in Textfeld übernommen.")
                except Exception as e:
                    st.error(f"Wind-CSV konnte nicht gelesen werden: {e}")

        st.text_area(
            "Wind-Profil: eine Zahl pro Stunde (0 bis 1)",
            key="wind_profile_text",
            height=220,
        )

        try:
            wind_values = parse_timeseries_text(st.session_state.wind_profile_text, expected_length=8760)
            if np.any(wind_values < 0) or np.any(wind_values > 1):
                raise ValueError("Alle Wind-Werte müssen zwischen 0 und 1 liegen.")

            st.session_state.timeseries_df["wind_kwh_per_kw"] = wind_values

            st.success("Wind-Profil gültig.")
            st.caption(
                f"8760 Werte | min = {wind_values.min():.3f} | "
                f"max = {wind_values.max():.3f} | Mittelwert = {wind_values.mean():.3f}"
            )
        except Exception as e:
            st.error(f"Fehler im Wind-Profil: {e}")

    # ------------------------------------------------------------
    # Spotmarktbezug
    # ------------------------------------------------------------
    with st.expander("Spotmarktbezug", expanded=False):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.checkbox(
                "Fehlenden Strom auf dem Spotmarkt kaufen",
                key="spot_purchase_enabled",
            )

        with c2:
            st.checkbox(
                "Maximalpreis verwenden",
                key="spot_purchase_price_limit_enabled",
                disabled=not st.session_state.spot_purchase_enabled,
            )

        with c3:
            st.number_input(
                "Maximaler Spotpreis [€/MWh]",
                min_value=-500.0,
                max_value=5_000.0,
                step=1.0,
                key="spot_purchase_price_limit_eur_per_mwh",
                disabled=(
                    not st.session_state.spot_purchase_enabled
                    or not st.session_state.spot_purchase_price_limit_enabled
                ),
            )

        st.slider(
            "Preisentwicklung Spot-Einkauf [%/a]",
            min_value=-20.0, max_value=30.0, step=0.5,
            key="spot_price_escalation_per_year",
            disabled=not st.session_state.spot_purchase_enabled,
            help=HELP["price_escalation"],
        )


    # ------------------------------------------------------------
    # Stromhandel / Überschussverkauf (Excel C206:C209)
    # ------------------------------------------------------------
    with st.expander("Stromhandel / Überschussverkauf", expanded=False):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.checkbox(
                "Überschüssigen Strom verkaufen",
                key="spot_sale_enabled",
                help=HELP.get("power_sale_enabled"),
            )

        with c2:
            st.selectbox(
                "Stromhandel",
                options=["Spotmarkt", "PPA"],
                key="power_sale_mode",
                disabled=not st.session_state.spot_sale_enabled,
                help=HELP.get("power_sale_mode"),
            )

        with c3:
            st.number_input(
                "PPA-Verkaufspreis heute [€/MWh]",
                min_value=-500.0,
                max_value=5_000.0,
                step=1.0,
                key="ppa_sale_price_eur_per_mwh",
                disabled=(
                    not st.session_state.spot_sale_enabled
                    or st.session_state.power_sale_mode != "PPA"
                ),
                help=HELP.get("ppa_sale_price"),
            )

        st.slider(
            "Jährliche Verkaufspreisentwicklung [%/a]",
            min_value=-20.0, max_value=30.0, step=0.5,
            key="spot_sale_price_escalation_per_year",
            disabled=not st.session_state.spot_sale_enabled,
            help=HELP["price_escalation"],
        )

        if st.session_state.power_sale_mode == "Spotmarkt":
            st.markdown("**Optionale Mindestpreisgrenze**")
            c4, c5 = st.columns(2)
            with c4:
                st.checkbox(
                    "Minimalpreis verwenden",
                    key="spot_sale_price_limit_enabled",
                    disabled=not st.session_state.spot_sale_enabled,
                    help="Zusätzliche Streamlit-Option; Excel Rev. 8 verkauft im Spotmodus ohne diese Mindestpreisgrenze.",
                )
            with c5:
                st.number_input(
                    "Minimaler Spotpreis [€/MWh]",
                    min_value=-500.0,
                    max_value=5_000.0,
                    step=1.0,
                    key="spot_sale_min_price_eur_per_mwh",
                    disabled=(
                        not st.session_state.spot_sale_enabled
                        or not st.session_state.spot_sale_price_limit_enabled
                    ),
                )

        st.caption(
            "Excel Rev. 8 bewertet die übrige Strommenge wahlweise zum Spotmarktpreis oder zu einem PPA-Verkaufspreis. "
            "Negative Spotpreise werden einnahmeseitig auf 0 €/MWh begrenzt. Die Verkaufspreisentwicklung gilt in beiden Modi."
        )

    # ------------------------------------------------------------
    # Spotmarktpreise
    # ------------------------------------------------------------
    with st.expander("Spotmarktpreise", expanded=False):
        c1, c2 = st.columns([1, 2])

        with c1:
            if st.button("Demo-Spotpreise laden", key="spot_demo_btn"):
                demo_df = make_demo_timeseries()
                st.session_state.spot_price_text = timeseries_to_text(demo_df["day_ahead_eur_per_mwh"])

        with c2:
            spot_upload = st.file_uploader("Spotpreise als CSV [€/MWh]", type=["csv"], key="spot_price_csv")
            if spot_upload is not None and st.button("Spotpreis-CSV übernehmen", key="spot_csv_btn"):
                try:
                    values = read_numeric_csv_series(spot_upload)
                    st.session_state.spot_price_text = timeseries_to_text(values)
                    st.success("Spotpreis-CSV in Textfeld übernommen.")
                except Exception as e:
                    st.error(f"Spotpreis-CSV konnte nicht gelesen werden: {e}")

        st.text_area(
            "Spotpreise: eine Zahl pro Stunde [€/MWh]",
            key="spot_price_text",
            height=220,
        )

        try:
            spot_values = parse_timeseries_text(st.session_state.spot_price_text, expected_length=8760)
            st.session_state.timeseries_df["day_ahead_eur_per_mwh"] = spot_values

            st.success("Spotpreis-Zeitreihe gültig.")
            st.caption(
                f"8760 Werte | min = {spot_values.min():.2f} €/MWh | "
                f"max = {spot_values.max():.2f} €/MWh | Mittelwert = {spot_values.mean():.2f} €/MWh"
            )
        except Exception as e:
            st.error(f"Fehler in der Spotpreis-Zeitreihe: {e}")

    # ------------------------------------------------------------
    # Zeitreihen-Vorschau
    # ------------------------------------------------------------
    with st.expander("Zeitreihen-Vorschau", expanded=True):
        preview_df = st.session_state.timeseries_df.copy().reset_index(drop=True)

        # Textfelder noch einmal explizit in den DataFrame übernehmen
        try:
            preview_df["pv_kwh_per_kw"] = parse_timeseries_text(
                st.session_state.pv_profile_text,
                expected_length=8760,
            )
            preview_df["wind_kwh_per_kw"] = parse_timeseries_text(
                st.session_state.wind_profile_text,
                expected_length=8760,
            )
            preview_df["day_ahead_eur_per_mwh"] = parse_timeseries_text(
                st.session_state.spot_price_text,
                expected_length=8760,
            )
            preview_df["co2_eur_per_t"] = parse_timeseries_text(
                st.session_state.co2_price_text,
                expected_length=8760,
            )
            preview_df["section13k_kwh"] = parse_timeseries_text(
                st.session_state.section13k_profile_text,
                expected_length=8760,
            )

            st.session_state.timeseries_df = preview_df.copy()

        except Exception as e:
            st.warning(f"Zeitreihen konnten für die Vorschau nicht vollständig aktualisiert werden: {e}")

        preview_df["Stunde"] = np.arange(1, len(preview_df) + 1)

        def plot_timeseries_interactive(
            df: pd.DataFrame,
            y_col: str,
            title: str,
            y_label: str,
            as_percent: bool = False,
        ):
            y_values = df[y_col] * 100 if as_percent else df[y_col]

            fig = go.Figure()

            fig.add_trace(
                go.Scattergl(
                    x=df["Stunde"],
                    y=y_values,
                    mode="lines",
                    name=y_label,
                )
            )

            fig.update_layout(
                title=title,
                xaxis_title="Stunde des Jahres",
                yaxis_title=y_label,
                height=400,
                margin=dict(l=20, r=20, t=50, b=20),
                hovermode="x unified",
            )

            fig.update_xaxes(rangeslider_visible=True)

            render_plotly(fig)

        tab_pv, tab_wind, tab_spot, tab_co2, tab_13k = st.tabs(
            ["PV", "Wind", "Spotmarkt", "CO₂ (§7)", "§13k"]
        )

        with tab_pv:
            values = preview_df["pv_kwh_per_kw"]

            c1, c2, c3 = st.columns(3)
            c1.metric("Minimum", f"{(values.min())*100:.3f} %")
            c2.metric("Maximum", f"{(values.max())*100:.3f} %")
            c3.metric("Mittelwert", f"{(values.mean())*100:.3f} %")

            plot_timeseries_interactive(
                preview_df,
                y_col="pv_kwh_per_kw",
                title="PV-Profil über das Jahr",
                y_label="Normierte Leistung [%]",
                as_percent=True
            )

        with tab_wind:
            values = preview_df["wind_kwh_per_kw"]

            c1, c2, c3 = st.columns(3)
            c1.metric("Minimum", f"{(values.min())*100:.3f} %")
            c2.metric("Maximum", f"{(values.max())*100:.3f} %")
            c3.metric("Mittelwert", f"{(values.mean())*100:.3f} %")

            plot_timeseries_interactive(
                preview_df,
                y_col="wind_kwh_per_kw",
                title="Wind-Profil über das Jahr",
                y_label="Normierte Leistung [%]",
                as_percent=True
            )

        with tab_spot:
            values = preview_df["day_ahead_eur_per_mwh"]

            c1, c2, c3 = st.columns(3)
            c1.metric("Minimum", f"{values.min():.2f} €/MWh")
            c2.metric("Maximum", f"{values.max():.2f} €/MWh")
            c3.metric("Mittelwert", f"{values.mean():.2f} €/MWh")

            plot_timeseries_interactive(
                preview_df,
                y_col="day_ahead_eur_per_mwh",
                title="Spotmarktpreise über das Jahr",
                y_label="Spotpreis [€/MWh]",
            )

        with tab_co2:
            values = preview_df["co2_eur_per_t"]
            c1, c2, c3 = st.columns(3)
            c1.metric("Minimum", f"{values.min():.2f} €/t")
            c2.metric("Maximum", f"{values.max():.2f} €/t")
            c3.metric("Mittelwert", f"{values.mean():.2f} €/t")
            plot_timeseries_interactive(
                preview_df,
                y_col="co2_eur_per_t",
                title="CO₂-Preisreihe für §7",
                y_label="CO₂-Preis [€/t]",
            )

        with tab_13k:
            values = preview_df["section13k_kwh"]
            c1, c2, c3 = st.columns(3)
            c1.metric("Stunden mit Angebot", f"{int((values > 0).sum())} h")
            c2.metric("Maximalangebot", f"{values.max():.0f} kWh/h")
            c3.metric("Jahresangebot", f"{values.sum()/1000:.0f} MWh")
            plot_timeseries_interactive(
                preview_df,
                y_col="section13k_kwh",
                title="Verfügbare §13k-Strommenge",
                y_label="§13k [kWh/h]",
            )

# ============================================================
# Tab 5: Förderungen & Strompreiskompensation
# ============================================================

with tabs[4]:
    st.subheader("Förderungen & Strompreiskompensation")
    st.caption(
        "Dieser Bereich bildet Excel Rev. 8 C167:C193 nach. Strompreisprivilegierungen "
        "werden weiterhin im Tab 'Strom & Zeitreihen' eingestellt."
    )

    with st.expander("CAPEX-Förderung", expanded=True):
        st.selectbox(
            "CAPEX-Förderung auswählen",
            options=["Ohne", "Prozentual", "Absolut"],
            key="capex_subsidy_mode",
            help=HELP["capex_subsidy"],
        )
        c1, c2 = st.columns(2)
        with c1:
            st.slider(
                "Prozentuale Förderung [% der CAPEX vor Förderung]",
                min_value=0.0, max_value=100.0, step=0.5,
                key="capex_subsidy_percentage",
                disabled=st.session_state.capex_subsidy_mode != "Prozentual",
            )
        with c2:
            st.number_input(
                "Absolute Förderung [€/kW Elektrolyseur]",
                min_value=0.0, max_value=100_000.0, step=10.0,
                key="capex_subsidy_absolute_eur_per_kw",
                disabled=st.session_state.capex_subsidy_mode != "Absolut",
            )
        st.caption("Die Gesamtförderung reduziert direkt die zu finanzierenden CAPEX; für die Förderübersicht wird sie gleichmäßig auf die Projektlaufzeit verteilt.")

    with st.expander("OPEX-Förderung", expanded=True):
        st.selectbox(
            "OPEX-Förderung auswählen",
            options=["Ohne", "Pro kg", "Pro Volllaststunde"],
            key="opex_subsidy_mode",
            help=HELP["opex_subsidy"],
        )
        c1, c2 = st.columns(2)
        with c1:
            st.number_input(
                "Förderung [€/kg H₂]", min_value=0.0, max_value=10_000.0, step=0.01,
                key="opex_subsidy_eur_per_kg_h2",
                disabled=st.session_state.opex_subsidy_mode != "Pro kg",
            )
        with c2:
            st.number_input(
                "Förderung [€/Volllaststunde]", min_value=0.0, max_value=10_000_000.0, step=10.0,
                key="opex_subsidy_eur_per_full_load_hour",
                disabled=st.session_state.opex_subsidy_mode != "Pro Volllaststunde",
            )
        if not st.session_state.lump_sum_enabled and st.session_state.opex_subsidy_mode != "Ohne":
            st.warning(
                "Excel Rev. 8 weist diese Förderung im detaillierten OPEX-Modus zwar aus, "
                "zieht sie aber nicht von OPEX Total/LCOH ab. Der Python-Rechner bildet dieses "
                "Verhalten für Ergebnisparität bewusst nach. Bei aktivierter pauschaler OPEX wird sie abgezogen."
            )

    with st.expander("Strompreisförderung", expanded=True):
        st.selectbox(
            "Strompreisförderung auswählen",
            options=["Ohne", "Pro kg", "Pro MWh Strom"],
            key="electricity_subsidy_mode",
            help=HELP["electricity_subsidy"],
        )
        c1, c2 = st.columns(2)
        with c1:
            st.number_input(
                "Förderung [€/kg H₂]", min_value=0.0, max_value=10_000.0, step=0.01,
                key="electricity_subsidy_eur_per_kg_h2",
                disabled=st.session_state.electricity_subsidy_mode != "Pro kg",
            )
        with c2:
            st.number_input(
                "Förderung [€/MWh Systemstromverbrauch]", min_value=0.0, max_value=10_000.0, step=1.0,
                key="electricity_subsidy_eur_per_mwh",
                disabled=st.session_state.electricity_subsidy_mode != "Pro MWh Strom",
            )

    with st.expander("Strompreiskompensation (SPK)", expanded=True):
        st.selectbox(
            "Strompreiskompensation",
            options=["Ohne", "Rechner", "Separat"],
            key="spk_mode",
            help=HELP["spk"],
        )
        c1, c2 = st.columns(2)
        with c1:
            st.number_input(
                "EUA-Preis [€/t CO₂]", min_value=0.0, max_value=10_000.0, step=1.0,
                key="spk_eua_price_eur_per_tco2",
                disabled=st.session_state.spk_mode != "Rechner",
            )
            st.number_input(
                "Faktor zum Stromverbrauch", min_value=0.0, max_value=10.0, step=0.01,
                key="spk_power_consumption_factor",
                disabled=st.session_state.spk_mode != "Rechner",
            )
        with c2:
            st.slider(
                "Jährliche Preisentwicklung SPK [%/a]",
                min_value=-20.0, max_value=30.0, step=0.5,
                key="spk_price_escalation_per_year",
                disabled=st.session_state.spk_mode == "Ohne",
                help=HELP["price_escalation"],
            )
            st.number_input(
                "Separat kalkulierter SPK-Ertrag [€/a]",
                min_value=0.0, max_value=1_000_000_000.0, step=10_000.0,
                key="spk_separate_revenue_eur_per_year",
                disabled=st.session_state.spk_mode != "Separat",
            )
        if st.session_state.spk_mode == "Rechner":
            st.caption(
                "Excel-Rechner: 75 % Beihilfeintensität × 0,72 t CO₂/MWh × mittlerer EUA-Preis "
                "× Fallback-Faktor × förderfähiger Stromverbrauch."
            )


# ============================================================
# Tab 6: Ergebnisse
# ============================================================

with tabs[5]:
    st.subheader("Ergebnisse")

    def fmt_de(value: float, decimals: int = 2) -> str:
        if value is None:
            return "-"
        return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def fmt_int_de(value: float) -> str:
        if value is None:
            return "-"
        return f"{value:,.0f}".replace(",", ".")

    def fmt_pct_de(value_fraction: float, decimals: int = 1) -> str:
        if value_fraction is None:
            return "-"
        value_percent = value_fraction * 100.0
        return f"{value_percent:.{decimals}f}".replace(".", ",") + " %"

    bundle = st.session_state.result_bundle
    if bundle is None:
        st.info("Bitte die Berechnung über die Seitenleiste starten.")
    else:
        results = bundle["results"]
        dispatch_df = bundle["dispatch"]
        model_inputs = bundle["inputs"]

        # ----------------------------------------------------
        # Kompakte Ergebnisübersicht
        # ----------------------------------------------------
        gross_running_costs = (
            results["financing_eur_per_year"]
            + results["stack_replacement_eur_per_year"]
            + results["total_opex_eur_per_year"]
            + results["annual_power_cost_gross_eur"]
        )
        gross_running_lcoh = (
            gross_running_costs / results["annual_h2_kg"]
            if results["annual_h2_kg"] > 0 else np.nan
        )
        operating_relief = (
            results["electricity_subsidy_eur_per_year"]
            + results["spk_revenue_eur_per_year"]
            + results["total_other_revenues_eur_per_year"]
        )

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("LCOH", f"{fmt_de(results['lcoh_eur_per_kg'], 2)} €/kg")
        k2.metric("LCOH", f"{fmt_de(results['lcoh_ct_per_kwh'], 2)} ct/kWh")
        k3.metric("H₂-Produktion", f"{fmt_int_de(results['annual_h2_kg'])} kg/a")
        k4.metric("Volllaststunden", f"{fmt_int_de(results['equivalent_full_load_hours'])} h/a")
        k5.metric("Ø Wirkungsgrad", fmt_pct_de(results["average_efficiency_h2_per_el"], 1))

        k6, k7, k8, k9, k10 = st.columns(5)
        k6.metric("CAPEX nach Förderung", f"{fmt_de(results['total_capex_eur']/1e6, 2)} Mio. €")
        k7.metric("Strompreis Ely", f"{fmt_de(results['electricity_price_ely_eur_per_mwh'], 2)} €/MWh")
        k8.metric("LCOH vor lfd. Entlastungen", f"{fmt_de(gross_running_lcoh, 2)} €/kg")
        k9.metric("Lfd. Förderungen & Erlöse", f"{fmt_de(operating_relief/1e6, 2)} Mio. €/a")
        k10.metric("WACC (KPI)", fmt_pct_de(results["wacc"], 2))

        bridge_df = lcoh_bridge(results)
        cost_dist_df = positive_cost_distribution(results)
        revenue_dist_df = revenue_distribution(results)

        st.markdown("### LCOH-Zusammensetzung")
        chart_left, chart_right = st.columns([1.6, 1.0])
        with chart_left:
            bridge_nonzero = bridge_df[np.abs(bridge_df["€/kg H₂"]) > 1e-12].copy()
            waterfall = go.Figure(
                go.Waterfall(
                    orientation="v",
                    measure=["relative"] * len(bridge_nonzero) + ["total"],
                    x=bridge_nonzero["Komponente"].tolist() + ["LCOH"],
                    y=bridge_nonzero["€/kg H₂"].tolist() + [0.0],
                    text=[f"{v:.2f}" for v in bridge_nonzero["€/kg H₂"]] + [f"{results['lcoh_eur_per_kg']:.2f}"],
                    textposition="outside",
                    connector={"line": {"width": 1}},
                )
            )
            waterfall.update_layout(
                yaxis_title="€/kg H₂",
                showlegend=False,
                margin=dict(l=30, r=20, t=20, b=90),
                height=470,
            )
            render_plotly(waterfall)

        with chart_right:
            pie_cost = go.Figure(
                go.Pie(
                    labels=cost_dist_df["Komponente"],
                    values=cost_dist_df["€/a"],
                    hole=0.48,
                    textinfo="label+percent",
                )
            )
            pie_cost.update_layout(
                title="Jährliche positive Kosten",
                margin=dict(l=10, r=10, t=55, b=10),
                height=470,
                showlegend=False,
            )
            render_plotly(pie_cost)

        if not revenue_dist_df.empty:
            with st.expander("Förderungen & Erlöse im Überblick", expanded=False):
                relief_fig = go.Figure(
                    go.Bar(
                        x=revenue_dist_df["Komponente"],
                        y=revenue_dist_df["€/a"] / 1e6,
                        text=[f"{v/1e6:.2f}" for v in revenue_dist_df["€/a"]],
                        textposition="outside",
                    )
                )
                relief_fig.update_layout(
                    yaxis_title="Mio. €/a",
                    xaxis_title="",
                    margin=dict(l=30, r=20, t=20, b=80),
                    height=390,
                )
                render_plotly(relief_fig)

        # ----------------------------------------------------
        # Kostenstruktur
        # ----------------------------------------------------
        with st.expander("Kostenstruktur", expanded=True):
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.markdown("**CAPEX**")
                st.metric("CAPEX vor Förderung", f"{fmt_int_de(results['gross_capex_eur'])} €")
                st.metric("CAPEX nach Förderung", f"{fmt_int_de(results['total_capex_eur'])} €")
                st.metric("Finanzierung (FK + EK)", f"{fmt_int_de(results['financing_eur_per_year'])} €/a")
                st.metric("Stackersatz", f"{fmt_int_de(results['stack_replacement_eur_per_year'])} €/a")

            with c2:
                st.markdown("**OPEX**")
                st.metric("Wartung & Instandhaltung", f"{fmt_int_de(results['maintenance_eur_per_year'])} €/a")
                st.metric("Personalkosten", f"{fmt_int_de(results['personnel_eur_per_year'])} €/a")
                st.metric("Rückstellungen", f"{fmt_int_de(results['reserves_total_eur_per_year'])} €/a")
                st.metric("Wasserkosten", f"{fmt_int_de(results['water_eur_per_year'])} €/a")
                st.metric("Individuelle OPEX", f"{fmt_int_de(results['individual_opex_eur_per_year'])} €/a")

            with c3:
                st.markdown("**Stromkosten**")
                st.metric("Stromkosten brutto", f"{fmt_int_de(results['annual_power_cost_gross_eur'])} €/a")
                st.metric("Stromerlöse", f"{fmt_int_de(results['annual_power_revenue_eur'])} €/a")
                st.metric("Strompreisförderung", f"{fmt_int_de(results['electricity_subsidy_eur_per_year'])} €/a")
                st.metric("Stromkosten nach Förderung", f"{fmt_int_de(results['annual_power_cost_after_subsidy_eur'])} €/a")
                st.metric("Stromkosten netto inkl. Verkauf", f"{fmt_int_de(results['annual_power_cost_net_eur'])} €/a")         

            with c4:
                st.markdown("**Gesamtkosten & Erlöse**")
                st.metric("OPEX gesamt", f"{fmt_int_de(results['total_opex_eur_per_year'])} €/a")
                st.metric("THG-Quote", f"{fmt_int_de(results['thg_revenue_eur_per_year'])} €/a")
                st.metric("Stromverkauf", f"{fmt_int_de(results['power_sale_revenue_eur_per_year'])} €/a")
                st.metric("Sauerstoff + Abwärme", f"{fmt_int_de(results['oxygen_revenue_eur_per_year'] + results['waste_heat_revenue_eur_per_year'])} €/a")
                st.metric("Regelenergie", f"{fmt_int_de(results['balancing_energy_revenue_eur_per_year'])} €/a")
                st.metric("Sonstige Erlöse", f"{fmt_int_de(results['other_revenue_eur_per_year'])} €/a")
                st.metric("Weitere Erlöse gesamt", f"{fmt_int_de(results['total_other_revenues_eur_per_year'])} €/a")
                st.metric("Kosten nach Erlösen", f"{fmt_int_de(results['annual_costs_eur_per_year'])} €/a")

        # ----------------------------------------------------
        # Förderungen & Strompreiskompensation
        # ----------------------------------------------------
        with st.expander("Förderungen & Strompreiskompensation", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("CAPEX vor Förderung", f"{fmt_int_de(results['gross_capex_eur'])} €")
            c2.metric("CAPEX-Förderung gesamt", f"{fmt_int_de(results['capex_subsidy_total_eur'])} €")
            c3.metric("CAPEX nach Förderung", f"{fmt_int_de(results['total_capex_eur'])} €")
            c4.metric("CAPEX-Förderung Ø", f"{fmt_int_de(results['capex_subsidy_eur_per_year'])} €/a")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("OPEX-Förderung berechnet", f"{fmt_int_de(results['opex_subsidy_calculated_eur_per_year'])} €/a")
            c6.metric("OPEX-Förderung angewendet", f"{fmt_int_de(results['opex_subsidy_applied_eur_per_year'])} €/a")
            c7.metric("Strompreisförderung", f"{fmt_int_de(results['electricity_subsidy_eur_per_year'])} €/a")
            c8.metric("Ersparnis Privilegierungen", f"{fmt_int_de(results['privilege_savings_eur_per_year'])} €/a")

            c9, c10, c11 = st.columns(3)
            c9.metric("Strompreiskompensation", f"{fmt_int_de(results['spk_revenue_eur_per_year'])} €/a")
            c10.metric("Förderungen/Privilegien gesamt", f"{fmt_int_de(results['annual_funding_total_eur_per_year'])} €/a")
            c11.metric("OPEX-Modus", "Pauschal" if results['opex_calculation_mode'] == 'lump_sum' else "Detailliert")

            if results["opex_subsidy_calculated_eur_per_year"] > 0 and results["opex_subsidy_applied_eur_per_year"] == 0:
                st.warning(
                    "Excel-Kompatibilität: Im detaillierten OPEX-Modus wird die OPEX-Förderung in Rev. 8 "
                    "nicht von OPEX Total bzw. den LCOH abgezogen. Deshalb unterscheiden sich hier "
                    "'berechnet' und 'angewendet'."
                )

            if model_inputs.funding.spk_mode == "calculator":
                st.caption(
                    f"SPK-Rechner: Ø EUA {fmt_de(results['spk_average_eua_price_eur_per_tco2'], 2)} €/t CO₂ · "
                    f"Fallback {fmt_de(results['spk_fallback_factor'], 3)} · "
                    f"förderfähiger Verbrauch {fmt_int_de(results['spk_eligible_consumption_mwh_per_year'])} MWh/a"
                )

        # ----------------------------------------------------
        # Erlösübersicht
        # ----------------------------------------------------
        with st.expander("Erlösübersicht", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Stromverkauf gesamt", f"{fmt_int_de(results['power_sale_revenue_eur_per_year'])} €/a")
            c2.metric("THG-Quote", f"{fmt_int_de(results['thg_revenue_eur_per_year'])} €/a")
            c3.metric("Sauerstoff", f"{fmt_int_de(results['oxygen_revenue_eur_per_year'])} €/a")
            c4.metric("Abwärme", f"{fmt_int_de(results['waste_heat_revenue_eur_per_year'])} €/a")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Regelenergie", f"{fmt_int_de(results['balancing_energy_revenue_eur_per_year'])} €/a")
            c6.metric("Sonstige 1", f"{fmt_int_de(results['other_revenue_1_eur_per_year'])} €/a")
            c7.metric("Sonstige 2", f"{fmt_int_de(results['other_revenue_2_eur_per_year'])} €/a")
            c8.metric("Weitere Einnahmen Total", f"{fmt_int_de(results['total_other_revenues_eur_per_year'])} €/a")

            if model_inputs.power.spot_sale_enabled:
                sale_mode = "Spotmarkt" if model_inputs.power.power_sale_mode == "spot" else "PPA"
                st.caption(
                    f"Stromhandel: {sale_mode} · Verkaufte Menge "
                    f"{fmt_int_de(results['annual_power_sale_kwh'] / 1000.0)} MWh/a · "
                    f"Ø Verkaufspreis {fmt_de(results['average_power_sale_price_eur_per_mwh'], 2)} €/MWh"
                )

        # ----------------------------------------------------
        # Stromkosten & Privilegierungen
        # ----------------------------------------------------
        with st.expander("Stromkosten & Privilegierungen", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(
                "Ø Strombeschaffungspreis",
                f"{fmt_de(results['average_procurement_price_eur_per_mwh'], 2)} €/MWh",
            )
            c2.metric(
                "Strompreis Elektrolyseur",
                f"{fmt_de(results['electricity_price_ely_eur_per_mwh'], 2)} €/MWh",
            )
            c3.metric(
                "Strompreis Rest",
                f"{fmt_de(results['electricity_price_rest_eur_per_mwh'], 2)} €/MWh",
            )
            c4.metric(
                "Stromnebenkosten gesamt",
                f"{fmt_int_de(results['annual_power_addons_eur'])} €/a",
            )

            st.markdown("#### Strombezugsquellen")
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("PPA", f"{fmt_int_de(results['annual_ppa_kwh']/1000)} MWh/a")
            q2.metric(
                "§7",
                f"{fmt_int_de(results['annual_section7_kwh']/1000)} MWh/a",
                help=f"{results['section7_hours']} Stunden mit mehr als 1 kWh §7-Bezug",
            )
            q3.metric(
                "§13k",
                f"{fmt_int_de(results['annual_section13k_kwh']/1000)} MWh/a",
                help=f"{results['section13k_hours']} Stunden mit mehr als 1 kWh §13k-Bezug",
            )
            q4.metric("Spotmarkt", f"{fmt_int_de(results['annual_spot_kwh']/1000)} MWh/a")

            st.markdown("#### Aktive Stromnebenkosten [€/MWh]")
            addons_df = pd.DataFrame(
                {
                    "Kostenbestandteil": [
                        "Netzentgelt",
                        "Stromsteuer",
                        "Konzessionsabgabe",
                        "KWK-Aufschlag",
                        "StromNEV-§19",
                        "Offshore-Netzumlage",
                        "Leistungspreis",
                    ],
                    "Elektrolyseur [€/MWh]": [
                        results["ely_grid_fee_eur_per_mwh"],
                        results["ely_electricity_tax_eur_per_mwh"],
                        results["ely_concession_fee_eur_per_mwh"],
                        results["ely_kwk_levy_eur_per_mwh"],
                        results["ely_stromnev19_levy_eur_per_mwh"],
                        results["ely_offshore_levy_eur_per_mwh"],
                        results["ely_demand_charge_eur_per_mwh"],
                    ],
                    "Rest [€/MWh]": [
                        results["rest_grid_fee_eur_per_mwh"],
                        results["rest_electricity_tax_eur_per_mwh"],
                        results["rest_concession_fee_eur_per_mwh"],
                        results["rest_kwk_levy_eur_per_mwh"],
                        results["rest_stromnev19_levy_eur_per_mwh"],
                        results["rest_offshore_levy_eur_per_mwh"],
                        results["rest_demand_charge_eur_per_mwh"],
                    ],
                }
            )
            st.dataframe(addons_df, use_container_width=True, hide_index=True)

        # ----------------------------------------------------
        # Betriebskennzahlen
        # ----------------------------------------------------
        with st.expander("Betriebskennzahlen", expanded=False):
            c1, c2, c3, c4 = st.columns(4)

            c1.metric("H₂-Energieproduktion", f"{fmt_int_de(results['annual_h2_kwh'])} kWh/a")
            c2.metric("Ely-Stromverbrauch", f"{fmt_int_de(results['annual_ely_kwh'])} kWh/a")
            c3.metric("PPA-Strombezug", f"{fmt_int_de(results['annual_ppa_kwh'])} kWh/a")
            c4.metric("Spot-Strombezug", f"{fmt_int_de(results['annual_spot_kwh'])} kWh/a")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Volllaststunden (gezählt)", f"{fmt_int_de(results['full_load_hours_count'])} h")
            c6.metric("Ø Wirkungsgrad inkl. Degradation", fmt_pct_de(results["average_efficiency_h2_per_el"], 1))
            c7.metric("Wasserbedarf", f"{fmt_de(results['annual_water_demand_m3'], 0)} m³/a")
            c8.metric("Wasserkosten gesamt", f"{fmt_de(results['water_cost_per_m3'], 2)} €/m³")

        # ----------------------------------------------------
        # Aufbereitung, Nebenprodukte & Batterie
        # ----------------------------------------------------
        with st.expander("Aufbereitung, Nebenprodukte & Batterie", expanded=False):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Installierte Systemleistung", f"{fmt_de(results['installed_system_power_kw'], 1)} kW")
            c2.metric("H₂-Verdichterleistung", f"{fmt_de(results['h2_compressor_power_kw'], 1)} kW")
            c3.metric("O₂-Verdichterleistung", f"{fmt_de(results['oxygen_compressor_power_kw'], 1)} kW")
            c4.metric("Reststromverbrauch", f"{fmt_int_de(results['annual_rest_mwh'])} MWh/a")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("H₂-Verdichter", f"{fmt_de(results['h2_compressor_real_kwh_per_t'], 1)} kWh/t")
            c6.metric("H₂-Verdichterstrom", f"{fmt_int_de(results['annual_h2_compressor_mwh'])} MWh/a")
            c7.metric("O₂-Verdichter", f"{fmt_de(results['oxygen_compressor_real_kwh_per_t'], 1)} kWh/t")
            c8.metric("O₂-Verdichterstrom", f"{fmt_int_de(results['annual_oxygen_compressor_mwh'])} MWh/a")

            c9, c10, c11, c12 = st.columns(4)
            c9.metric("Sauerstoffproduktion", f"{fmt_int_de(results['annual_oxygen_t'])} t/a")
            c10.metric("Nutzbare Abwärme", f"{fmt_int_de(results['usable_waste_heat_mwh_per_year'])} MWh/a")
            c11.metric("Sauerstofferlös", f"{fmt_int_de(results['oxygen_revenue_eur_per_year'])} €/a")
            c12.metric("Abwärmeerlös", f"{fmt_int_de(results['waste_heat_revenue_eur_per_year'])} €/a")

            if model_inputs.capex.battery_enabled:
                st.markdown("#### Batteriesystem")
                b1, b2, b3, b4 = st.columns(4)
                b1.metric("Speicherkapazität", f"{fmt_int_de(results['battery_capacity_kwh'])} kWh")
                b2.metric("Laden", f"{fmt_int_de(results['annual_battery_charge_kwh']/1000)} MWh/a")
                b3.metric("Entladen", f"{fmt_int_de(results['annual_battery_discharge_kwh']/1000)} MWh/a")
                b4.metric("Ladezyklen (Excel-KPI)", f"{fmt_int_de(results['battery_cycles_per_year'])} /a")

                soc_df = pd.DataFrame({
                    "Stunde": np.arange(1, len(dispatch_df) + 1),
                    "SOC [MWh]": dispatch_df["battery_soc_kwh"].to_numpy() / 1000.0,
                })
                st.markdown("##### Ladezustand über das Jahr")
                soc_fig = go.Figure(
                    go.Scattergl(
                        x=soc_df["Stunde"],
                        y=soc_df["SOC [MWh]"],
                        mode="lines",
                        name="SOC",
                        hovertemplate="Stunde %{x:,.0f}<br>SOC %{y:,.1f} MWh<extra></extra>",
                    )
                )
                soc_fig.update_layout(
                    xaxis_title="Stunde des Jahres",
                    yaxis_title="Ladezustand [MWh]",
                    height=360,
                    margin=dict(l=20, r=20, t=20, b=45),
                    hovermode="x unified",
                    showlegend=False,
                )
                render_plotly(soc_fig)

        # ----------------------------------------------------
        # Visualisierung
        # ----------------------------------------------------
        with st.expander("Visualisierung", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### Dauerlinie der Auslastung")
                duration_df = utilization_duration_curve(dispatch_df)
                if duration_df.empty:
                    st.info("Für die Dauerlinie sind keine gültigen Auslastungsdaten vorhanden.")
                else:
                    duration_fig = go.Figure(
                        go.Scatter(
                            x=duration_df["Stundenrang"],
                            y=duration_df["Auslastung [%]"],
                            mode="lines",
                            name="Auslastung",
                            hovertemplate=(
                                "Stundenrang %{x:,.0f}<br>"
                                "Auslastung %{y:.1f} %<extra></extra>"
                            ),
                        )
                    )
                    duration_fig.update_layout(
                        xaxis_title="Stundenrang [h/a]",
                        yaxis_title="Auslastung [%]",
                        yaxis=dict(range=[0, 100]),
                        height=360,
                        margin=dict(l=20, r=20, t=20, b=20),
                        showlegend=False,
                    )
                    render_plotly(duration_fig)

            with col2:
                st.markdown("### Strommix (Jahressummen)")
                mix_df = pd.DataFrame(
                    {
                        "Kategorie": [
                            "PPA verfügbar",
                            "PPA genutzt",
                            "§7-Bezug",
                            "§13k-Bezug",
                            "Spotbezug",
                            "Spotverkauf",
                            "PPA-Verkauf",
                            "Abregelung",
                            "Systemverbrauch",
                            "Ely-Verbrauch",
                            "Peripherie",
                            "H₂-Verdichtung",
                            "O₂-Verdichtung",
                        ],
                        "MWh/a": [
                            dispatch_df["ppa_available_kwh"].sum() / 1000.0,
                            dispatch_df["ppa_used_kwh"].sum() / 1000.0,
                            dispatch_df["section7_purchase_kwh"].sum() / 1000.0,
                            dispatch_df["section13k_purchase_kwh"].sum() / 1000.0,
                            dispatch_df["spot_purchase_kwh"].sum() / 1000.0,
                            dispatch_df["spot_sale_kwh"].sum() / 1000.0,
                            dispatch_df["ppa_sale_kwh"].sum() / 1000.0,
                            dispatch_df["curtailed_kwh"].sum() / 1000.0,
                            dispatch_df["system_consumption_kwh"].sum() / 1000.0,
                            dispatch_df["ely_consumption_kwh"].sum() / 1000.0,
                            dispatch_df["peripheral_consumption_kwh"].sum() / 1000.0,
                            dispatch_df["h2_compressor_consumption_kwh"].sum() / 1000.0,
                            dispatch_df["oxygen_compressor_consumption_kwh"].sum() / 1000.0,
                        ],
                    }
                )
                mix_fig = go.Figure(
                    go.Bar(
                        x=mix_df["MWh/a"],
                        y=mix_df["Kategorie"],
                        orientation="h",
                        name="Energie",
                        hovertemplate="%{y}<br>%{x:,.0f} MWh/a<extra></extra>",
                    )
                )
                mix_fig.update_layout(
                    xaxis_title="Energie [MWh/a]",
                    yaxis_title="",
                    yaxis=dict(autorange="reversed"),
                    height=430,
                    margin=dict(l=20, r=20, t=20, b=45),
                    showlegend=False,
                )
                render_plotly(mix_fig)

            st.markdown("### Kostenstruktur (jährlich)")
            cost_breakdown_df = pd.DataFrame(
                {
                    "Kategorie": [
                        "Finanzierung (FK + EK)",
                        "Stackersatz",
                        "Wartung & Instandhaltung",
                        "Personal",
                        "Rückstellungen",
                        "Wasser",
                        "Individuelle OPEX",
                        "Baseload-PPA",
                        "PV-PPA",
                        "Wind-PPA",
                        "§7",
                        "§13k",
                        "Spotbezug",
                        "Stromnebenkosten Ely",
                        "Stromnebenkosten Rest",
                        "Strompreisförderung",
                        "Strompreiskompensation",
                        "Spotverkauf (Erlös)",
                        "PPA-Verkauf (Erlös)",
                        "THG-Quote (Erlös)",
                        "Sauerstoff (Erlös)",
                        "Abwärme (Erlös)",
                        "Regelenergie (Erlös)",
                        "Sonstige Einnahmen 1",
                        "Sonstige Einnahmen 2",
                    ],
                    "€/a": [
                        results["financing_eur_per_year"],
                        results["stack_replacement_eur_per_year"],
                        results["maintenance_eur_per_year"],
                        results["personnel_eur_per_year"],
                        results["reserves_total_eur_per_year"],
                        results["water_eur_per_year"],
                        results["individual_opex_eur_per_year"],
                        results["annual_baseload_cost_eur"],
                        results["annual_pv_ppa_cost_eur"],
                        results["annual_wind_ppa_cost_eur"],
                        results["annual_section7_cost_eur"],
                        results["annual_section13k_cost_eur"],
                        results["annual_spot_purchase_cost_eur"],
                        results["ely_power_addons_eur_per_year"],
                        results["rest_power_addons_eur_per_year"],
                        -results["electricity_subsidy_eur_per_year"],
                        -results["spk_revenue_eur_per_year"],
                        -results["annual_spot_sale_revenue_eur"],
                        -results["annual_ppa_sale_revenue_eur"],
                        -results["thg_revenue_eur_per_year"],
                        -results["oxygen_revenue_eur_per_year"],
                        -results["waste_heat_revenue_eur_per_year"],
                        -results["balancing_energy_revenue_eur_per_year"],
                        -results["other_revenue_1_eur_per_year"],
                        -results["other_revenue_2_eur_per_year"],
                    ],
                }
            )
            cost_breakdown_fig = go.Figure(
                go.Bar(
                    x=cost_breakdown_df["€/a"],
                    y=cost_breakdown_df["Kategorie"],
                    orientation="h",
                    name="Kosten / Erlöse",
                    hovertemplate="%{y}<br>%{x:,.0f} €/a<extra></extra>",
                )
            )
            cost_breakdown_fig.add_vline(x=0.0, line_width=1)
            cost_breakdown_fig.update_layout(
                xaxis_title="Jährlicher Beitrag [€/a]",
                yaxis_title="",
                yaxis=dict(autorange="reversed"),
                height=720,
                margin=dict(l=20, r=20, t=20, b=45),
                showlegend=False,
            )
            render_plotly(cost_breakdown_fig)

        # ----------------------------------------------------
        # Ergebnisübersicht als Tabelle
        # ----------------------------------------------------
        with st.expander("Ergebnisübersicht als Tabelle", expanded=False):
            summary_df = pd.DataFrame(
                [
                    ["LCOH", f"{fmt_de(results['lcoh_eur_per_kg'], 2)} €/kg"],
                    ["LCOH", f"{fmt_de(results['lcoh_ct_per_kwh'], 2)} ct/kWh"],
                    ["Wasserstoffproduktion", f"{fmt_int_de(results['annual_h2_kg'])} kg/a"],
                    ["Ely-Stromverbrauch", f"{fmt_int_de(results['annual_ely_mwh'])} MWh/a"],
                    ["Durchschnittliche Auslastung", fmt_pct_de(results["avg_utilization"], 1)],
                    ["Betriebsstunden", f"{fmt_int_de(results['operating_hours'])} h"],
                    ["Äquivalente Volllaststunden", f"{fmt_int_de(results['equivalent_full_load_hours'])} h/a"],
                    ["Finanzierung (FK + EK)", f"{fmt_int_de(results['financing_eur_per_year'])} €/a"],
                    ["OPEX gesamt", f"{fmt_int_de(results['total_opex_eur_per_year'])} €/a"],
                    ["CAPEX-Förderung gesamt", f"{fmt_int_de(results['capex_subsidy_total_eur'])} €"],
                    ["Strompreisförderung", f"{fmt_int_de(results['electricity_subsidy_eur_per_year'])} €/a"],
                    ["Strompreiskompensation", f"{fmt_int_de(results['spk_revenue_eur_per_year'])} €/a"],
                    ["Stromverkauf", f"{fmt_int_de(results['power_sale_revenue_eur_per_year'])} €/a"],
                    ["Regelenergie", f"{fmt_int_de(results['balancing_energy_revenue_eur_per_year'])} €/a"],
                    ["Sonstige Erlöse", f"{fmt_int_de(results['other_revenue_eur_per_year'])} €/a"],
                    ["Weitere Einnahmen Total", f"{fmt_int_de(results['total_other_revenues_eur_per_year'])} €/a"],
                    ["Gesamtkosten jährlich", f"{fmt_int_de(results['annual_costs_eur_per_year'])} €/a"],
                ],
                columns=["Kennzahl", "Wert"],
            )
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # ----------------------------------------------------
        # Export
        # ----------------------------------------------------
        with st.expander("Export", expanded=False):
            export_json = json.dumps(
                {
                    "system": asdict(model_inputs.system),
                    "capex": asdict(model_inputs.capex),
                    "opex": asdict(model_inputs.opex),
                    "power": asdict(model_inputs.power),
                    "revenue": asdict(model_inputs.revenue),
                    "funding": asdict(model_inputs.funding),
                    "results": results,
                },
                indent=2,
            ).encode("utf-8")

            st.download_button(
                "Ergebnisse als JSON herunterladen",
                export_json,
                "lcoh_results.json",
                "application/json",
            )

            export_csv = pd.DataFrame([results]).to_csv(index=False, sep=";", decimal=",").encode("utf-8")
            st.download_button(
                "KPIs als CSV herunterladen",
                export_csv,
                "lcoh_kpis.csv",
                "text/csv",
            )

# ============================================================
# Tab 7: Sensitivität
# ============================================================

with tabs[6]:
    st.subheader("Sensitivitätsanalyse")
    st.caption(
        "Die Analyse folgt der Methodik des Excel-Blatts ‚7. Grafiken‘. "
        "Dabei wird jeweils eine Größe variiert, während die übrigen Größen auf dem Basisfall bleiben."
    )

    bundle = st.session_state.result_bundle
    if bundle is None:
        st.info("Bitte zuerst die Berechnung über die Seitenleiste starten.")
    else:
        results = bundle["results"]
        model_inputs = bundle["inputs"]

        c1, c2, c3 = st.columns([1.0, 1.0, 1.4])
        with c1:
            sensitivity_range_percent = st.slider(
                "Variationsbereich ± [%]",
                min_value=5,
                max_value=80,
                value=int(st.session_state.sensitivity_range_percent),
                step=5,
                key=SENSITIVITY_RANGE_WIDGET_KEY,
                help=(
                    "Standard: ±30 % wie im Excel-Sensitivitätsblatt. "
                    "Der gewählte Wert wird unmittelbar für Tornado-Diagramm, Tabelle und Detailkurve verwendet."
                ),
            )
            st.session_state.sensitivity_range_percent = sensitivity_range_percent
        with c2:
            sensitivity_points = st.slider(
                "Punkte der Detailkurve",
                min_value=5,
                max_value=31,
                value=int(st.session_state.sensitivity_points),
                step=2,
                key=SENSITIVITY_POINTS_WIDGET_KEY,
                help=(
                    "Standard: 13 Punkte. Bei ±30 % entstehen dadurch 5-%-Schritte von −30 % bis +30 % "
                    "einschließlich des Basisfalls bei 0 %."
                ),
            )
            st.session_state.sensitivity_points = sensitivity_points
        with c3:
            label_to_key = {p.label: p.key for p in EXCEL_SENSITIVITY_PARAMETERS}
            key_to_label = {p.key: p.label for p in EXCEL_SENSITIVITY_PARAMETERS}
            selected_label = st.selectbox(
                "Parameter für Detailkurve",
                options=list(label_to_key),
                index=list(label_to_key).index(
                    key_to_label.get(st.session_state.sensitivity_parameter, "Strompreis")
                ),
            )
            st.session_state.sensitivity_parameter = label_to_key[selected_label]

        relative_range = sensitivity_range_percent / 100.0
        tornado_df = compute_tornado(model_inputs, results, relative_range)

        st.markdown("### Einfluss auf den LCOH")
        tornado_fig = go.Figure()
        tornado_fig.add_trace(
            go.Bar(
                name=f"−{sensitivity_range_percent} %",
                y=tornado_df["Parameter"],
                x=tornado_df["Delta_minus"],
                orientation="h",
                customdata=tornado_df["LCOH_minus"],
                hovertemplate="%{y}<br>Δ LCOH: %{x:.3f} €/kg<br>LCOH: %{customdata:.3f} €/kg<extra></extra>",
            )
        )
        tornado_fig.add_trace(
            go.Bar(
                name=f"+{sensitivity_range_percent} %",
                y=tornado_df["Parameter"],
                x=tornado_df["Delta_plus"],
                orientation="h",
                customdata=tornado_df["LCOH_plus"],
                hovertemplate="%{y}<br>Δ LCOH: %{x:.3f} €/kg<br>LCOH: %{customdata:.3f} €/kg<extra></extra>",
            )
        )
        tornado_fig.add_vline(x=0.0, line_width=1)
        tornado_fig.update_layout(
            barmode="group",
            xaxis_title="Änderung des LCOH gegenüber Basis [€/kg]",
            yaxis_title="",
            height=520,
            margin=dict(l=20, r=20, t=20, b=40),
            legend_title="Szenario",
        )
        render_plotly(tornado_fig)

        display_tornado = tornado_df.copy().sort_values("Spannweite", ascending=False)
        display_tornado[f"LCOH −{sensitivity_range_percent} % [€/kg]"] = display_tornado["LCOH_minus"]
        display_tornado["Basis [€/kg]"] = display_tornado["LCOH_basis"]
        display_tornado[f"LCOH +{sensitivity_range_percent} % [€/kg]"] = display_tornado["LCOH_plus"]
        st.dataframe(
            display_tornado[[
                "Parameter",
                f"LCOH −{sensitivity_range_percent} % [€/kg]",
                "Basis [€/kg]",
                f"LCOH +{sensitivity_range_percent} % [€/kg]",
            ]],
            use_container_width=True,
            hide_index=True,
            column_config={
                f"LCOH −{sensitivity_range_percent} % [€/kg]": st.column_config.NumberColumn(format="%.3f"),
                "Basis [€/kg]": st.column_config.NumberColumn(format="%.3f"),
                f"LCOH +{sensitivity_range_percent} % [€/kg]": st.column_config.NumberColumn(format="%.3f"),
            },
        )

        parameter_key = st.session_state.sensitivity_parameter
        parameter = PARAMETER_BY_KEY[parameter_key]
        curve_df = compute_sensitivity_curve(
            model_inputs,
            results,
            parameter_key,
            relative_range=relative_range,
            points=sensitivity_points,
        )

        st.markdown(f"### Detailkurve: {parameter.label}")
        st.caption(parameter.description)
        curve_fig = go.Figure(
            go.Scatter(
                x=curve_df["Änderung [%]"],
                y=curve_df["LCOH [€/kg]"],
                mode="lines+markers",
                hovertemplate="Änderung: %{x:.1f} %<br>LCOH: %{y:.3f} €/kg<extra></extra>",
            )
        )
        curve_fig.add_hline(
            y=results["lcoh_eur_per_kg"],
            line_dash="dash",
            annotation_text="Basis",
        )
        curve_fig.add_vline(x=0.0, line_dash="dash")
        curve_fig.update_layout(
            xaxis_title="Änderung gegenüber Basis [%]",
            yaxis_title="LCOH [€/kg H₂]",
            height=460,
            margin=dict(l=30, r=20, t=20, b=50),
        )
        render_plotly(curve_fig)

        with st.expander("Methodik & Export", expanded=False):
            st.markdown(
                "**Excel-Kompatibilität:** CAPEX- und OPEX-Sensitivitäten skalieren wie in Rev. 8 "
                "die jeweilige Kostenkomponente und nicht automatisch alle davon abhängigen Eingaben. "
                "Die Projektlaufzeit wirkt in dieser Analyse auf Finanzierung und Stacktausch; "
                "Volllaststunden skalieren Produktion und energieabhängige Größen proportional. "
                "So sind die Ergebnisse mit dem Sensitivitätsblatt des Excel-Tools vergleichbar."
            )
            sensitivity_csv = curve_df.to_csv(index=False, sep=";", decimal=",").encode("utf-8")
            st.download_button(
                "Detailkurve als CSV herunterladen",
                sensitivity_csv,
                f"lcoh_sensitivitaet_{parameter_key}.csv",
                "text/csv",
            )
