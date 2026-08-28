from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SystemInputs:
    commissioning_year: int = 2026
    project_lifetime_years: int = 20

    electrolyzer_power_kw: float = 25_000.0
    # Stromverbrauch der Peripherie relativ zur Elektrolyseurleistung.
    # Die einfache Systemleistungs-Eigenschaft verwendet P_system = P_ely * (1 + Anteil).
    peripheral_power_fraction: float = 0.20
    min_load_fraction: float = 0.20

    # Nennwirkungsgrad des Elektrolyseurs bezogen auf H₂-Energie zu elektrischem Einsatz.
    avg_efficiency_h2_per_el: float = 0.70

    # Stacklebensdauer in äquivalenten Betriebsstunden und lineare
    # Wirkungsgraddegradation in Prozentpunkten pro Kalenderjahr.
    stack_lifetime_hours: float = 60_000.0
    degradation_per_year: float = 0.01

    @property
    def system_power_kw(self) -> float:
        return self.electrolyzer_power_kw * (1.0 + self.peripheral_power_fraction)


@dataclass
class CapexInputs:
    # Elektrolyseur und allgemeine spezifische Investitionskosten.
    electrolyzer_invest_eur_per_kw: float = 1_000.0
    epc_eur_per_kw: float = 125.0
    bop_eur_per_kw: float = 750.0
    hochbau_eur_per_kw: float = 1_000.0
    tiefbau_eur_per_kw: float = 300.0

    # Individuelle CAPEX setzen sich aus einem spezifischen Betrag, einem Anteil
    # der Elektrolyseurkosten und einem absoluten Fixbetrag zusammen.
    individual_specific_eur_per_kw: float = 50.0
    individual_ely_cost_share: float = 0.015
    individual_fixed_eur: float = 0.0

    # Abwärme
    waste_heat_enabled: bool = False
    waste_heat_system_eur_per_kw: float = 10.0

    # Sauerstoff
    oxygen_enabled: bool = False
    oxygen_system_eur_per_kw: float = 30.0

    # H₂-Aufbereitung: Auch bei direkter Nutzung kann ein separates Übergabe-/Aufbereitungssystem angesetzt werden.
    compression_enabled: bool = False
    compressor_system_eur_per_kw: float = 30.0
    h2_direct_system_eur_per_kw: float = 10.0

    # Technische Parameter für H₂- und O₂-Verdichter.
    h2_processed_share: float = 1.0
    h2_compressor_outlet_pressure_bar: float = 150.0
    h2_compressor_inlet_temperature_c: float = 20.0
    h2_compressor_inlet_pressure_bar: float = 10.0
    h2_compressor_efficiency: float = 0.75

    oxygen_compressor_outlet_pressure_bar: float = 300.0
    oxygen_compressor_inlet_temperature_c: float = 20.0
    oxygen_compressor_inlet_pressure_bar: float = 10.0
    oxygen_compressor_efficiency: float = 0.70

    # Batteriesystem: Kapazität, Ladeleistung und Investitionskosten.
    battery_enabled: bool = False
    battery_capacity_factor_kwh_per_kw: float = 5.0  # Stunden/Faktor * Systemleistung
    battery_power_kw: float = 50_000.0
    battery_invest_eur_per_kwh: float = 220.0
    battery_fixed_eur: float = 0.0

    # Finanzierung über Fremd- und Eigenkapital.
    debt_share: float = 0.75
    debt_interest_rate: float = 0.03
    equity_interest_rate: float = 0.10
    corporate_tax_rate: float = 0.30

    # Annahmen zu Stacktausch, Kostendegression und Finanzierung.
    stack_replacement_share_of_ely_capex: float = 0.40
    stack_cost_degression_per_year: float = -0.05
    stack_financing_interest_rate: float = 0.05


@dataclass
class OpexInputs:
    # Optional kann die gesamte OPEX pauschal als Anteil der nach CAPEX-Förderung
    # verbleibenden Investition angesetzt werden.
    lump_sum_enabled: bool = False
    lump_sum_share_of_capex: float = 0.0
    lump_sum_escalation_per_year: float = 0.0

    maintenance_share_of_capex: float = 0.005
    maintenance_escalation_per_year: float = 0.0

    personnel_eur_per_year: float = 85_000.0
    personnel_escalation_per_year: float = 0.0

    reserve_remaining_plant_share_of_capex: float = 0.01
    reserve_decommissioning_share_of_capex: float = 0.0025
    reserve_escalation_per_year: float = 0.0

    freshwater_price_eur_per_m3: float = 4.0
    freshwater_treatment_price_eur_per_m3: float = 5.0
    wastewater_price_eur_per_m3: float = 6.5
    water_escalation_per_year: float = 0.0

    individual_opex_share_of_capex: float = 0.005
    individual_opex_escalation_per_year: float = 0.0


@dataclass
class FundingInputs:
    """Förderungen und Strompreiskompensation.

    Interne ``mode``-Werte kodieren die auswählbaren Berechnungsvarianten:
    - CAPEX: ``none`` | ``percentage`` | ``absolute``
    - OPEX: ``none`` | ``per_kg`` | ``per_full_load_hour``
    - Strom: ``none`` | ``per_kg`` | ``per_mwh``
    - SPK: ``none`` | ``calculator`` | ``separate``
    """

    capex_mode: str = "none"
    capex_percentage: float = 0.0
    capex_absolute_eur_per_kw: float = 0.0

    opex_mode: str = "none"
    opex_eur_per_kg_h2: float = 0.0
    opex_eur_per_full_load_hour: float = 0.0

    electricity_mode: str = "none"
    electricity_eur_per_kg_h2: float = 0.0
    electricity_eur_per_mwh: float = 0.0

    spk_mode: str = "none"
    spk_eua_price_eur_per_tco2: float = 89.0
    spk_power_consumption_factor: float = 0.80
    spk_price_escalation_per_year: float = 0.0
    spk_separate_revenue_eur_per_year: float = 0.0


@dataclass
class PowerInputs:
    baseload_enabled: bool = False
    baseload_kw: float = 0.0
    baseload_price_eur_per_mwh: float = 70.0
    baseload_price_escalation_per_year: float = 0.0

    ppa_pv_enabled: bool = True
    ppa_pv_capacity_kw: float = 10_000.0
    ppa_pv_price_eur_per_mwh: float = 40.0

    ppa_wind_enabled: bool = True
    ppa_wind_capacity_kw: float = 35_000.0
    ppa_wind_price_eur_per_mwh: float = 75.0

    ppa_price_escalation_per_year: float = 0.0

    # Strombezug nach §7 Abs. 3 der 37. BImSchV.
    section7_enabled: bool = False
    section7_include_negative_prices: bool = True
    # CO₂-Preis wahlweise aus der stündlichen Zeitreihe oder als konstanter Eingabewert.
    section7_co2_price_mode: str = "timeseries"
    section7_co2_price_eur_per_t: float = 0.0
    section7_co2_price_escalation_per_year: float = 0.0
    section7_co2_factor: float = 0.36
    section7_min_price_threshold_eur_per_mwh: float = 20.0

    # Strombezug nach §13k EnWG ("Nutzen statt Abregeln").
    section13k_enabled: bool = False
    section13k_price_eur_per_mwh: float = 30.0
    section13k_price_escalation_per_year: float = 0.0

    # Optionaler Spotmarktbezug zur Deckung verbleibender Stromlücken.
    spot_purchase_enabled: bool = False
    spot_purchase_price_limit_enabled: bool = True
    spot_purchase_price_limit_eur_per_mwh: float = 70.0
    spot_price_escalation_per_year: float = 0.0

    # Stromhandel / Überschussverkauf. Der historische Feldname
    # ``spot_sale_enabled`` dient als gemeinsamer Aktivierungsschalter; verkauft
    # werden kann wahlweise am Spotmarkt oder zu einem festen PPA-Verkaufspreis.
    spot_sale_enabled: bool = True
    power_sale_mode: str = "spot"  # "spot" | "ppa"
    ppa_sale_price_eur_per_mwh: float = 0.0
    spot_sale_price_escalation_per_year: float = 0.0

    # Optionaler Mindestpreis für Spotverkäufe. Ist die Funktion deaktiviert,
    # wird jeder positive vermarktbare Überschuss zum stündlichen Marktpreis bewertet.
    spot_sale_price_limit_enabled: bool = False
    spot_sale_min_price_eur_per_mwh: float = 0.0


@dataclass
class ElectricityCostInputs:
    """Stromnebenkosten und Privilegierungen.

    Die variablen Sätze werden in ct/kWh eingegeben. Eine aktive
    Befreiung setzt den jeweiligen Kostenbestandteil auf 0. Der Leistungspreis
    wird separat in €/kW und Monat angegeben und aus der maximalen Leistung
    annualisiert.
    """

    grid_fee_ct_per_kwh: float = 11.0
    electricity_tax_ct_per_kwh: float = 0.5
    concession_fee_ct_per_kwh: float = 1.66
    kwk_levy_ct_per_kwh: float = 0.275
    stromnev19_levy_ct_per_kwh: float = 1.56
    offshore_levy_ct_per_kwh: float = 0.82

    electrolyzer_grid_fee_exempt: bool = True
    electrolyzer_electricity_tax_exempt: bool = True
    electrolyzer_concession_fee_exempt: bool = True
    electrolyzer_kwk_levy_exempt: bool = True
    electrolyzer_stromnev19_levy_exempt: bool = True
    electrolyzer_offshore_levy_exempt: bool = True

    rest_grid_fee_exempt: bool = True
    rest_electricity_tax_exempt: bool = True
    rest_concession_fee_exempt: bool = True
    rest_kwk_levy_exempt: bool = True
    rest_stromnev19_levy_exempt: bool = True
    rest_offshore_levy_exempt: bool = True

    electrolyzer_demand_charge_eur_per_kw_month: float = 2.0
    rest_demand_charge_eur_per_kw_month: float = 2.0
    electrolyzer_demand_charge_exempt: bool = True
    rest_demand_charge_exempt: bool = True


@dataclass
class RevenueInputs:
    # THG-Quote: Preis, anrechenbarer Mobilitätsanteil und Erlösaufteilung.
    thg_enabled: bool = True
    thg_price_eur_per_tco2: float = 200.0
    mobility_share: float = 0.35
    thg_revenue_share: float = 0.75
    h2_thg_intensity_kgco2_per_gj: float = 5.0
    thg_price_escalation_per_year: float = 0.0

    # Nebenprodukte: Erlöse werden nur angesetzt, wenn das zugehörige
    # Sauerstoff- bzw. Abwärmesystem in den CAPEX aktiviert wurde.
    oxygen_price_eur_per_t: float = 50.0
    oxygen_price_escalation_per_year: float = 0.0
    waste_heat_price_eur_per_mwh: float = 40.0
    waste_heat_usable_share: float = 0.75
    waste_heat_price_escalation_per_year: float = 0.0

    # Regelenergie wird nicht stündlich simuliert. Stattdessen wird ein exogen
    # kalkulierter Jahresertrag angesetzt und seine Preisentwicklung über die
    # Projektlaufzeit nominal gemittelt.
    balancing_energy_enabled: bool = False
    balancing_energy_revenue_eur_per_year: float = 0.0
    balancing_energy_escalation_per_year: float = 0.0

    # Sonstige Erlöse: zwei getrennte Jahrespositionen mit jeweils eigener
    # Preisentwicklung und gemeinsamem Aktivierungsschalter.
    other_revenues_enabled: bool = False
    other_revenue_1_eur_per_year: float = 0.0
    other_revenue_1_escalation_per_year: float = 0.0
    other_revenue_2_eur_per_year: float = 0.0
    other_revenue_2_escalation_per_year: float = 0.0

    # Legacy-Feld für ältere gespeicherte Python-Konfigurationen. Es wird aus
    # Kompatibilitätsgründen weiterhin eingelesen, aber nicht mehr im UI angeboten.
    other_revenue_eur_per_year: float = 0.0


@dataclass
class ModelInputs:
    system: SystemInputs
    capex: CapexInputs
    opex: OpexInputs
    power: PowerInputs
    revenue: RevenueInputs
    electricity_costs: ElectricityCostInputs = field(default_factory=ElectricityCostInputs)
    funding: FundingInputs = field(default_factory=FundingInputs)
