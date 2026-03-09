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
    electrolyzer_specific_eur_per_kw: float = 1_000.0
    bop_specific_eur_per_kw: float = 250.0
    infrastructure_specific_eur_per_kw: float = 150.0
    development_share: float = 0.05

    stack_replacement_specific_eur_per_kw: float = 250.0

    discount_rate: float = 0.08
    debt_interest_rate: float = 0.05
    equity_share: float = 0.30


@dataclass
class OpexInputs:
    maintenance_share_of_capex: float = 0.03
    personnel_eur_per_year: float = 300_000.0
    other_fixed_opex_eur_per_year: float = 100_000.0
    water_eur_per_kg_h2: float = 0.05


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