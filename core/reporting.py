from __future__ import annotations

import numpy as np
import pandas as pd


def lcoh_bridge(results: dict) -> pd.DataFrame:
    """Annual cost/revenue bridge whose sum equals annual LCOH numerator."""
    rows = [
        ("Finanzierung (FK + EK)", float(results["financing_eur_per_year"]), "Kosten"),
        ("Stackersatz", float(results["stack_replacement_eur_per_year"]), "Kosten"),
        ("OPEX", float(results["total_opex_eur_per_year"]), "Kosten"),
        ("Stromkosten brutto", float(results["annual_power_cost_gross_eur"]), "Kosten"),
        ("Strompreisförderung", -float(results["electricity_subsidy_eur_per_year"]), "Förderung"),
        ("Strompreiskompensation", -float(results["spk_revenue_eur_per_year"]), "Förderung"),
        ("Stromverkauf", -float(results["power_sale_revenue_eur_per_year"]), "Erlös"),
        ("THG-Quote", -float(results["thg_revenue_eur_per_year"]), "Erlös"),
        ("Sauerstoff", -float(results["oxygen_revenue_eur_per_year"]), "Erlös"),
        ("Abwärme", -float(results["waste_heat_revenue_eur_per_year"]), "Erlös"),
        ("Regelenergie", -float(results["balancing_energy_revenue_eur_per_year"]), "Erlös"),
        ("Sonstige Erlöse", -float(results["other_revenue_eur_per_year"]), "Erlös"),
    ]
    df = pd.DataFrame(rows, columns=["Komponente", "€/a", "Typ"])
    annual_h2 = float(results["annual_h2_kg"])
    df["€/kg H₂"] = df["€/a"] / annual_h2 if annual_h2 > 0 else float("nan")
    return df


def positive_cost_distribution(results: dict) -> pd.DataFrame:
    rows = [
        ("Finanzierung", float(results["financing_eur_per_year"])),
        ("Stackersatz", float(results["stack_replacement_eur_per_year"])),
        ("OPEX", float(results["total_opex_eur_per_year"])),
        ("Strombeschaffung", float(results["annual_procurement_cost_eur"])),
        ("Stromnebenkosten", float(results["annual_power_addons_eur"])),
    ]
    return pd.DataFrame(rows, columns=["Komponente", "€/a"])


def revenue_distribution(results: dict) -> pd.DataFrame:
    rows = [
        ("Strompreisförderung", float(results["electricity_subsidy_eur_per_year"])),
        ("Strompreiskompensation", float(results["spk_revenue_eur_per_year"])),
        ("Stromverkauf", float(results["power_sale_revenue_eur_per_year"])),
        ("THG-Quote", float(results["thg_revenue_eur_per_year"])),
        ("Sauerstoff", float(results["oxygen_revenue_eur_per_year"])),
        ("Abwärme", float(results["waste_heat_revenue_eur_per_year"])),
        ("Regelenergie", float(results["balancing_energy_revenue_eur_per_year"])),
        ("Sonstige", float(results["other_revenue_eur_per_year"])),
    ]
    df = pd.DataFrame(rows, columns=["Komponente", "€/a"])
    return df[df["€/a"] > 0].reset_index(drop=True)


def utilization_duration_curve(dispatch_df: pd.DataFrame) -> pd.DataFrame:
    """Return a robust load-duration curve from the hourly utilization series.

    ``utilization`` is stored as a fraction in the dispatch (0...1). Invalid
    values are discarded and the remaining values are clipped to the physical
    interval before sorting in descending order. The result is presentation-
    ready in percent and deliberately independent of Streamlit's implicit chart
    data conversion.
    """
    if "utilization" not in dispatch_df.columns:
        return pd.DataFrame(columns=["Stundenrang", "Auslastung [%]"])

    values = pd.to_numeric(dispatch_df["utilization"], errors="coerce").to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return pd.DataFrame(columns=["Stundenrang", "Auslastung [%]"])

    values = np.clip(values, 0.0, 1.0)
    values = np.sort(values)[::-1] * 100.0
    return pd.DataFrame(
        {
            "Stundenrang": np.arange(1, values.size + 1, dtype=int),
            "Auslastung [%]": values,
        }
    )


# ---------------------------------------------------------------------------
# Complete scalar result overview / export helpers
# ---------------------------------------------------------------------------

_RESULT_LABELS = {
    # Core KPIs
    "lcoh_eur_per_kg": "LCOH",
    "lcoh_ct_per_kwh": "LCOH",
    "annual_h2_kg": "Wasserstoffproduktion",
    "annual_h2_kwh": "H₂-Energieproduktion",
    "average_efficiency_h2_per_el": "Ø Wirkungsgrad inkl. Degradation",
    "avg_utilization": "Durchschnittliche Auslastung",
    "operating_hours": "Betriebsstunden",
    "full_load_hours_count": "Volllaststunden (gezählt)",
    "partial_load_hours": "Teillaststunden",
    "equivalent_full_load_hours": "Äquivalente Volllaststunden",
    "green_hydrogen_share": "Anteil grüner Wasserstoff",
    # CAPEX / plant
    "gross_capex_eur": "CAPEX vor Förderung",
    "total_capex_eur": "CAPEX nach Förderung",
    "net_capex_eur": "Netto-CAPEX",
    "direct_capex_eur": "Direkte CAPEX",
    "specific_capex_before_subsidy_eur_per_kw": "Spezifische CAPEX vor Förderung",
    "specific_capex_eur_per_kw": "Spezifische CAPEX nach Förderung",
    "electrolyzer_cost_eur": "Elektrolyseur-CAPEX",
    "epc_cost_eur": "EPC-CAPEX",
    "bop_cost_eur": "Balance-of-Plant-CAPEX",
    "hochbau_cost_eur": "Hochbau-CAPEX",
    "tiefbau_cost_eur": "Tiefbau-CAPEX",
    "individual_specific_total_eur_per_kw": "Individuelle CAPEX spezifisch gesamt",
    "individual_specific_cost_eur": "Individuelle CAPEX",
    "individual_fixed_cost_eur": "Individuelle fixe CAPEX",
    "waste_heat_cost_eur": "CAPEX Abwärmesystem",
    "oxygen_cost_eur": "CAPEX Sauerstoffsystem",
    "compressor_cost_eur": "CAPEX H₂-Kompressor",
    "h2_direct_system_cost_eur": "CAPEX H₂-Direktsystem",
    "h2_treatment_cost_eur": "CAPEX H₂-Aufbereitung",
    "battery_cost_eur": "CAPEX Batteriesystem",
    "installed_system_power_kw": "Installierte Systemleistung",
    "peripheral_power_kw": "Peripherieleistung",
    "h2_compressor_power_kw": "H₂-Verdichterleistung",
    "oxygen_compressor_power_kw": "O₂-Verdichterleistung",
    "battery_system_power_kw": "Batterie-Systemleistung",
    "battery_capacity_kwh": "Speicherkapazität",
    "h2_compressor_ideal_kwh_per_t": "H₂-Verdichterarbeit ideal",
    "h2_compressor_real_kwh_per_t": "H₂-Verdichterarbeit real",
    "oxygen_compressor_ideal_kwh_per_t": "O₂-Verdichterarbeit ideal",
    "oxygen_compressor_real_kwh_per_t": "O₂-Verdichterarbeit real",
    # Financing / stack
    "debt_share": "Fremdkapitalquote",
    "equity_share": "Eigenkapitalquote",
    "debt_required_eur": "Fremdkapitalbedarf",
    "equity_required_eur": "Eigenkapitalbedarf",
    "debt_annuity_eur_per_year": "FK-Annuität",
    "equity_annuity_eur_per_year": "EK-Annuität",
    "financing_eur_per_year": "Finanzierung (FK + EK)",
    "annualized_capex_eur_per_year": "Finanzierung / annualisierte CAPEX",
    "wacc": "WACC (KPI)",
    "annuity_factor": "Annuitätenfaktor (Legacy)",
    "stack_replacement_count": "Anzahl Stackwechsel",
    "stack_replacement_interval_years": "Stackwechselintervall",
    "stack_average_specific_cost_eur_per_kw": "Ø spezifische Stackersatzkosten",
    "stack_replacement_cost_eur": "Stackersatzkosten gesamt",
    "stack_reserve_amount_eur": "Stack-Rückstellungsanteil",
    "stack_financing_amount_eur": "Stack-Finanzierungsanteil",
    "stack_replacement_eur_per_year": "Stackersatz jährlich",
    # OPEX / water
    "opex_calculation_mode": "OPEX-Berechnungsmodus",
    "maintenance_eur_per_year": "Wartung & Instandhaltung",
    "maintenance_escalation_per_year": "Preisentwicklung Wartung",
    "personnel_eur_per_year": "Personalkosten",
    "personnel_escalation_per_year": "Preisentwicklung Personal",
    "reserve_remaining_plant_eur_per_year": "Rückstellungen Restanlage",
    "reserve_decommissioning_eur_per_year": "Rückstellungen Rückbau",
    "reserves_total_eur_per_year": "Rückstellungen gesamt",
    "reserve_escalation_per_year": "Preisentwicklung Rückstellungen",
    "annual_freshwater_demand_m3": "Frischwasserbedarf",
    "annual_wastewater_m3": "Abwassermenge",
    "annual_water_demand_m3": "Wasserbedarf",
    "water_cost_per_m3": "Wasserkosten spezifisch",
    "water_eur_per_year": "Wasserkosten gesamt",
    "water_escalation_per_year": "Preisentwicklung Wasser",
    "individual_opex_eur_per_year": "Individuelle OPEX",
    "individual_opex_escalation_per_year": "Preisentwicklung individuelle OPEX",
    "detailed_opex_before_subsidy_eur_per_year": "Detaillierte OPEX vor Förderung",
    "lump_sum_opex_before_subsidy_eur_per_year": "Pauschale OPEX vor Förderung",
    "opex_subsidy_calculated_eur_per_year": "OPEX-Förderung berechnet",
    "opex_subsidy_applied_eur_per_year": "OPEX-Förderung angewendet",
    "total_opex_eur_per_year": "OPEX gesamt",
    # Energy / dispatch
    "annual_system_kwh": "Systemstromverbrauch",
    "annual_system_mwh": "Systemstromverbrauch",
    "annual_ely_kwh": "Elektrolyseur-Stromverbrauch",
    "annual_ely_mwh": "Elektrolyseur-Stromverbrauch",
    "annual_rest_kwh": "Reststromverbrauch",
    "annual_rest_mwh": "Reststromverbrauch",
    "annual_peripheral_kwh": "Peripherie-Stromverbrauch",
    "annual_peripheral_mwh": "Peripherie-Stromverbrauch",
    "annual_h2_compressor_kwh": "H₂-Verdichterstrom",
    "annual_h2_compressor_mwh": "H₂-Verdichterstrom",
    "annual_oxygen_compressor_kwh": "O₂-Verdichterstrom",
    "annual_oxygen_compressor_mwh": "O₂-Verdichterstrom",
    "annual_baseload_available_kwh": "Baseload-PPA verfügbar",
    "annual_pv_available_kwh": "PV-PPA verfügbar",
    "annual_wind_available_kwh": "Wind-PPA verfügbar",
    "annual_ppa_available_kwh": "PPA gesamt verfügbar",
    "annual_baseload_used_kwh": "Baseload-PPA genutzt",
    "annual_pv_used_kwh": "PV-PPA genutzt",
    "annual_wind_used_kwh": "Wind-PPA genutzt",
    "annual_ppa_used_kwh": "PPA gesamt genutzt",
    "annual_section7_kwh": "§7-Strombezug",
    "annual_section13k_kwh": "§13k-Strombezug",
    "section7_hours": "§7-Bezugsstunden",
    "section13k_hours": "§13k-Bezugsstunden",
    "annual_battery_charge_kwh": "Batterieladung",
    "annual_battery_discharge_kwh": "Batterieentladung",
    "battery_cycles_per_year": "Ladezyklen (Excel-KPI)",
    "annual_spot_purchase_kwh": "Spotmarktbezug",
    "annual_spot_sale_kwh": "Spotverkauf",
    "annual_ppa_sale_kwh": "PPA-Verkauf",
    "annual_power_sale_kwh": "Stromverkauf gesamt",
    "annual_curtailed_kwh": "Abregelung",
    "annual_ppa_kwh": "PPA-Strommenge",
    "annual_spot_kwh": "Spot-Strommenge",
    "annual_total_procured_kwh": "Strombeschaffung gesamt",
    # Electricity costs
    "annual_baseload_cost_eur": "Kosten Baseload-PPA",
    "annual_pv_ppa_cost_eur": "Kosten PV-PPA",
    "annual_wind_ppa_cost_eur": "Kosten Wind-PPA",
    "annual_section7_cost_eur": "Kosten §7",
    "annual_section13k_cost_eur": "Kosten §13k",
    "annual_spot_purchase_cost_eur": "Kosten Spotbezug",
    "annual_spot_cost_eur": "Kosten Spotbezug (Alias)",
    "annual_procurement_cost_eur": "Strombeschaffungskosten",
    "average_procurement_price_eur_per_mwh": "Ø Strombeschaffungspreis",
    "ely_grid_fee_eur_per_mwh": "Netzentgelt Elektrolyseur",
    "ely_electricity_tax_eur_per_mwh": "Stromsteuer Elektrolyseur",
    "ely_concession_fee_eur_per_mwh": "Konzessionsabgabe Elektrolyseur",
    "ely_kwk_levy_eur_per_mwh": "KWK-Aufschlag Elektrolyseur",
    "ely_stromnev19_levy_eur_per_mwh": "StromNEV-§19 Elektrolyseur",
    "ely_offshore_levy_eur_per_mwh": "Offshore-Netzumlage Elektrolyseur",
    "rest_grid_fee_eur_per_mwh": "Netzentgelt Rest",
    "rest_electricity_tax_eur_per_mwh": "Stromsteuer Rest",
    "rest_concession_fee_eur_per_mwh": "Konzessionsabgabe Rest",
    "rest_kwk_levy_eur_per_mwh": "KWK-Aufschlag Rest",
    "rest_stromnev19_levy_eur_per_mwh": "StromNEV-§19 Rest",
    "rest_offshore_levy_eur_per_mwh": "Offshore-Netzumlage Rest",
    "ely_variable_power_surcharge_eur_per_mwh": "Variable Stromnebenkosten Elektrolyseur",
    "rest_variable_power_surcharge_eur_per_mwh": "Variable Stromnebenkosten Rest",
    "ely_demand_charge_eur_per_year": "Leistungspreis Elektrolyseur",
    "rest_demand_charge_eur_per_year": "Leistungspreis Rest",
    "ely_demand_charge_eur_per_mwh": "Leistungspreis Elektrolyseur spezifisch",
    "rest_demand_charge_eur_per_mwh": "Leistungspreis Rest spezifisch",
    "ely_power_addons_eur_per_year": "Stromnebenkosten Elektrolyseur",
    "rest_power_addons_eur_per_year": "Stromnebenkosten Rest",
    "annual_power_addons_eur": "Stromnebenkosten gesamt",
    "annual_power_cost_without_privileges_eur": "Stromkosten ohne Privilegierungen",
    "privilege_savings_eur_per_year": "Ersparnis Privilegierungen",
    "electricity_price_ely_eur_per_mwh": "Strompreis Elektrolyseur",
    "electricity_price_rest_eur_per_mwh": "Strompreis Rest",
    "annual_power_cost_gross_eur": "Stromkosten brutto",
    "electricity_subsidy_eur_per_year": "Strompreisförderung",
    "annual_power_cost_after_subsidy_eur": "Stromkosten nach Förderung",
    "annual_power_revenue_eur": "Stromerlöse",
    "annual_power_cost_net_eur": "Stromkosten netto inkl. Verkauf",
    "annual_power_costs_eur": "Stromkosten netto (Alias)",
    "annual_spot_sale_revenue_eur": "Spotverkaufserlös",
    "annual_ppa_sale_revenue_eur": "PPA-Verkaufserlös",
    "annual_power_sale_revenue_eur": "Stromverkaufserlös gesamt",
    "average_ppa_sale_price_eur_per_mwh": "Ø PPA-Verkaufspreis",
    "average_power_sale_price_eur_per_mwh": "Ø Stromverkaufspreis",
    # Revenues / funding
    "thg_reduction_tco2_per_year": "THG-Minderung",
    "thg_revenue_eur_per_year": "THG-Quotenerlös",
    "annual_oxygen_kg": "Sauerstoffproduktion",
    "annual_oxygen_t": "Sauerstoffproduktion",
    "average_oxygen_price_eur_per_t": "Ø Sauerstoffpreis",
    "oxygen_revenue_eur_per_year": "Sauerstofferlös",
    "ely_waste_heat_mwh_per_year": "Abwärme Elektrolyseur",
    "h2_compressor_waste_heat_mwh_per_year": "Abwärme H₂-Verdichter",
    "oxygen_compressor_waste_heat_mwh_per_year": "Abwärme O₂-Verdichter",
    "total_waste_heat_mwh_per_year": "Abwärme gesamt",
    "usable_waste_heat_mwh_per_year": "Nutzbare Abwärme",
    "average_waste_heat_price_eur_per_mwh": "Ø Abwärmepreis",
    "waste_heat_revenue_eur_per_year": "Abwärmeerlös",
    "power_sale_revenue_eur_per_year": "Stromverkauf",
    "balancing_energy_revenue_eur_per_year": "Regelenergieerlös",
    "other_revenue_1_eur_per_year": "Sonstige Einnahmen 1",
    "other_revenue_2_eur_per_year": "Sonstige Einnahmen 2",
    "legacy_other_revenue_eur_per_year": "Sonstige Erlöse Legacy",
    "other_revenue_eur_per_year": "Sonstige Erlöse gesamt",
    "total_other_revenues_eur_per_year": "Weitere Einnahmen Total",
    "capex_subsidy_total_eur": "CAPEX-Förderung gesamt",
    "capex_subsidy_eur_per_year": "CAPEX-Förderung Ø",
    "spk_revenue_eur_per_year": "Strompreiskompensation",
    "spk_calculated_revenue_eur_per_year": "SPK-Rechnerergebnis",
    "spk_separate_average_eur_per_year": "SPK separat Ø",
    "spk_average_eua_price_eur_per_tco2": "SPK Ø EUA-Preis",
    "spk_fallback_factor": "SPK-Fallback-Faktor",
    "spk_eligible_consumption_mwh_per_year": "SPK-förderfähiger Verbrauch",
    "spk_aid_intensity": "SPK-Beihilfeintensität",
    "spk_co2_factor_t_per_mwh": "SPK-CO₂-Faktor",
    "annual_funding_total_eur_per_year": "Förderungen/Privilegien gesamt",
    # Total result numerator
    "annual_costs_before_revenues_eur_per_year": "Jährliche Kosten vor Erlösen",
    "annual_costs_eur_per_year": "Kosten nach Erlösen",
}


def _result_category(key: str) -> str:
    """Best-effort presentation category for a scalar result key."""
    if key.startswith("lcoh_") or key in {
        "annual_costs_eur_per_year", "annual_costs_before_revenues_eur_per_year",
        "annual_h2_kg", "annual_h2_kwh", "average_efficiency_h2_per_el",
        "avg_utilization", "operating_hours", "full_load_hours_count",
        "partial_load_hours", "equivalent_full_load_hours", "green_hydrogen_share",
    }:
        return "Kern-KPIs & Betrieb"
    if key.startswith("stack_"):
        return "Stacktausch"
    if any(token in key for token in ("debt", "equity", "financing", "wacc", "annuity")):
        return "Finanzierung"
    if any(token in key for token in ("maintenance", "personnel", "reserve", "water", "opex")):
        return "OPEX & Wasser"
    if any(token in key for token in ("subsidy", "privilege", "spk_", "funding")):
        return "Förderungen & SPK"
    if any(token in key for token in ("thg_", "oxygen_revenue", "waste_heat_revenue", "power_sale_revenue", "balancing_energy", "other_revenue", "total_other_revenues")):
        return "Erlöse & Nebenprodukte"
    if any(token in key for token in ("power_cost", "procurement", "grid_fee", "electricity_tax", "concession_fee", "kwk_", "stromnev", "offshore", "demand_charge", "power_addons", "spot_sale_revenue", "ppa_sale_revenue", "electricity_price")):
        return "Stromkosten & Privilegierungen"
    if key.startswith("annual_") and any(token in key for token in ("kwh", "mwh", "hours")):
        return "Energiemengen & Dispatch"
    if any(token in key for token in ("capex", "cost_eur", "system_power", "compressor_power", "battery_", "specific_cost")):
        return "CAPEX & Anlagen"
    if any(token in key for token in ("oxygen_", "waste_heat_", "compressor_")):
        return "Aufbereitung & Nebenprodukte"
    return "Weitere Modellkennzahlen"


def _result_unit(key: str) -> str:
    """Infer the user-facing unit from the established result key naming."""
    percentage_keys = {
        "debt_share", "equity_share", "wacc", "average_efficiency_h2_per_el",
        "avg_utilization", "green_hydrogen_share", "maintenance_escalation_per_year",
        "personnel_escalation_per_year", "reserve_escalation_per_year",
        "water_escalation_per_year", "individual_opex_escalation_per_year",
        "spk_aid_intensity",
    }
    if key in percentage_keys or key.endswith("_share") or key.endswith("_escalation_per_year"):
        return "%"
    if key == "lcoh_eur_per_kg": return "€/kg H₂"
    if key == "lcoh_ct_per_kwh": return "ct/kWh H₂"
    if key.endswith("_eur_per_tco2"): return "€/t CO₂"
    if key.endswith("_tco2_per_year"): return "t CO₂/a"
    if key.endswith("_eur_per_mwh"): return "€/MWh"
    if key.endswith("_eur_per_kw_month"): return "€/kW·Monat"
    if key.endswith("_eur_per_kw"): return "€/kW"
    if key.endswith("_eur_per_kg_h2"): return "€/kg H₂"
    if key.endswith("_eur_per_t"): return "€/t"
    if key.endswith("_eur_per_year"): return "€/a"
    if key.endswith("_eur"): return "€"
    if key.endswith("_kwh_per_t"): return "kWh/t"
    if key.endswith("_mwh_per_year"): return "MWh/a"
    if key.endswith("_mwh"):
        return "MWh/a" if key.startswith("annual_") else "MWh"
    if key.endswith("_kwh"):
        return "kWh/a" if key.startswith("annual_") else "kWh"
    if key.endswith("_kg"):
        return "kg/a" if key.startswith("annual_") else "kg"
    if key.endswith("_t"):
        return "t/a" if key.startswith("annual_") else "t"
    if key.endswith("_m3"):
        return "m³/a" if key.startswith("annual_") else "m³"
    if key.endswith("_kw"): return "kW"
    if key.endswith("_years"): return "a"
    if key in {"operating_hours", "full_load_hours_count", "partial_load_hours", "section7_hours", "section13k_hours"}:
        return "h"
    if key == "equivalent_full_load_hours": return "h/a"
    if key.endswith("_hours"): return "h"
    if key == "stack_replacement_count": return "Anzahl"
    if key == "battery_cycles_per_year": return "Anzahl/a"
    if key.endswith("_count"): return "Anzahl"
    if key.endswith("_factor"): return "–"
    return "–"


def _result_label(key: str) -> str:
    if key in _RESULT_LABELS:
        return _RESULT_LABELS[key]
    # Fallback remains understandable and exposes the exact key separately.
    return key.replace("_", " ").strip().capitalize()


def _presentation_numeric_value(key: str, value: float) -> float:
    """Convert internal fractions to percentage points for the overview only."""
    if _result_unit(key) == "%":
        return float(value) * 100.0
    return float(value)


def complete_result_overview(results: dict, *, derived: dict | None = None) -> pd.DataFrame:
    """Return every scalar result in one long, export-friendly table.

    This deliberately includes more than the compact result expanders. That way
    the table and CSV remain complete when new scalar KPIs are added to the
    calculation. ``derived`` can add presentation-only scalar KPIs that are not
    stored in the finance result dict itself.
    """
    rows: list[dict] = []
    combined = dict(results)
    if derived:
        combined.update(derived)

    derived_meta = {
        "lcoh_before_operating_relief_eur_per_kg": (
            "Kern-KPIs & Betrieb", "LCOH vor laufenden Entlastungen", "€/kg H₂"
        ),
        "operating_relief_eur_per_year": (
            "Förderungen & SPK", "Laufende Förderungen & Erlöse", "€/a"
        ),
        "oxygen_and_waste_heat_revenue_eur_per_year": (
            "Erlöse & Nebenprodukte", "Sauerstoff + Abwärme", "€/a"
        ),
    }

    for key, value in combined.items():
        # Scalar outputs only. Hourly dispatch belongs to the simulation, not the
        # KPI table; its annual aggregates are already part of ``results``.
        if isinstance(value, (np.generic,)):
            value = value.item()
        if not isinstance(value, (str, bool, int, float)) and value is not None:
            continue

        if key in derived_meta:
            category, label, unit = derived_meta[key]
        else:
            category, label, unit = _result_category(key), _result_label(key), _result_unit(key)

        raw_value = value
        presentation_value = value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            presentation_value = _presentation_numeric_value(key, value)

        rows.append(
            {
                "Kategorie": category,
                "Kennzahl": label,
                "Wert": presentation_value,
                "Einheit": unit,
                "Schlüssel": key,
                "Rohwert": raw_value,
            }
        )

    category_order = {
        name: idx for idx, name in enumerate([
            "Kern-KPIs & Betrieb", "CAPEX & Anlagen", "Finanzierung", "Stacktausch",
            "OPEX & Wasser", "Energiemengen & Dispatch", "Stromkosten & Privilegierungen",
            "Förderungen & SPK", "Erlöse & Nebenprodukte", "Aufbereitung & Nebenprodukte",
            "Weitere Modellkennzahlen",
        ])
    }
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["_sort"] = df["Kategorie"].map(category_order).fillna(999)
    df = df.sort_values(["_sort", "Kennzahl", "Schlüssel"], kind="stable").drop(columns="_sort")
    return df.reset_index(drop=True)


def json_compatible(value):
    """Recursively convert numpy/pandas scalars and non-finite floats to strict JSON."""
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, dict):
        return {str(k): json_compatible(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_compatible(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return value
