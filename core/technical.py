from __future__ import annotations

import math

from core.constants import KWH_PER_KG_H2
from core.models import ModelInputs

JOULE_PER_KWH = 3_600_000.0
KG_PER_TONNE = 1_000.0
O2_KG_PER_KG_H2 = 8.0

# Thermodynamic constants used by the ideal-gas compressor calculation.
H2_ISENTROPIC_EXPONENT = 1.41
H2_SPECIFIC_GAS_CONSTANT_J_PER_KG_K = 4_124.0
O2_ISENTROPIC_EXPONENT = 1.40
O2_SPECIFIC_GAS_CONSTANT_J_PER_KG_K = 259.8


def compressor_specific_work_kwh_per_t(
    inlet_pressure_bar: float,
    outlet_pressure_bar: float,
    inlet_temperature_c: float,
    isentropic_efficiency: float,
    isentropic_exponent: float,
    specific_gas_constant_j_per_kg_k: float,
) -> dict:
    """Calculate ideal and real specific compressor work for an ideal gas.

    The isentropic work is calculated in J/kg, converted to kWh/t and divided by
    the compressor efficiency. The pressure ratio is dimensionless, so inlet and
    outlet pressure may both be provided in bar.
    """
    p_in = float(inlet_pressure_bar)
    p_out = float(outlet_pressure_bar)
    eta = float(isentropic_efficiency)
    temperature_k = float(inlet_temperature_c) + 273.15
    kappa = float(isentropic_exponent)
    gas_constant = float(specific_gas_constant_j_per_kg_k)

    if p_in <= 0 or p_out <= 0:
        raise ValueError("Verdichterdrücke müssen größer als 0 bar sein.")
    if temperature_k <= 0:
        raise ValueError("Verdichtereintrittstemperatur muss über 0 K liegen.")
    if eta <= 0:
        raise ValueError("Verdichterwirkungsgrad muss größer als 0 sein.")
    if kappa <= 1:
        raise ValueError("Isentropenexponent muss größer als 1 sein.")

    # A lower or equal outlet pressure does not require compression; return zero
    # instead of evaluating the compression equation outside its intended range.
    if p_out <= p_in:
        ideal_j_per_kg = 0.0
    else:
        ideal_j_per_kg = (
            (kappa / (kappa - 1.0))
            * gas_constant
            * temperature_k
            * ((p_out / p_in) ** ((kappa - 1.0) / kappa) - 1.0)
        )

    ideal_kwh_per_t = ideal_j_per_kg / JOULE_PER_KWH * KG_PER_TONNE
    real_kwh_per_t = ideal_kwh_per_t / eta

    return {
        "ideal_j_per_kg": ideal_j_per_kg,
        "ideal_kwh_per_t": ideal_kwh_per_t,
        "real_kwh_per_t": real_kwh_per_t,
    }


def compute_processing_design(inputs: ModelInputs, average_efficiency: float) -> dict:
    """Calculate design loads for H₂ and O₂ treatment.

    Compressor design power is derived from H₂ production at 100 % electrolyzer
    load using the average efficiency including degradation. These auxiliary
    loads are added to installed system power and scale linearly with hourly
    system utilization.
    """
    s = inputs.system
    c = inputs.capex
    eta = max(float(average_efficiency), 0.0)
    ely_kw = float(s.electrolyzer_power_kw)
    peripheral_kw = ely_kw * float(s.peripheral_power_fraction)

    h2_work = compressor_specific_work_kwh_per_t(
        c.h2_compressor_inlet_pressure_bar,
        c.h2_compressor_outlet_pressure_bar,
        c.h2_compressor_inlet_temperature_c,
        c.h2_compressor_efficiency,
        H2_ISENTROPIC_EXPONENT,
        H2_SPECIFIC_GAS_CONSTANT_J_PER_KG_K,
    )
    o2_work = compressor_specific_work_kwh_per_t(
        c.oxygen_compressor_inlet_pressure_bar,
        c.oxygen_compressor_outlet_pressure_bar,
        c.oxygen_compressor_inlet_temperature_c,
        c.oxygen_compressor_efficiency,
        O2_ISENTROPIC_EXPONENT,
        O2_SPECIFIC_GAS_CONSTANT_J_PER_KG_K,
    )

    h2_kg_per_h_at_full_load = (
        ely_kw * eta / KWH_PER_KG_H2 if KWH_PER_KG_H2 > 0 else 0.0
    )
    o2_kg_per_h_at_full_load = h2_kg_per_h_at_full_load * O2_KG_PER_KG_H2

    h2_processed_share = max(float(c.h2_processed_share), 0.0)
    h2_compressor_kw = (
        h2_work["real_kwh_per_t"]
        / KG_PER_TONNE
        * h2_kg_per_h_at_full_load
        * h2_processed_share
        if c.compression_enabled
        else 0.0
    )
    o2_compressor_kw = (
        o2_work["real_kwh_per_t"]
        / KG_PER_TONNE
        * o2_kg_per_h_at_full_load
        if c.oxygen_enabled
        else 0.0
    )

    system_kw = ely_kw + peripheral_kw + h2_compressor_kw + o2_compressor_kw
    if system_kw <= 0:
        raise ValueError("Installierte Systemleistung muss größer als 0 sein.")

    return {
        "processing_efficiency_h2_per_el": eta,
        "electrolyzer_power_kw": ely_kw,
        "peripheral_power_kw": peripheral_kw,
        "h2_compressor_power_kw": h2_compressor_kw,
        "oxygen_compressor_power_kw": o2_compressor_kw,
        "system_power_kw": system_kw,
        "electrolyzer_power_share": ely_kw / system_kw,
        "peripheral_power_share": peripheral_kw / system_kw,
        "h2_compressor_power_share": h2_compressor_kw / system_kw,
        "oxygen_compressor_power_share": o2_compressor_kw / system_kw,
        "h2_at_full_load_kg_per_h": h2_kg_per_h_at_full_load,
        "oxygen_at_full_load_kg_per_h": o2_kg_per_h_at_full_load,
        "h2_compressor_ideal_kwh_per_t": h2_work["ideal_kwh_per_t"],
        "h2_compressor_real_kwh_per_t": h2_work["real_kwh_per_t"],
        "oxygen_compressor_ideal_kwh_per_t": o2_work["ideal_kwh_per_t"],
        "oxygen_compressor_real_kwh_per_t": o2_work["real_kwh_per_t"],
    }


def compute_stack_schedule(inputs: ModelInputs, equivalent_full_load_hours: float) -> dict:
    """Technical stack schedule used by both dispatch and finance."""
    s = inputs.system
    lifetime_hours = float(s.stack_lifetime_hours)
    project_years = int(s.project_lifetime_years)
    total_equivalent_hours = float(equivalent_full_load_hours) * project_years

    if lifetime_hours > 0 and total_equivalent_hours > lifetime_hours:
        replacement_count = math.floor(total_equivalent_hours / lifetime_hours)
    else:
        replacement_count = 0

    replacement_interval_years = (
        project_years / (replacement_count + 1) if replacement_count > 0 else 0.0
    )
    return {
        "stack_replacement_count": replacement_count,
        "stack_replacement_interval_years": replacement_interval_years,
    }


def compute_average_efficiency(inputs: ModelInputs, stack: dict) -> float:
    """Return the average electrolyzer efficiency over one effective stack interval.

    With at least one replacement, efficiency is averaged between fresh-stack
    efficiency and the linearly degraded value immediately before replacement.
    Without replacement, the end-of-project degraded efficiency is used.
    """
    s = inputs.system
    eta0 = float(s.avg_efficiency_h2_per_el)
    deg = float(s.degradation_per_year)
    interval = float(stack["stack_replacement_interval_years"])

    if stack["stack_replacement_count"] > 0 and interval > 0:
        eta_before_change = max(eta0 - deg * interval, 0.0)
        return (eta0 + eta_before_change) / 2.0

    return max(eta0 - deg * s.project_lifetime_years, 0.0)
