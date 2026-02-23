from __future__ import annotations

import io
import json
from dataclasses import asdict
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

from core.inputs import ScalarInputs
from core.timeseries import to_hourly_series, HourlySeries
from core.dispatch import run_dispatch_skeleton
from core.kpis import compute_kpis, CoreKPIs

# Optional Excel loading (only if openpyxl available & you want it)
try:
    from core.excel_io import load_case_from_excel, load_kwh_per_kg_factor
    EXCEL_IO_AVAILABLE = True
except Exception:
    EXCEL_IO_AVAILABLE = False


APP_TITLE = "H₂ Electrolyzer LCOH Tool (Mockup/MVP)"
DEFAULT_KWH_PER_KG = 39.4  # typical LHV-ish ballpark; Excel ref comes from sheet3 C6

st.set_page_config(page_title=APP_TITLE, layout="wide")

# ----------------------------
# Helpers
# ----------------------------

def _init_state() -> None:
    if "scalars" not in st.session_state:
        st.session_state.scalars = ScalarInputs(
            commissioning_year=2026,
            ely_kW=25_000.0,
            system_min_load=0.2,
            system_kW_override=None,
            spot_enabled=True,
            spot_price_threshold_eur_per_mwh=50.0,
            ppa1_enabled=True,
            ppa2_enabled=True,
            ppa1_kW=10_000.0,
            ppa2_kW=10_000.0,
            baseload_enabled=False,
            baseload_kW=0.0,
            avg_efficiency=0.7,
        )

    if "kwh_per_kg_h2" not in st.session_state:
        st.session_state.kwh_per_kg_h2 = DEFAULT_KWH_PER_KG

    if "ts" not in st.session_state:
        # default demo series (plausible shapes, 8760h)
        st.session_state.ts = make_demo_timeseries()

    if "last_result" not in st.session_state:
        st.session_state.last_result = None  # (CoreKPIs, dispatch, inputs snapshot)


def make_demo_timeseries(seed: int = 7) -> HourlySeries:
    """
    Creates a plausible 8760h demo dataset (NOT real meteorology).
    - PV: daily sinus with seasonal variation
    - Wind: noisy seasonal-ish
    - Day-ahead price: seasonal + random with occasional negatives
    """
    rng = np.random.default_rng(seed)
    n = 8760
    hours = np.arange(n)

    # Seasonality factor across year (0..1)
    season = 0.5 + 0.5 * np.sin(2 * np.pi * (hours / n - 0.2))

    # PV: daylight approx with daily cycle + season
    day = hours % 24
    pv_day = np.clip(np.sin(np.pi * (day - 6) / 12), 0, None)  # peak around noon
    pv = pv_day * (0.2 + 0.8 * season)  # kWh/kW per hour (capacity factor-ish)

    # Wind: more in winter, noisy
    wind = np.clip(0.35 + 0.25 * (1 - season) + 0.15 * rng.normal(size=n), 0, 0.95)

    # Prices: base + seasonality + noise; occasional negatives
    price = 60 + 20 * (1 - season) + 25 * rng.normal(size=n)
    neg_mask = rng.random(n) < 0.02
    price[neg_mask] = -10 - 40 * rng.random(np.sum(neg_mask))
    price = np.clip(price, -80, 250)

    return to_hourly_series(pv.tolist(), wind.tolist(), price.tolist())


def parse_csv_series(uploaded_file, value_col: Optional[str] = None) -> list[float]:
    """
    Parse a CSV file that contains 8760 hourly values.
    Accepts either:
      - one numeric column, or
      - a specified value column.
    """
    df = pd.read_csv(uploaded_file)
    if value_col and value_col in df.columns:
        s = df[value_col]
    else:
        # auto pick first numeric column
        num_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if not num_cols:
            raise ValueError("CSV enthält keine numerische Spalte.")
        s = df[num_cols[0]]

    values = s.astype(float).to_list()
    if len(values) != 8760:
        raise ValueError(f"Erwartet 8760 Werte, gefunden: {len(values)}.")
    return values


def run_model(scalars: ScalarInputs, ts: HourlySeries, kwh_per_kg_h2: float) -> tuple[CoreKPIs, object]:
    dispatch = run_dispatch_skeleton(scalars, ts)
    kpis = compute_kpis(scalars, dispatch, kwh_per_kg_h2=kwh_per_kg_h2)
    return kpis, dispatch


def df_duration_curve(util: np.ndarray) -> pd.DataFrame:
    u = np.sort(util)[::-1]
    return pd.DataFrame({"hour_rank": np.arange(1, len(u) + 1), "utilization": u})


def df_mix(dispatch) -> pd.DataFrame:
    return pd.DataFrame({
        "PPA (kWh/a)": [float(np.sum(dispatch.supply_ppa_kwh))],
        "Spot (kWh/a)": [float(np.sum(dispatch.supply_spot_kwh))],
        "System consumption (kWh/a)": [float(np.sum(dispatch.system_consumption_kwh))],
        "Ely consumption (kWh/a)": [float(np.sum(dispatch.ely_consumption_kwh))],
    })


# ----------------------------
# UI
# ----------------------------

_init_state()

st.title(APP_TITLE)
st.caption("Mockup + MVP-fähig: Fokus auf Bedienung und plausible Ergebnisse. Rechenkern wird iterativ verbessert.")

tabs = st.tabs([
    "1) Projekt & Ely",
    "2) Strom & PPAs",
    "3) Zeitreihen",
    "4) Ergebnisse",
    "5) Export & Debug",
])

# ---- Tab 1: Project & Ely ----
with tabs[0]:
    st.subheader("Projekt & Elektrolyseur")

    s: ScalarInputs = st.session_state.scalars

    with st.form("form_project"):
        c1, c2, c3 = st.columns(3)

        with c1:
            commissioning_year = st.number_input("Inbetriebnahmejahr", min_value=2000, max_value=2100, value=int(s.commissioning_year), step=1)
            ely_kW = st.number_input("Ely-Nennleistung [kW]", min_value=1.0, value=float(s.ely_kW), step=100.0, format="%.1f")
            system_kW_override = st.number_input(
                "Systemleistung Override [kW] (optional)",
                min_value=0.0,
                value=float(s.system_kW_override or 0.0),
                step=100.0,
                help="Wenn 0: Systemleistung = Ely-Leistung (Skeleton). Später wird Systemleistung wie in Excel abgeleitet.",
                format="%.1f",
            )

        with c2:
            system_min_load = st.slider("Mindest-Teillast (System) [0..1]", 0.0, 1.0, float(s.system_min_load), 0.01)
            avg_efficiency = st.slider("Durchschnittl. Effizienz (Phase 1) [-]", 0.0, 1.0, float(s.avg_efficiency), 0.01)
            kwh_per_kg_h2 = st.number_input(
                "Umrechnung: kWh pro kg H₂ (z.B. aus Excel Nebenrechnungen C6)",
                min_value=0.0,
                value=float(st.session_state.kwh_per_kg_h2),
                step=0.1,
                format="%.3f",
            )

        with c3:
            st.markdown("**Hinweise**")
            st.write("- In Phase 1 nutzen wir eine **skalare** Effizienz (inkl. Degradation/Stacktausch so wie später implementiert).")
            st.write("- Teillast-Kennlinie η(u) und dynamische Degradation kommen später als Upgrade.")

        submitted = st.form_submit_button("Übernehmen")
        if submitted:
            st.session_state.scalars = ScalarInputs(
                commissioning_year=int(commissioning_year),
                ely_kW=float(ely_kW),
                system_min_load=float(system_min_load),
                system_kW_override=(None if system_kW_override <= 0 else float(system_kW_override)),
                spot_enabled=s.spot_enabled,
                spot_price_threshold_eur_per_mwh=s.spot_price_threshold_eur_per_mwh,
                ppa1_enabled=s.ppa1_enabled,
                ppa2_enabled=s.ppa2_enabled,
                ppa1_kW=s.ppa1_kW,
                ppa2_kW=s.ppa2_kW,
                baseload_enabled=s.baseload_enabled,
                baseload_kW=s.baseload_kW,
                avg_efficiency=float(avg_efficiency),
            )
            st.session_state.kwh_per_kg_h2 = float(kwh_per_kg_h2)
            st.success("Projektparameter übernommen.")


# ---- Tab 2: Power & PPAs ----
with tabs[1]:
    st.subheader("Strom & PPAs")

    s: ScalarInputs = st.session_state.scalars

    with st.form("form_power"):
        c1, c2, c3 = st.columns(3)

        with c1:
            ppa1_enabled = st.checkbox("PPA 1 aktiv (z.B. PV)", value=bool(s.ppa1_enabled))
            ppa1_kW = st.number_input("PPA 1 Leistung [kW]", min_value=0.0, value=float(s.ppa1_kW), step=100.0, format="%.1f")
            ppa2_enabled = st.checkbox("PPA 2 aktiv (z.B. Wind)", value=bool(s.ppa2_enabled))
            ppa2_kW = st.number_input("PPA 2 Leistung [kW]", min_value=0.0, value=float(s.ppa2_kW), step=100.0, format="%.1f")

        with c2:
            baseload_enabled = st.checkbox("Baseload PPA aktiv", value=bool(s.baseload_enabled))
            baseload_kW = st.number_input("Baseload [kW] (konstant pro Stunde)", min_value=0.0, value=float(s.baseload_kW), step=100.0, format="%.1f")
            spot_enabled = st.checkbox("Spotmarkt aktiv (Skeleton-Fill)", value=bool(s.spot_enabled))
            spot_thr = st.number_input("Spot Preis-Schwelle [€/MWh]", min_value=-200.0, value=float(s.spot_price_threshold_eur_per_mwh), step=1.0, format="%.1f")

        with c3:
            st.markdown("**Dispatch (Skeleton)**")
            st.write("1) PPA-Energie nutzen")
            st.write("2) Wenn Spot aktiv & Preis < Schwelle: auf 100% auffüllen")
            st.write("3) Mindestlast: darunter -> AUS")

        submitted = st.form_submit_button("Übernehmen")
        if submitted:
            st.session_state.scalars = ScalarInputs(
                commissioning_year=s.commissioning_year,
                ely_kW=s.ely_kW,
                system_min_load=s.system_min_load,
                system_kW_override=s.system_kW_override,
                spot_enabled=bool(spot_enabled),
                spot_price_threshold_eur_per_mwh=float(spot_thr),
                ppa1_enabled=bool(ppa1_enabled),
                ppa2_enabled=bool(ppa2_enabled),
                ppa1_kW=float(ppa1_kW),
                ppa2_kW=float(ppa2_kW),
                baseload_enabled=bool(baseload_enabled),
                baseload_kW=float(baseload_kW),
                avg_efficiency=s.avg_efficiency,
            )
            st.success("Strom-/PPA-Parameter übernommen.")


# ---- Tab 3: Time series ----
with tabs[2]:
    st.subheader("Zeitreihen (8760h)")

    st.write("Du kannst Demo-Daten nutzen, CSVs hochladen oder – falls verfügbar – aus der Excel-Datei ziehen.")

    cA, cB = st.columns(2)

    with cA:
        st.markdown("### Option A: Demo-Zeitreihen")
        if st.button("Demo-Daten laden"):
            st.session_state.ts = make_demo_timeseries()
            st.success("Demo-Zeitreihen geladen.")

    with cB:
        st.markdown("### Option B: CSV Upload")
        st.caption("CSV muss 8760 Zeilen mit einer numerischen Spalte enthalten (oder wähle die Spalte).")

        pv_file = st.file_uploader("PV/PPA1 Zeitreihe (kWh pro kW pro Stunde)", type=["csv"], key="pv_csv")
        wind_file = st.file_uploader("Wind/PPA2 Zeitreihe (kWh pro kW pro Stunde)", type=["csv"], key="wind_csv")
        price_file = st.file_uploader("Day-Ahead Preis (€/MWh)", type=["csv"], key="price_csv")

        if st.button("CSV Zeitreihen übernehmen"):
            try:
                if not (pv_file and wind_file and price_file):
                    raise ValueError("Bitte alle drei CSVs hochladen (PV, Wind, Preis).")
                pv = parse_csv_series(pv_file)
                wind = parse_csv_series(wind_file)
                price = parse_csv_series(price_file)
                st.session_state.ts = to_hourly_series(pv, wind, price)
                st.success("CSV-Zeitreihen übernommen.")
            except Exception as e:
                st.error(f"CSV-Import fehlgeschlagen: {e}")

    st.divider()

    if EXCEL_IO_AVAILABLE:
        st.markdown("### Option C: Excel Upload (optional)")
        excel_file = st.file_uploader("Excel-Datei (.xlsx) hochladen", type=["xlsx"], key="excel_xlsx")
        if excel_file is not None and st.button("Zeitreihen & Basiswerte aus Excel übernehmen"):
            try:
                # Write upload to BytesIO for openpyxl
                data = io.BytesIO(excel_file.getvalue())
                case = load_case_from_excel(data)
                st.session_state.scalars = case.scalars
                st.session_state.ts = case.ts
                # kWh/kg factor from Excel
                st.session_state.kwh_per_kg_h2 = load_kwh_per_kg_factor(data)
                st.success("Daten aus Excel übernommen.")
            except Exception as e:
                st.error(f"Excel-Import fehlgeschlagen: {e}")
    else:
        st.info("Excel-Import ist nicht verfügbar (excel_io konnte nicht geladen werden). CSV oder Demo nutzen.")

    # Preview
    ts: HourlySeries = st.session_state.ts
    st.markdown("### Preview")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("PV1 min/max", f"{float(np.min(ts.pv1_kwh_per_kw)):.3f} / {float(np.max(ts.pv1_kwh_per_kw)):.3f}")
    with col2:
        st.metric("Wind2 min/max", f"{float(np.min(ts.wind2_kwh_per_kw)):.3f} / {float(np.max(ts.wind2_kwh_per_kw)):.3f}")
    with col3:
        st.metric("Preis min/max (€/MWh)", f"{float(np.min(ts.day_ahead_eur_per_mwh)):.1f} / {float(np.max(ts.day_ahead_eur_per_mwh)):.1f}")

    preview_df = pd.DataFrame({
        "hour": np.arange(1, 25),
        "pv1_kwh_per_kw": ts.pv1_kwh_per_kw[:24],
        "wind2_kwh_per_kw": ts.wind2_kwh_per_kw[:24],
        "day_ahead_eur_per_mwh": ts.day_ahead_eur_per_mwh[:24],
    })
    st.dataframe(preview_df, use_container_width=True, height=260)


# ---- Tab 4: Results ----
with tabs[3]:
    st.subheader("Ergebnisse")

    left, right = st.columns([1, 1])

    with left:
        if st.button("Run Model", type="primary"):
            try:
                s: ScalarInputs = st.session_state.scalars
                ts: HourlySeries = st.session_state.ts
                kwh_per_kg = float(st.session_state.kwh_per_kg_h2)

                kpis, dispatch = run_model(s, ts, kwh_per_kg_h2=kwh_per_kg)
                st.session_state.last_result = (kpis, dispatch, s, kwh_per_kg)
                st.success("Berechnung abgeschlossen.")
            except Exception as e:
                st.error(f"Berechnung fehlgeschlagen: {e}")

        st.caption("Hinweis: LCOH (F3/F4) kommt erst, wenn Kostenblöcke implementiert sind. Hier zeigen wir die stundenbasierten KPIs.")

    with right:
        st.markdown("**Status**")
        if st.session_state.last_result is None:
            st.info("Noch keine Berechnung durchgeführt.")
        else:
            st.success("Letzte Berechnung ist verfügbar.")

    st.divider()

    if st.session_state.last_result is not None:
        kpis: CoreKPIs
        dispatch: object
        kpis, dispatch, s_used, kwh_per_kg_used = st.session_state.last_result

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("AA4 Ely-Strom [kWh/a]", f"{kpis.ely_electricity_year_kwh:,.0f}")
        c2.metric("H₂ Energie [kWh/a]", f"{kpis.h2_energy_year_kwh:,.0f}")
        c3.metric("H₂ Masse [kg/a]", f"{kpis.h2_mass_year_kg:,.0f}")
        c4.metric("Ø Auslastung [-]", f"{kpis.utilization_avg:.3f}")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Äquiv. Volllaststunden [h/a]", f"{kpis.eq_full_load_hours:,.0f}")
        c6.metric("Betriebsstunden [h]", f"{kpis.operating_hours:,}")
        c7.metric("Volllaststunden [h]", f"{kpis.full_load_hours:,}")
        c8.metric("Teillaststunden [h]", f"{kpis.partial_load_hours:,}")

        st.divider()

        # Charts
        ch1, ch2 = st.columns(2)

        with ch1:
            st.markdown("### Dauerlinie Auslastung AU")
            dur = df_duration_curve(dispatch.utilization)
            st.line_chart(dur.set_index("hour_rank")["utilization"], height=280)

        with ch2:
            st.markdown("### Strommix (Jahressummen)")
            mix = df_mix(dispatch).T
            mix.columns = ["kWh/a"]
            st.bar_chart(mix, height=280)

        st.markdown("### Preis vs. Betrieb (Stichprobe)")
        ts: HourlySeries = st.session_state.ts
        sample = pd.DataFrame({
            "price_eur_per_mwh": ts.day_ahead_eur_per_mwh,
            "utilization": dispatch.utilization,
        }).iloc[:1000]  # keep it light
        st.line_chart(sample, height=280)


# ---- Tab 5: Export & Debug ----
with tabs[4]:
    st.subheader("Export & Debug")

    if st.session_state.last_result is None:
        st.info("Erst berechnen, dann exportieren.")
    else:
        kpis, dispatch, s_used, kwh_per_kg_used = st.session_state.last_result

        st.markdown("### Inputs Snapshot")
        st.json({
            "scalars": asdict(s_used),
            "kwh_per_kg_h2": kwh_per_kg_used,
        })

        st.markdown("### KPI Export")
        kpi_dict = asdict(kpis)
        st.json(kpi_dict)

        # JSON download
        json_bytes = json.dumps({"inputs": asdict(s_used), "kpis": kpi_dict}, indent=2).encode("utf-8")
        st.download_button("Download JSON", data=json_bytes, file_name="results.json", mime="application/json")

        # CSV download
        kpi_df = pd.DataFrame([kpi_dict])
        csv_bytes = kpi_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download KPI CSV", data=csv_bytes, file_name="kpis.csv", mime="text/csv")

        st.divider()
        st.markdown("### Debug: erste 48 Stunden (AU, Verbrauch, Quellen)")
        dbg = pd.DataFrame({
            "hour": np.arange(1, 49),
            "AU": dispatch.utilization[:48],
            "system_kwh": dispatch.system_consumption_kwh[:48],
            "ely_kwh": dispatch.ely_consumption_kwh[:48],
            "ppa_kwh": dispatch.supply_ppa_kwh[:48],
            "spot_kwh": dispatch.supply_spot_kwh[:48],
        })
        st.dataframe(dbg, use_container_width=True, height=300)