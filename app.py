from __future__ import annotations

from dataclasses import asdict
import json

import numpy as np
import pandas as pd
import streamlit as st

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


st.set_page_config(page_title="Electrolyzer LCOH Demo", layout="wide")


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
    st.session_state.min_load_fraction = s.min_load_fraction
    st.session_state.avg_efficiency_h2_per_el = s.avg_efficiency_h2_per_el
    st.session_state.kwh_h2_per_kg = s.kwh_h2_per_kg
    st.session_state.stack_lifetime_years = s.stack_lifetime_years
    st.session_state.degradation_per_year = s.degradation_per_year

    # CAPEX
    st.session_state.electrolyzer_specific_eur_per_kw = c.electrolyzer_specific_eur_per_kw
    st.session_state.bop_specific_eur_per_kw = c.bop_specific_eur_per_kw
    st.session_state.infrastructure_specific_eur_per_kw = c.infrastructure_specific_eur_per_kw
    st.session_state.development_share = c.development_share
    st.session_state.stack_replacement_specific_eur_per_kw = c.stack_replacement_specific_eur_per_kw
    st.session_state.discount_rate = c.discount_rate
    st.session_state.debt_interest_rate = c.debt_interest_rate
    st.session_state.equity_share = c.equity_share

    # OPEX
    st.session_state.maintenance_share_of_capex = o.maintenance_share_of_capex
    st.session_state.personnel_eur_per_year = o.personnel_eur_per_year
    st.session_state.other_fixed_opex_eur_per_year = o.other_fixed_opex_eur_per_year
    st.session_state.water_eur_per_kg_h2 = o.water_eur_per_kg_h2

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
        min_load_fraction=float(st.session_state.min_load_fraction),
        avg_efficiency_h2_per_el=float(st.session_state.avg_efficiency_h2_per_el),
        kwh_h2_per_kg=float(st.session_state.kwh_h2_per_kg),
        stack_lifetime_years=int(st.session_state.stack_lifetime_years),
        degradation_per_year=float(st.session_state.degradation_per_year),
    )

    capex = CapexInputs(
        electrolyzer_specific_eur_per_kw=float(st.session_state.electrolyzer_specific_eur_per_kw),
        bop_specific_eur_per_kw=float(st.session_state.bop_specific_eur_per_kw),
        infrastructure_specific_eur_per_kw=float(st.session_state.infrastructure_specific_eur_per_kw),
        development_share=float(st.session_state.development_share),
        stack_replacement_specific_eur_per_kw=float(st.session_state.stack_replacement_specific_eur_per_kw),
        discount_rate=float(st.session_state.discount_rate),
        debt_interest_rate=float(st.session_state.debt_interest_rate),
        equity_share=float(st.session_state.equity_share),
    )

    opex = OpexInputs(
        maintenance_share_of_capex=float(st.session_state.maintenance_share_of_capex),
        personnel_eur_per_year=float(st.session_state.personnel_eur_per_year),
        other_fixed_opex_eur_per_year=float(st.session_state.other_fixed_opex_eur_per_year),
        water_eur_per_kg_h2=float(st.session_state.water_eur_per_kg_h2),
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

st.sidebar.title("Berechnung")
st.sidebar.caption("Modelllauf und Hauptkennzahlen")

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
        st.sidebar.success("Berechnung erfolgreich")
    except Exception as e:
        st.sidebar.error(f"Fehler: {e}")

st.sidebar.divider()

if st.session_state.result_bundle is None:
    st.sidebar.info("Noch keine Ergebnisse verfügbar.")
else:
    r = st.session_state.result_bundle["results"]
    st.sidebar.metric("LCOH [€/kg]", f"{r['lcoh_eur_per_kg']:.2f}")
    st.sidebar.metric("LCOH [ct/kWh]", f"{r['lcoh_ct_per_kwh']:.2f}")
    st.sidebar.metric("H₂-Produktion [kg/a]", f"{r['annual_h2_kg']:,.0f}")
    st.sidebar.metric("Ely-Strom [MWh/a]", f"{r['annual_ely_mwh']:,.0f}")


# ============================================================
# Hauptlayout
# ============================================================

st.title("Electrolyzer LCOH Demo")
st.caption(
    "Basisversion eines techno-ökonomischen Rechners für Wasserstoffelektrolyseure "
    "mit stündlicher Simulation."
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

    with st.expander("Projekt & Leistung", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.number_input(
                "Inbetriebnahmejahr",
                min_value=2000,
                max_value=2100,
                step=1,
                key="commissioning_year",
            )
            st.number_input(
                "Projektlaufzeit [a]",
                min_value=1,
                max_value=50,
                step=1,
                key="project_lifetime_years",
            )

        with c2:
            st.number_input(
                "Elektrolyseurleistung [kW]",
                min_value=1.0,
                max_value=1_000_000.0,
                step=100.0,
                key="electrolyzer_power_kw",
            )
            st.number_input(
                "Systemleistung [kW]",
                min_value=1.0,
                max_value=1_000_000.0,
                step=100.0,
                key="system_power_kw",
            )

        with c3:
            st.slider(
                "Mindestlast [-]",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                key="min_load_fraction",
            )

    with st.expander("Wirkungsgrad & Wasserstoff", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.slider(
                "Mittlere Effizienz η [-]",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                key="avg_efficiency_h2_per_el",
            )

        with c2:
            st.number_input(
                "Energieinhalt H₂ [kWh/kg]",
                min_value=1.0,
                max_value=100.0,
                step=0.1,
                key="kwh_h2_per_kg",
            )

        with c3:
            st.number_input(
                "Stack-Lebensdauer [a]",
                min_value=1,
                max_value=30,
                step=1,
                key="stack_lifetime_years",
            )
            st.number_input(
                "Degradation pro Jahr [-]",
                min_value=0.0,
                max_value=1.0,
                step=0.001,
                format="%.3f",
                key="degradation_per_year",
            )


# ============================================================
# Tab 2: CAPEX
# ============================================================

with tabs[1]:
    st.subheader("CAPEX & Finanzierung")

    with st.expander("Direkte Investitionskosten", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.number_input(
                "Elektrolyseur-CAPEX [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="electrolyzer_specific_eur_per_kw",
            )

        with c2:
            st.number_input(
                "BoP-CAPEX [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="bop_specific_eur_per_kw",
            )

        with c3:
            st.number_input(
                "Infrastruktur-CAPEX [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="infrastructure_specific_eur_per_kw",
            )

    with st.expander("Projektentwicklung & Ersatzinvestitionen", expanded=True):
        c1, c2 = st.columns(2)

        with c1:
            st.slider(
                "Projektentwicklungskosten [-]",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                key="development_share",
            )

        with c2:
            st.number_input(
                "Stackersatz [€/kW]",
                min_value=0.0,
                max_value=100_000.0,
                step=10.0,
                key="stack_replacement_specific_eur_per_kw",
            )

    with st.expander("Finanzierung", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.slider(
                "Kalkulationszins [-]",
                min_value=0.0,
                max_value=0.30,
                step=0.005,
                key="discount_rate",
            )

        with c2:
            st.slider(
                "Fremdkapitalzins [-]",
                min_value=0.0,
                max_value=0.30,
                step=0.005,
                key="debt_interest_rate",
            )

        with c3:
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

    with st.expander("Fixe Betriebskosten", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.slider(
                "Wartung & Instandhaltung [- von CAPEX]",
                min_value=0.0,
                max_value=0.20,
                step=0.005,
                key="maintenance_share_of_capex",
            )

        with c2:
            st.number_input(
                "Personal [€/a]",
                min_value=0.0,
                max_value=100_000_000.0,
                step=10_000.0,
                key="personnel_eur_per_year",
            )

        with c3:
            st.number_input(
                "Sonstige fixe OPEX [€/a]",
                min_value=0.0,
                max_value=100_000_000.0,
                step=10_000.0,
                key="other_fixed_opex_eur_per_year",
            )

    with st.expander("Variable Betriebskosten", expanded=True):
        st.number_input(
            "Wasserkosten [€/kg H₂]",
            min_value=0.0,
            max_value=100.0,
            step=0.01,
            key="water_eur_per_kg_h2",
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
        st.dataframe(st.session_state.timeseries_df.head(24), use_container_width=True, height=260)


# ============================================================
# Tab 5: Ergebnisse
# ============================================================

with tabs[4]:
    st.subheader("Ergebnisse")

    bundle = st.session_state.result_bundle
    if bundle is None:
        st.info("Bitte die Berechnung über die Seitenleiste starten.")
    else:
        results = bundle["results"]
        dispatch_df = bundle["dispatch"]
        model_inputs = bundle["inputs"]

        with st.expander("Hauptkennzahlen", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("LCOH [€/kg]", f"{results['lcoh_eur_per_kg']:.2f}")
            c2.metric("LCOH [ct/kWh]", f"{results['lcoh_ct_per_kwh']:.2f}")
            c3.metric("H₂-Produktion [kg/a]", f"{results['annual_h2_kg']:,.0f}")
            c4.metric("Ely-Stromverbrauch [MWh/a]", f"{results['annual_ely_mwh']:,.0f}")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Ø Auslastung [-]", f"{results['avg_utilization']:.3f}")
            c6.metric("Betriebsstunden [h]", f"{results['operating_hours']:,}")
            c7.metric("Volllaststunden (eq.) [h/a]", f"{results['equivalent_full_load_hours']:,.0f}")
            c8.metric("Spotkosten [€/a]", f"{results['annual_spot_cost_eur']:,.0f}")

        with st.expander("Visualisierung", expanded=True):
            st.markdown("### Dauerlinie der Auslastung")
            duration_curve = np.sort(dispatch_df["utilization"].to_numpy())[::-1]
            duration_df = pd.DataFrame(
                {
                    "Stundenrang": np.arange(1, len(duration_curve) + 1),
                    "Auslastung": duration_curve,
                }
            )
            st.line_chart(duration_df.set_index("Stundenrang"))

            st.markdown("### Strommix (Jahressummen)")
            mix_df = pd.DataFrame(
                {
                    "Kategorie": ["PPA", "Spot", "Systemverbrauch", "Ely-Verbrauch"],
                    "kWh/a": [
                        dispatch_df["ppa_supply_kwh"].sum(),
                        dispatch_df["spot_supply_kwh"].sum(),
                        dispatch_df["system_consumption_kwh"].sum(),
                        dispatch_df["ely_consumption_kwh"].sum(),
                    ],
                }
            ).set_index("Kategorie")
            st.bar_chart(mix_df)

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

            export_csv = pd.DataFrame([results]).to_csv(index=False).encode("utf-8")
            st.download_button(
                "KPIs als CSV herunterladen",
                export_csv,
                "lcoh_kpis.csv",
                "text/csv",
            )