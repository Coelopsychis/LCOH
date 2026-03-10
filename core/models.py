from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SystemInputs:
    commissioning_year: int = 2026
    project_lifetime_years: int = 20

    electrolyzer_power_kw: float = 25_000.0
    system_power_kw: float = 28_000.0
    min_load_fraction: float = 0.20

    avg_efficiency_h2_per_el: float = 0.70

    stack_lifetime_years: int = 8
    degradation_per_year: float = 0.0


@dataclass
class CapexInputs:
    # Allgemeine CAPEX
    epc_eur_per_kw: float = 300.0
    bop_eur_per_kw: float = 250.0
    hochbau_eur_per_kw: float = 100.0
    tiefbau_eur_per_kw: float = 80.0
    individual_specific_eur_per_kw: float = 0.0
    individual_fixed_eur: float = 0.0

    # Abwärme
    waste_heat_enabled: bool = False
    waste_heat_system_eur_per_kw: float = 0.0

    # Sauerstoff
    oxygen_enabled: bool = False
    oxygen_system_eur_per_kw: float = 0.0

    # H2-Aufbereitung / Verdichtung
    compression_enabled: bool = False
    compressor_system_eur_per_kw: float = 0.0

    # Batteriesystem
    battery_enabled: bool = False
    battery_capacity_factor_kwh_per_kw: float = 0.0
    battery_power_kw: float = 0.0
    battery_invest_eur_per_kwh: float = 0.0

    # Finanzierung
    discount_rate: float = 0.08
    debt_interest_rate: float = 0.05
    equity_share: float = 0.30
    stack_replacement_specific_eur_per_kw: float = 250.0


@dataclass
class OpexInputs:
    # Wartung & Instandhaltung
    maintenance_share_of_capex: float = 0.005
    maintenance_escalation_per_year: float = 0.025

    # Personalkosten
    personnel_eur_per_year: float = 85_000.0
    personnel_escalation_per_year: float = 0.02

    # Rückstellungen
    reserve_remaining_plant_share_of_capex: float = 0.01
    reserve_decommissioning_share_of_capex: float = 0.0025
    reserve_escalation_per_year: float = 0.01

    # Wasser
    freshwater_price_eur_per_m3: float = 4.0
    freshwater_treatment_price_eur_per_m3: float = 5.0
    wastewater_price_eur_per_m3: float = 6.5
    water_escalation_per_year: float = 0.01

    # Individuelle OPEX
    individual_opex_share_of_capex: float = 0.005
    individual_opex_escalation_per_year: float = 0.01


@dataclass
class PowerInputs:
    baseload_enabled: bool = False
    baseload_kw: float = 0.0

    ppa_pv_enabled: bool = True
    ppa_pv_capacity_kw: float = 10_000.0

    ppa_wind_enabled: bool = True
    ppa_wind_capacity_kw: float = 10_000.0

    spot_enabled: bool = True
    spot_price_limit_eur_per_mwh: float = 50.0


@dataclass
class ModelInputs:
    system: SystemInputs
    capex: CapexInputs
    opex: OpexInputs
    power: PowerInputs