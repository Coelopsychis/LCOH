from __future__ import annotations

from dataclasses import asdict
import json

import numpy as np
import pandas as pd
import streamlit as st

from widgets import percent_slider

from core.models import (
    SystemInputs,
    CapexInputs,
    OpexInputs,
    PowerInputs,
    ModelInputs,
)
from core.timeseries import make_demo_timeseries, validate_timeseries
from core.simulation import build_dispatch
from core.finance import compute_lcoh

import locale

locale.setlocale(locale.LC_ALL, "de_DE.UTF-8")

def de_number(value, decimals=2):
    if value is None:
        return "-"
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.set_page_config(page_title="Berechnungstool LCOH", layout="wide")


# ============================================================
# Session-State Initialisierung
# ============================================================

def init_ui_state() -> None:
    if "ui_initialized" in st.session_state:
        return

    # Defaults aus Dataclasses
    s = SystemInputs()
    c = CapexInputs()
    o = OpexInputs()
    p = PowerInputs()

    # System
    st.session_state.commissioning_year = s.commissioning_year
    st.session_state.project_lifetime_years = s.project_lifetime_years
    st.session_state.electrolyzer_power_kw = s.electrolyzer_power_kw
    st.session_state.system_power_kw = s.system_power_kw
    st.session_state.min_load_fraction = s.min_load_fraction * 100
    st.session_state.avg_efficiency_h2_per_el = s.avg_efficiency_h2_per_el * 100
    st.session_state.stack_lifetime_years = s.stack_lifetime_years
    st.session_state.degradation_per_year = s.degradation_per_year

    # CAPEX
    st.session_state.epc_eur_per_kw = c.epc_eur_per_kw
    st.session_state.bop_eur_per_kw = c.bop_eur_per_kw
    st.session_state.hochbau_eur_per_kw = c.hochbau_eur_per_kw
    st.session_state.tiefbau_eur_per_kw = c.tiefbau_eur_per_kw
    st.session_state.individual_specific_eur_per_kw = c.individual_specific_eur_per_kw
    st.session_state.individual_fixed_eur = c.individual_fixed_eur

    st.session_state.waste_heat_enabled = c.waste_heat_enabled
    st.session_state.waste_heat_system_eur_per_kw = c.waste_heat_system_eur_per_kw

    st.session_state.oxygen_enabled = c.oxygen_enabled
    st.session_state.oxygen_system_eur_per_kw = c.oxygen_system_eur_per_kw

    st.session_state.compression_enabled = c.compression_enabled
    st.session_state.compressor_system_eur_per_kw = c.compressor_system_eur_per_kw

    st.session_state.battery_enabled = c.battery_enabled
    st.session_state.battery_capacity_factor_kwh_per_kw = c.battery_capacity_factor_kwh_per_kw
    st.session_state.battery_power_kw = c.battery_power_kw
    st.session_state.battery_invest_eur_per_kwh = c.battery_invest_eur_per_kwh

    st.session_state.stack_replacement_specific_eur_per_kw = c.stack_replacement_specific_eur_per_kw
    st.session_state.discount_rate = c.discount_rate
    st.session_state.debt_interest_rate = c.debt_interest_rate
    st.session_state.equity_share = c.equity_share

    # OPEX
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
    st.session_state.ppa_pv_enabled = p.ppa_pv_enabled
    st.session_state.ppa_pv_capacity_kw = p.ppa_pv_capacity_kw
    st.session_state.ppa_wind_enabled = p.ppa_wind_enabled
    st.session_state.ppa_wind_capacity_kw = p.ppa_wind_capacity_kw
    st.session_state.spot_enabled = p.spot_enabled
    st.session_state.spot_price_limit_eur_per_mwh = p.spot_price_limit_eur_per_mwh

    # Weitere Zustände
    st.session_state.timeseries_df = make_demo_timeseries()
    st.session_state.result_bundle = None
    st.session_state.ui_initialized = True


def build_model_inputs_from_ui() -> ModelInputs:
    system = SystemInputs(
        commissioning_year=int(st.session_state.commissioning_year),
        project_lifetime_years=int(st.session_state.project_lifetime_years),
        electrolyzer_power_kw=float(st.session_state.electrolyzer_power_kw),
        system_power_kw=float(st.session_state.system_power_kw),
        min_load_fraction=float(st.session_state.min_load_fraction) / 100,
        avg_efficiency_h2_per_el=float(st.session_state.avg_efficiency_h2_per_el) / 100,
        stack_lifetime_years=int(st.session_state.stack_lifetime_years),
        degradation_per_year=float(st.session_state.degradation_per_year),
    )

    capex = CapexInputs(
        epc_eur_per_kw=float(st.session_state.epc_eur_per_kw),
        bop_eur_per_kw=float(st.session_state.bop_eur_per_kw),
        hochbau_eur_per_kw=float(st.session_state.hochbau_eur_per_kw),
        tiefbau_eur_per_kw=float(st.session_state.tiefbau_eur_per_kw),
        individual_specific_eur_per_kw=float(st.session_state.individual_specific_eur_per_kw),
        individual_fixed_eur=float(st.session_state.individual_fixed_eur),

        waste_heat_enabled=bool(st.session_state.waste_heat_enabled),
        waste_heat_system_eur_per_kw=float(st.session_state.waste_heat_system_eur_per_kw),

        oxygen_enabled=bool(st.session_state.oxygen_enabled),
        oxygen_system_eur_per_kw=float(st.session_state.oxygen_system_eur_per_kw),

        compression_enabled=bool(st.session_state.compression_enabled),
        compressor_system_eur_per_kw=float(st.session_state.compressor_system_eur_per_kw),

        battery_enabled=bool(st.session_state.battery_enabled),
        battery_capacity_factor_kwh_per_kw=float(st.session_state.battery_capacity_factor_kwh_per_kw),
        battery_power_kw=float(st.session_state.battery_power_kw),
        battery_invest_eur_per_kwh=float(st.session_state.battery_invest_eur_per_kwh),

        stack_replacement_specific_eur_per_kw=float(st.session_state.stack_replacement_specific_eur_per_kw),
        discount_rate=float(st.session_state.discount_rate),
        debt_interest_rate=float(st.session_state.debt_interest_rate),
        equity_share=float(st.session_state.equity_share),
    )

    opex = OpexInputs(
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
        ppa_pv_enabled=bool(st.session_state.ppa_pv_enabled),
        ppa_pv_capacity_kw=float(st.session_state.ppa_pv_capacity_kw),
        ppa_wind_enabled=bool(st.session_state.ppa_wind_enabled),
        ppa_wind_capacity_kw=float(st.session_state.ppa_wind_capacity_kw),
        spot_enabled=bool(st.session_state.spot_enabled),
        spot_price_limit_eur_per_mwh=float(st.session_state.spot_price_limit_eur_per_mwh),
    )

    return ModelInputs(system=system, capex=capex, opex=opex, power=power)


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
    st.sidebar.metric("LCOH [€/kg]", de_number(r["lcoh_eur_per_kg"], 2))
    st.sidebar.metric("LCOH [ct/kWh]", de_number(r["lcoh_ct_per_kwh"], 2))
    st.sidebar.metric("H₂-Produktion [kg/a]", de_number(r["annual_h2_kg"], 0))
    st.sidebar.metric("Ely-Stromverbrauch [MWh/a]", de_number(r["annual_ely_mwh"], 0))


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
        "5) Ergebnisse",
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
            st.number_input(
                "Systemleistung [kW]",
                min_value=1.0,
                max_value=1_000_000.0,
                step=100.0,
                key="system_power_kw",
            )

        with c3:
            percent_slider(
                "Mindestlast",
                key="min_load_fraction",
            )

    with st.expander("Wirkungsgrad & Degradation", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            percent_slider(
                "Mittlere Effizienz η",
                key="avg_efficiency_h2_per_el",
            )

        with c2:
            st.number_input(
                "Stack-Lebensdauer [a]",
                min_value=1,
                max_value=30,
                step=1,
                key="stack_lifetime_years",
            )

        with c3:
            percent_slider(
                "Degradation pro Jahr",
                key="degradation_per_year",
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

        with c2:
            st.number_input(
                "Peripherie / Balance of Plant [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="bop_eur_per_kw",
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
        c1, c2 = st.columns(2)
        with c1:
            st.checkbox("Abwärme nutzbar", key="waste_heat_enabled")
        with c2:
            st.number_input(
                "Abwärmesystemkosten [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="waste_heat_system_eur_per_kw",
                disabled=not st.session_state.waste_heat_enabled,
            )

    with st.expander("Sauerstoff", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.checkbox("Sauerstoff nutzbar", key="oxygen_enabled")
        with c2:
            st.number_input(
                "Sauerstoffsystemkosten [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="oxygen_system_eur_per_kw",
                disabled=not st.session_state.oxygen_enabled,
            )

    with st.expander("H₂-Aufbereitung", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.checkbox("H₂ wird verdichtet", key="compression_enabled")
        with c2:
            st.number_input(
                "Verdichtersystemkosten [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="compressor_system_eur_per_kw",
                disabled=not st.session_state.compression_enabled,
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
                "Installierte Leistung [kW]",
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

    with st.expander("Ersatzinvestitionen & Finanzierung", expanded=True):
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.number_input(
                "Stackersatz [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="stack_replacement_specific_eur_per_kw",
            )

        with c2:
            st.slider(
                "Kalkulationszins [-]",
                min_value=0.0,
                max_value=0.30,
                step=0.005,
                key="discount_rate",
            )

        with c3:
            st.slider(
                "Fremdkapitalzins [-]",
                min_value=0.0,
                max_value=0.30,
                step=0.005,
                key="debt_interest_rate",
            )

        with c4:
            st.slider(
                "Eigenkapitalquote [-]",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                key="equity_share",
            )

# ============================================================
# Tab 3: OPEX
# ============================================================

with tabs[2]:
    st.subheader("OPEX")

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


# ============================================================
# Tab 4: Strom & Zeitreihen
# ============================================================

with tabs[3]:
    st.subheader("Stromversorgung & Zeitreihen")

    with st.expander("Beschaffungsoptionen", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.checkbox("Baseload aktiv", key="baseload_enabled")
            st.number_input(
                "Baseload [kW]",
                min_value=0.0,
                max_value=1_000_000.0,
                step=100.0,
                key="baseload_kw",
            )

        with c2:
            st.checkbox("PV-PPA aktiv", key="ppa_pv_enabled")
            st.number_input(
                "PV-PPA Leistung [kW]",
                min_value=0.0,
                max_value=1_000_000.0,
                step=100.0,
                key="ppa_pv_capacity_kw",
            )
            st.checkbox("Wind-PPA aktiv", key="ppa_wind_enabled")
            st.number_input(
                "Wind-PPA Leistung [kW]",
                min_value=0.0,
                max_value=1_000_000.0,
                step=100.0,
                key="ppa_wind_capacity_kw",
            )

        with c3:
            st.checkbox("Spotmarkt aktiv", key="spot_enabled")
            st.number_input(
                "Spot-Preisgrenze [€/MWh]",
                min_value=-200.0,
                max_value=1000.0,
                step=1.0,
                key="spot_price_limit_eur_per_mwh",
            )

    with st.expander("Zeitreihenquelle", expanded=True):
        c1, c2 = st.columns([1, 2])

        with c1:
            if st.button("Demo-Zeitreihen erzeugen"):
                st.session_state.timeseries_df = make_demo_timeseries()
                st.success("Demo-Zeitreihen geladen.")

        with c2:
            uploaded = st.file_uploader(
                "CSV mit Spalten pv_kwh_per_kw, wind_kwh_per_kw, day_ahead_eur_per_mwh",
                type=["csv"],
            )
            if uploaded is not None:
                try:
                    df = pd.read_csv(uploaded)
                    validate_timeseries(df)
                    st.session_state.timeseries_df = df.copy()
                    st.success("CSV-Zeitreihe übernommen.")
                except Exception as e:
                    st.error(f"CSV konnte nicht eingelesen werden: {e}")

    with st.expander("Vorschau der ersten 24 Stunden", expanded=False):
        df = st.session_state.timeseries_df.applymap(lambda x: de_number(x, 2) if isinstance(x, (int, float)) else x)
        st.dataframe(df.head(24), use_container_width=True, height=260)


# ============================================================
# Tab 5: Ergebnisse
# ============================================================

with tabs[4]:
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
        # Hauptkennzahlen
        # ----------------------------------------------------
        with st.expander("Hauptkennzahlen", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("LCOH", f"{fmt_de(results['lcoh_eur_per_kg'], 2)} €/kg")
            c2.metric("LCOH", f"{fmt_de(results['lcoh_ct_per_kwh'], 2)} ct/kWh")
            c3.metric("Wasserstoffproduktion", f"{fmt_int_de(results['annual_h2_kg'])} kg/a")
            c4.metric("Ely-Stromverbrauch", f"{fmt_int_de(results['annual_ely_mwh'])} MWh/a")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Durchschnittliche Auslastung", fmt_pct_de(results["avg_utilization"], 1))
            c6.metric("Betriebsstunden", f"{fmt_int_de(results['operating_hours'])} h")
            c7.metric("Äquivalente Volllaststunden", f"{fmt_int_de(results['equivalent_full_load_hours'])} h/a")
            c8.metric("Spotmarktkosten", f"{fmt_int_de(results['annual_spot_cost_eur'])} €/a")

        # ----------------------------------------------------
        # Kostenstruktur
        # ----------------------------------------------------
        with st.expander("Kostenstruktur", expanded=True):
            c1, c2, c3 = st.columns(3)

            with c1:
                st.markdown("**CAPEX**")
                st.metric("CAPEX gesamt", f"{fmt_int_de(results['total_capex_eur'])} €")
                st.metric("CAPEX annuisiert", f"{fmt_int_de(results['annualized_capex_eur_per_year'])} €/a")
                st.metric("Stackersatz", f"{fmt_int_de(results['stack_replacement_eur_per_year'])} €/a")

            with c2:
                st.markdown("**OPEX**")
                st.metric("Wartung & Instandhaltung", f"{fmt_int_de(results['maintenance_eur_per_year'])} €/a")
                st.metric("Personalkosten", f"{fmt_int_de(results['personnel_eur_per_year'])} €/a")
                st.metric("Rückstellungen", f"{fmt_int_de(results['reserves_total_eur_per_year'])} €/a")
                st.metric("Wasserkosten", f"{fmt_int_de(results['water_eur_per_year'])} €/a")
                st.metric("Individuelle OPEX", f"{fmt_int_de(results['individual_opex_eur_per_year'])} €/a")

            with c3:
                st.markdown("**Gesamtkosten**")
                st.metric("OPEX gesamt", f"{fmt_int_de(results['total_opex_eur_per_year'])} €/a")
                st.metric("Spotmarktkosten", f"{fmt_int_de(results['annual_spot_cost_eur'])} €/a")
                st.metric("Gesamtkosten jährlich", f"{fmt_int_de(results['annual_costs_eur_per_year'])} €/a")

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
            c6.metric("Teillaststunden", f"{fmt_int_de(results['partial_load_hours'])} h")
            c7.metric("Wasserbedarf", f"{fmt_de(results['annual_water_demand_m3'], 0)} m³/a")
            c8.metric("Wasserkosten gesamt", f"{fmt_de(results['water_cost_per_m3'], 2)} €/m³")

        # ----------------------------------------------------
        # Visualisierung
        # ----------------------------------------------------
        with st.expander("Visualisierung", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("### Dauerlinie der Auslastung")
                duration_curve = np.sort(dispatch_df["utilization"].to_numpy())[::-1] * 100.0
                duration_df = pd.DataFrame(
                    {
                        "Stundenrang": np.arange(1, len(duration_curve) + 1),
                        "Auslastung [%]": duration_curve,
                    }
                )
                st.line_chart(duration_df.set_index("Stundenrang"))

            with col2:
                st.markdown("### Strommix (Jahressummen)")
                mix_df = pd.DataFrame(
                    {
                        "Kategorie": ["PPA", "Spot", "Systemverbrauch", "Ely-Verbrauch"],
                        "MWh/a": [
                            dispatch_df["ppa_supply_kwh"].sum() / 1000.0,
                            dispatch_df["spot_supply_kwh"].sum() / 1000.0,
                            dispatch_df["system_consumption_kwh"].sum() / 1000.0,
                            dispatch_df["ely_consumption_kwh"].sum() / 1000.0,
                        ],
                    }
                ).set_index("Kategorie")
                st.bar_chart(mix_df)

            st.markdown("### Kostenstruktur (jährlich)")
            cost_breakdown_df = pd.DataFrame(
                {
                    "Kategorie": [
                        "CAPEX annuisiert",
                        "Stackersatz",
                        "Wartung & Instandhaltung",
                        "Personal",
                        "Rückstellungen",
                        "Wasser",
                        "Individuelle OPEX",
                        "Spotmarkt",
                    ],
                    "€/a": [
                        results["annualized_capex_eur_per_year"],
                        results["stack_replacement_eur_per_year"],
                        results["maintenance_eur_per_year"],
                        results["personnel_eur_per_year"],
                        results["reserves_total_eur_per_year"],
                        results["water_eur_per_year"],
                        results["individual_opex_eur_per_year"],
                        results["annual_spot_cost_eur"],
                    ],
                }
            ).set_index("Kategorie")
            st.bar_chart(cost_breakdown_df)

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
                    ["CAPEX annuisiert", f"{fmt_int_de(results['annualized_capex_eur_per_year'])} €/a"],
                    ["OPEX gesamt", f"{fmt_int_de(results['total_opex_eur_per_year'])} €/a"],
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