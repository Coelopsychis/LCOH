from __future__ import annotations

import numpy as np
import pandas as pd

from core.models import ModelInputs
from core.timeseries import validate_timeseries
from core.constants import KWH_PER_KG_H2
from core.technical import (
    compute_processing_design,
    compute_stack_schedule,
    compute_average_efficiency,
)


def _average_escalation_multiplier(escalation: float, years: int) -> float:
    """Return the average nominal escalation multiplier over the project lifetime."""
    if years <= 0 or escalation == 0:
        return 1.0
    return (((1.0 + escalation) ** years - 1.0) / escalation) / years


def _optional_series(ts: pd.DataFrame, column: str, default: float) -> np.ndarray:
    if column in ts.columns:
        values = ts[column].to_numpy(dtype=float)
        if np.any(~np.isfinite(values)):
            raise ValueError(f"Zeitreihe '{column}' enthält ungültige Werte.")
        return values
    return np.full(len(ts), default, dtype=float)


def _build_dispatch_once(
    inputs: ModelInputs, ts: pd.DataFrame, processing_efficiency: float
) -> pd.DataFrame:
    """Calculate the hourly electricity dispatch.

    Procurement priority is:

    1. Baseload, PV and wind PPAs
    2. §7 Abs. 3 der 37. BImSchV when its price condition is satisfied
    3. §13k EnWG ("Nutzen statt Abregeln") up to the hourly available amount
    4. battery discharge when a battery is enabled
    5. ordinary spot-market procurement up to full system load

    The plant is switched off below its minimum-load threshold. Procured energy
    that is not consumed or stored can be marketed according to the configured
    sales mode. PPA, §7 and §13k energy may charge the battery; discharge occurs
    before ordinary spot procurement. Battery charge/discharge losses are not
    modeled.
    """
    validate_timeseries(ts)

    design = compute_processing_design(inputs, processing_efficiency)
    system_kw = float(design["system_power_kw"])
    ely_kw = float(inputs.system.electrolyzer_power_kw)
    min_load = float(inputs.system.min_load_fraction)
    power = inputs.power
    capex = inputs.capex

    if system_kw <= 0:
        raise ValueError("Systemleistung muss größer als 0 sein.")
    if ely_kw <= 0:
        raise ValueError("Elektrolyseurleistung muss größer als 0 sein.")
    if ely_kw > system_kw:
        raise ValueError("Elektrolyseurleistung darf nicht größer als Systemleistung sein.")

    n = len(ts)
    years = int(inputs.system.project_lifetime_years)

    # Apply the average project-lifetime price escalation directly to the hourly
    # spot series so it affects both procurement cost and dispatch thresholds.
    raw_spot_price = ts["day_ahead_eur_per_mwh"].to_numpy(dtype=float)
    spot_multiplier = _average_escalation_multiplier(
        power.spot_price_escalation_per_year, years
    )
    spot_price = raw_spot_price * spot_multiplier

    co2_series = _optional_series(ts, "co2_eur_per_t", 66.6)
    section13k_available_series = np.maximum(
        _optional_series(ts, "section13k_kwh", 0.0), 0.0
    )

    # §7 eligibility uses the CO₂-based threshold with the configured minimum cap.
    co2_multiplier = _average_escalation_multiplier(
        power.section7_co2_price_escalation_per_year, years
    )
    if power.section7_co2_price_mode == "fixed":
        co2_price = np.full(
            n, power.section7_co2_price_eur_per_t * co2_multiplier, dtype=float
        )
    else:
        co2_price = co2_series * co2_multiplier

    section7_threshold = np.maximum(
        co2_price * power.section7_co2_factor,
        power.section7_min_price_threshold_eur_per_mwh,
    )
    if power.spot_purchase_price_limit_enabled:
        section7_threshold = np.minimum(
            section7_threshold, power.spot_purchase_price_limit_eur_per_mwh
        )

    section7_assessment_price = (
        spot_price
        if power.section7_include_negative_prices
        else np.maximum(spot_price, 0.0)
    )
    section7_eligible = section7_assessment_price <= section7_threshold

    baseload_available_kwh = np.full(
        n, power.baseload_kw if power.baseload_enabled else 0.0, dtype=float
    )
    pv_available_kwh = (
        ts["pv_kwh_per_kw"].to_numpy(dtype=float) * power.ppa_pv_capacity_kw
        if power.ppa_pv_enabled
        else np.zeros(n, dtype=float)
    )
    wind_available_kwh = (
        ts["wind_kwh_per_kw"].to_numpy(dtype=float) * power.ppa_wind_capacity_kw
        if power.ppa_wind_enabled
        else np.zeros(n, dtype=float)
    )
    ppa_available_kwh = baseload_available_kwh + pv_available_kwh + wind_available_kwh

    # Battery capacity is the configured capacity factor times rounded-up installed
    # system power. The entered battery power limits charging; discharge is limited
    # by total installed system power.
    battery_system_power_kw = float(np.ceil(system_kw)) if capex.battery_enabled else 0.0
    battery_capacity_kwh = (
        capex.battery_capacity_factor_kwh_per_kw * battery_system_power_kw
        if capex.battery_enabled
        else 0.0
    )
    battery_input_power_kw = capex.battery_power_kw if capex.battery_enabled else 0.0
    battery_output_power_kw = system_kw if capex.battery_enabled else 0.0
    battery_active = (
        capex.battery_enabled
        and battery_capacity_kwh > 0
        and battery_input_power_kw > 0
    )

    # Arrays common to both dispatch paths.
    section7_purchase_kwh = np.zeros(n, dtype=float)
    section13k_purchase_kwh = np.zeros(n, dtype=float)
    spot_purchase_kwh = np.zeros(n, dtype=float)
    battery_charge_kwh = np.zeros(n, dtype=float)
    battery_discharge_kwh = np.zeros(n, dtype=float)
    battery_soc_kwh = np.zeros(n, dtype=float)

    if not battery_active:
        # Without storage, procurement follows PPA → §7 → §13k → spot.
        missing_after_ppa = np.maximum(system_kw - ppa_available_kwh, 0.0)
        if power.section7_enabled:
            section7_purchase_kwh = np.where(
                section7_eligible, missing_after_ppa, 0.0
            )

        after_section7 = ppa_available_kwh + section7_purchase_kwh
        missing_after_section7 = np.maximum(system_kw - after_section7, 0.0)
        if power.section13k_enabled:
            section13k_purchase_kwh = np.minimum(
                section13k_available_series, missing_after_section7
            )

        before_spot = after_section7 + section13k_purchase_kwh
        missing_to_full_load = np.maximum(system_kw - before_spot, 0.0)
        if power.spot_purchase_enabled:
            if power.spot_purchase_price_limit_enabled:
                # The maximum spot-purchase price is an exclusive upper bound.
                spot_allowed = spot_price < power.spot_purchase_price_limit_eur_per_mwh
            else:
                spot_allowed = np.ones(n, dtype=bool)
            spot_purchase_kwh = np.where(spot_allowed, missing_to_full_load, 0.0)

        total_procured_kwh = before_spot + spot_purchase_kwh
        utilization_raw = np.clip(total_procured_kwh / system_kw, 0.0, 1.0)
        utilization = np.where(utilization_raw >= min_load, utilization_raw, 0.0)
        system_consumption_kwh = utilization * system_kw

    else:
        # Storage dispatch has no explicit charge/discharge losses. Charging is
        # limited by the configured battery input power, discharge by installed
        # system power, and §7/§13k procurement may also be used to charge storage.
        utilization = np.zeros(n, dtype=float)
        system_consumption_kwh = np.zeros(n, dtype=float)
        soc = 0.0

        for i in range(n):
            ppa = float(ppa_available_kwh[i])
            prev_soc = soc
            prev_soc_fraction = (
                prev_soc / battery_capacity_kwh if battery_capacity_kwh > 0 else 0.0
            )

            # PPA surplus above system demand can directly charge the battery.
            ppa_charge = min(
                battery_input_power_kw, max(ppa - system_kw, 0.0)
            )

            # Ratio used to limit additional §7 procurement for battery charging.
            ppa_ratio_for_battery = min(
                ppa / battery_input_power_kw, 1.0
            ) if battery_input_power_kw > 0 else 0.0

            s7 = 0.0
            if power.section7_enabled and section7_eligible[i]:
                if i == 0:
                    # At the first hour there is no previous state of charge.
                    s7 = min(
                        max((1.0 - ppa_ratio_for_battery) * battery_input_power_kw, 0.0),
                        max(battery_input_power_kw - ppa, 0.0),
                    )
                else:
                    s7 = min(
                        max(battery_input_power_kw - ppa, 0.0),
                        max(system_kw + (battery_capacity_kwh - prev_soc) - ppa, 0.0),
                    )

            after_s7 = ppa + s7
            s7_charge = min(
                max(
                    0.0,
                    (after_s7 - system_kw) if ppa < system_kw else (after_s7 - ppa),
                ),
                battery_input_power_kw,
            )

            s13 = 0.0
            if power.section13k_enabled:
                available_13k = max(float(section13k_available_series[i]), 0.0)
                if i == 0:
                    s13 = min(available_13k, battery_input_power_kw)
                else:
                    s13 = min(
                        available_13k,
                        max(battery_input_power_kw - after_s7, 0.0),
                        max(after_s7 + battery_input_power_kw + battery_capacity_kwh - prev_soc, 0.0),
                        max(system_kw - after_s7 + battery_capacity_kwh - prev_soc, 0.0),
                    )

            before_battery_discharge = after_s7 + s13

            if i == 0:
                s13_charge = max(
                    0.0, 0.0 if s13 == 0.0 else before_battery_discharge - system_kw
                )
            elif prev_soc_fraction >= 1.0:
                s13_charge = 0.0
            else:
                s13_charge = min(
                    max(
                        0.0,
                        0.0 if s13 < 1.0 else before_battery_discharge - system_kw,
                    ),
                    max(battery_capacity_kwh - prev_soc, 0.0),
                )

            # Storage discharges before ordinary spot procurement. If generic spot
            # procurement is disabled, a low-SOC/low-supply situation does not
            # discharge when the resulting supply would remain below minimum load.
            if i == 0:
                discharge = 0.0
            else:
                possible_discharge = min(
                    max(system_kw - before_battery_discharge, 0.0),
                    prev_soc,
                    battery_output_power_kw,
                )
                if power.spot_purchase_enabled:
                    discharge = possible_discharge
                elif (
                    prev_soc < min_load * system_kw
                    and before_battery_discharge < min_load * system_kw
                ):
                    discharge = 0.0
                else:
                    discharge = possible_discharge

            utilization_before_spot = min(
                max((ppa + discharge + s7 + s13) / system_kw, 0.0), 1.0
            )

            spot = 0.0
            if power.spot_purchase_enabled:
                allowed = (
                    not power.spot_purchase_price_limit_enabled
                    or spot_price[i] < power.spot_purchase_price_limit_eur_per_mwh
                )
                if allowed:
                    spot = max((1.0 - utilization_before_spot) * system_kw, 0.0)

            final_utilization_raw = min(
                max((ppa + discharge + s7 + s13 + spot) / system_kw, 0.0), 1.0
            )
            demand = (
                system_kw * final_utilization_raw
                if final_utilization_raw >= min_load
                else 0.0
            )

            # Total storage charging includes PPA, §7 and §13k charging. In the
            # low-load/negative-price branch, available PPA energy is stored even
            # while the process itself remains switched off.
            if i == 0:
                charge = (
                    ppa + ppa_charge + s7_charge + s13_charge
                    if demand == 0.0
                    else ppa_charge + s7_charge + s13_charge
                )
            elif (
                final_utilization_raw < min_load
                and section7_assessment_price[i] < 0.0
            ):
                charge = ppa
            else:
                # The charging rule is intentionally asymmetric when process demand
                # is zero: total PPA plus dedicated charging flows are used only
                # for the free-capacity comparison; otherwise the accepted charge
                # is limited to the dedicated charging flows and input-power headroom.
                normal_charge = min(
                    battery_input_power_kw - system_kw,
                    ppa_charge + s7_charge + s13_charge,
                )
                comparison_charge = (
                    ppa + ppa_charge + s7_charge + s13_charge
                    if demand == 0.0
                    else normal_charge
                )
                free_capacity = battery_capacity_kwh - prev_soc
                charge = free_capacity if comparison_charge > free_capacity else normal_charge

            charge = max(min(charge, battery_capacity_kwh - prev_soc), 0.0)
            soc = min(max(prev_soc + charge - discharge, 0.0), battery_capacity_kwh)

            section7_purchase_kwh[i] = s7
            section13k_purchase_kwh[i] = s13
            spot_purchase_kwh[i] = spot
            battery_discharge_kwh[i] = discharge
            battery_charge_kwh[i] = charge
            battery_soc_kwh[i] = soc
            utilization[i] = final_utilization_raw if demand > 0.0 else 0.0
            system_consumption_kwh[i] = demand

        total_procured_kwh = (
            ppa_available_kwh
            + section7_purchase_kwh
            + section13k_purchase_kwh
            + spot_purchase_kwh
        )

    # Allocate the actual system consumption by source for reporting. Contracted
    # PPA quantities remain cost-relevant even when not used.
    remaining_demand = system_consumption_kwh.copy()
    baseload_used_kwh = np.minimum(baseload_available_kwh, remaining_demand)
    remaining_demand -= baseload_used_kwh
    pv_used_kwh = np.minimum(pv_available_kwh, remaining_demand)
    remaining_demand -= pv_used_kwh
    wind_used_kwh = np.minimum(wind_available_kwh, remaining_demand)
    remaining_demand -= wind_used_kwh
    section7_used_kwh = np.minimum(section7_purchase_kwh, remaining_demand)
    remaining_demand -= section7_used_kwh
    section13k_used_kwh = np.minimum(section13k_purchase_kwh, remaining_demand)
    remaining_demand -= section13k_used_kwh
    battery_used_kwh = np.minimum(battery_discharge_kwh, remaining_demand)
    remaining_demand -= battery_used_kwh
    spot_used_kwh = np.minimum(spot_purchase_kwh, remaining_demand)

    ppa_used_kwh = baseload_used_kwh + pv_used_kwh + wind_used_kwh

    # Marketable surplus is total procurement minus process consumption and
    # battery charging, so surplus from every enabled procurement route can be sold.
    gross_surplus_kwh = np.maximum(
        total_procured_kwh - system_consumption_kwh - battery_charge_kwh, 0.0
    )

    # Surplus electricity is sold either on the spot market or at the configured
    # PPA sale price. In PPA mode the entire remaining surplus is sold.
    spot_sale_kwh = np.zeros(n, dtype=float)
    ppa_sale_kwh = np.zeros(n, dtype=float)
    if power.spot_sale_enabled:
        if power.power_sale_mode == "ppa":
            ppa_sale_kwh = gross_surplus_kwh.copy()
        else:
            if power.spot_sale_price_limit_enabled:
                spot_sale_allowed = spot_price >= power.spot_sale_min_price_eur_per_mwh
            else:
                spot_sale_allowed = np.ones(n, dtype=bool)
            spot_sale_kwh = np.where(spot_sale_allowed, gross_surplus_kwh, 0.0)
        power_sale_kwh = spot_sale_kwh + ppa_sale_kwh
        curtailed_kwh = gross_surplus_kwh - power_sale_kwh
    else:
        power_sale_kwh = np.zeros(n, dtype=float)
        curtailed_kwh = gross_surplus_kwh

    ely_consumption_kwh = (
        system_consumption_kwh * design["electrolyzer_power_share"]
    )
    peripheral_consumption_kwh = (
        system_consumption_kwh * design["peripheral_power_share"]
    )
    h2_compressor_consumption_kwh = (
        system_consumption_kwh * design["h2_compressor_power_share"]
    )
    oxygen_compressor_consumption_kwh = (
        system_consumption_kwh * design["oxygen_compressor_power_share"]
    )
    rest_consumption_kwh = (
        peripheral_consumption_kwh
        + h2_compressor_consumption_kwh
        + oxygen_compressor_consumption_kwh
    )

    # Procurement costs: PPA and §13k escalation is applied later as an average
    # project-lifetime multiplier; spot and §7 use the already escalated hourly
    # market-price series from the dispatch calculation.
    baseload_cost_eur = baseload_available_kwh * power.baseload_price_eur_per_mwh / 1000.0
    pv_ppa_cost_eur = pv_available_kwh * power.ppa_pv_price_eur_per_mwh / 1000.0
    wind_ppa_cost_eur = wind_available_kwh * power.ppa_wind_price_eur_per_mwh / 1000.0
    section7_cost_eur = section7_purchase_kwh * section7_assessment_price / 1000.0
    section13k_cost_eur = (
        section13k_purchase_kwh * power.section13k_price_eur_per_mwh / 1000.0
    )
    spot_purchase_cost_eur = spot_purchase_kwh * spot_price / 1000.0
    # Spot-sale revenue is floored at zero when the hourly market price is negative.
    spot_sale_revenue_eur = spot_sale_kwh * np.maximum(spot_price, 0.0) / 1000.0

    procurement_cost_eur = (
        baseload_cost_eur
        + pv_ppa_cost_eur
        + wind_ppa_cost_eur
        + section7_cost_eur
        + section13k_cost_eur
        + spot_purchase_cost_eur
    )

    result = ts.copy()
    result["spot_price_effective_eur_per_mwh"] = spot_price
    result["section7_co2_price_effective_eur_per_t"] = co2_price
    result["section7_threshold_eur_per_mwh"] = section7_threshold
    result["section7_eligible"] = section7_eligible
    result["section13k_available_kwh"] = section13k_available_series

    result["baseload_available_kwh"] = baseload_available_kwh
    result["pv_available_kwh"] = pv_available_kwh
    result["wind_available_kwh"] = wind_available_kwh
    result["ppa_available_kwh"] = ppa_available_kwh
    result["baseload_used_kwh"] = baseload_used_kwh
    result["pv_used_kwh"] = pv_used_kwh
    result["wind_used_kwh"] = wind_used_kwh
    result["ppa_used_kwh"] = ppa_used_kwh
    result["section7_purchase_kwh"] = section7_purchase_kwh
    result["section7_used_kwh"] = section7_used_kwh
    result["section13k_purchase_kwh"] = section13k_purchase_kwh
    result["section13k_used_kwh"] = section13k_used_kwh
    result["battery_charge_kwh"] = battery_charge_kwh
    result["battery_discharge_kwh"] = battery_discharge_kwh
    result["battery_used_kwh"] = battery_used_kwh
    result["battery_soc_kwh"] = battery_soc_kwh
    result["spot_purchase_kwh"] = spot_purchase_kwh
    result["spot_sale_kwh"] = spot_sale_kwh
    result["ppa_sale_kwh"] = ppa_sale_kwh
    result["power_sale_kwh"] = power_sale_kwh
    result["curtailed_kwh"] = curtailed_kwh
    result["utilization"] = utilization
    result["system_consumption_kwh"] = system_consumption_kwh
    result["ely_consumption_kwh"] = ely_consumption_kwh
    result["peripheral_consumption_kwh"] = peripheral_consumption_kwh
    result["h2_compressor_consumption_kwh"] = h2_compressor_consumption_kwh
    result["oxygen_compressor_consumption_kwh"] = oxygen_compressor_consumption_kwh
    result["rest_consumption_kwh"] = rest_consumption_kwh

    result["baseload_cost_eur"] = baseload_cost_eur
    result["pv_ppa_cost_eur"] = pv_ppa_cost_eur
    result["wind_ppa_cost_eur"] = wind_ppa_cost_eur
    result["section7_cost_eur"] = section7_cost_eur
    result["section13k_cost_eur"] = section13k_cost_eur
    result["spot_purchase_cost_eur"] = spot_purchase_cost_eur
    result["spot_sale_revenue_eur"] = spot_sale_revenue_eur
    result["procurement_cost_eur"] = procurement_cost_eur

    result.attrs["processing_design"] = design.copy()
    result.attrs["battery_capacity_kwh"] = battery_capacity_kwh
    result.attrs["battery_input_power_kw"] = battery_input_power_kw
    result.attrs["battery_output_power_kw"] = battery_output_power_kw
    return result


def build_dispatch(inputs: ModelInputs, ts: pd.DataFrame) -> pd.DataFrame:
    """Build dispatch while solving the efficiency/auxiliary-load coupling.

    Compressor design power depends on average degraded electrolyzer efficiency,
    while stack degradation depends on equivalent full-load hours produced by the
    dispatch. The circular dependency is solved iteratively until the efficiency
    and resulting stack interval converge.
    """
    eta = float(inputs.system.avg_efficiency_h2_per_el)
    dispatch = None
    for _ in range(12):
        dispatch = _build_dispatch_once(inputs, ts, eta)
        full_load_hours = float(dispatch["utilization"].sum())
        schedule = compute_stack_schedule(inputs, full_load_hours)
        new_eta = compute_average_efficiency(inputs, schedule)
        if abs(new_eta - eta) <= 1e-12:
            eta = new_eta
            break
        eta = new_eta

    # Ensure the returned hourly allocations use the final converged efficiency.
    if dispatch is None or abs(
        dispatch.attrs["processing_design"]["processing_efficiency_h2_per_el"] - eta
    ) > 1e-12:
        dispatch = _build_dispatch_once(inputs, ts, eta)

    dispatch.attrs["average_efficiency_h2_per_el"] = eta
    return dispatch


def compute_operation_kpis(
    inputs: ModelInputs,
    dispatch: pd.DataFrame,
    efficiency_override: float | None = None,
) -> dict:
    annual_ely_kwh = float(dispatch["ely_consumption_kwh"].sum())
    annual_system_kwh = float(dispatch["system_consumption_kwh"].sum())
    annual_rest_kwh = float(dispatch["rest_consumption_kwh"].sum())
    annual_peripheral_kwh = float(dispatch["peripheral_consumption_kwh"].sum())
    annual_h2_compressor_kwh = float(dispatch["h2_compressor_consumption_kwh"].sum())
    annual_oxygen_compressor_kwh = float(dispatch["oxygen_compressor_consumption_kwh"].sum())

    efficiency = (
        inputs.system.avg_efficiency_h2_per_el
        if efficiency_override is None
        else float(efficiency_override)
    )
    annual_h2_kwh = annual_ely_kwh * efficiency
    annual_h2_kg = annual_h2_kwh / KWH_PER_KG_H2 if KWH_PER_KG_H2 > 0 else 0.0

    utilization = dispatch["utilization"].to_numpy(dtype=float)
    avg_utilization = float(utilization.mean())
    operating_hours = int(np.sum(utilization > 0.0))
    full_load_hours_count = int(np.sum(np.isclose(utilization, 1.0)))
    partial_load_hours = operating_hours - full_load_hours_count
    equivalent_full_load_hours = float(utilization.sum())

    annual_baseload_available_kwh = float(dispatch["baseload_available_kwh"].sum())
    annual_pv_available_kwh = float(dispatch["pv_available_kwh"].sum())
    annual_wind_available_kwh = float(dispatch["wind_available_kwh"].sum())
    annual_ppa_available_kwh = float(dispatch["ppa_available_kwh"].sum())
    annual_baseload_used_kwh = float(dispatch["baseload_used_kwh"].sum())
    annual_pv_used_kwh = float(dispatch["pv_used_kwh"].sum())
    annual_wind_used_kwh = float(dispatch["wind_used_kwh"].sum())
    annual_ppa_used_kwh = float(dispatch["ppa_used_kwh"].sum())
    annual_section7_kwh = float(dispatch["section7_purchase_kwh"].sum())
    annual_section13k_kwh = float(dispatch["section13k_purchase_kwh"].sum())
    annual_spot_purchase_kwh = float(dispatch["spot_purchase_kwh"].sum())
    annual_spot_sale_kwh = float(dispatch["spot_sale_kwh"].sum())
    annual_ppa_sale_kwh = float(dispatch["ppa_sale_kwh"].sum())
    annual_power_sale_kwh = float(dispatch["power_sale_kwh"].sum())
    annual_curtailed_kwh = float(dispatch["curtailed_kwh"].sum())
    annual_battery_charge_kwh = float(dispatch["battery_charge_kwh"].sum())
    annual_battery_discharge_kwh = float(dispatch["battery_discharge_kwh"].sum())

    annual_baseload_cost_eur = float(dispatch["baseload_cost_eur"].sum())
    annual_pv_ppa_cost_eur = float(dispatch["pv_ppa_cost_eur"].sum())
    annual_wind_ppa_cost_eur = float(dispatch["wind_ppa_cost_eur"].sum())
    annual_section7_cost_eur = float(dispatch["section7_cost_eur"].sum())
    annual_section13k_cost_eur = float(dispatch["section13k_cost_eur"].sum())
    annual_spot_purchase_cost_eur = float(dispatch["spot_purchase_cost_eur"].sum())
    annual_spot_sale_revenue_eur = float(dispatch["spot_sale_revenue_eur"].sum())
    annual_procurement_cost_eur = float(dispatch["procurement_cost_eur"].sum())

    section7_hours = int(np.sum(dispatch["section7_purchase_kwh"].to_numpy() > 1.0))
    section13k_hours = int(np.sum(dispatch["section13k_purchase_kwh"].to_numpy() > 1.0))

    total_procured_kwh = (
        annual_ppa_available_kwh
        + annual_section7_kwh
        + annual_section13k_kwh
        + annual_spot_purchase_kwh
    )
    green_procured_kwh = annual_ppa_available_kwh + annual_section7_kwh + annual_section13k_kwh
    green_hydrogen_share = (
        min(green_procured_kwh / annual_system_kwh, 1.0)
        if annual_system_kwh > 0
        else 0.0
    )

    design = dispatch.attrs.get("processing_design", {})
    installed_system_power_kw = float(
        design.get("system_power_kw", inputs.system.system_power_kw)
    )
    battery_capacity_kwh = float(dispatch.attrs.get("battery_capacity_kwh", 0.0))
    # Report storage turnovers as ceil(total procured annual energy / storage capacity).
    battery_cycles_per_year = (
        int(np.ceil(total_procured_kwh / battery_capacity_kwh))
        if battery_capacity_kwh > 0
        else 0
    )

    return {
        "annual_system_kwh": annual_system_kwh,
        "annual_system_mwh": annual_system_kwh / 1000.0,
        "annual_ely_kwh": annual_ely_kwh,
        "annual_ely_mwh": annual_ely_kwh / 1000.0,
        "annual_rest_kwh": annual_rest_kwh,
        "annual_rest_mwh": annual_rest_kwh / 1000.0,
        "annual_peripheral_kwh": annual_peripheral_kwh,
        "annual_peripheral_mwh": annual_peripheral_kwh / 1000.0,
        "annual_h2_compressor_kwh": annual_h2_compressor_kwh,
        "annual_h2_compressor_mwh": annual_h2_compressor_kwh / 1000.0,
        "annual_oxygen_compressor_kwh": annual_oxygen_compressor_kwh,
        "annual_oxygen_compressor_mwh": annual_oxygen_compressor_kwh / 1000.0,
        "installed_system_power_kw": installed_system_power_kw,
        "h2_compressor_power_kw": float(design.get("h2_compressor_power_kw", 0.0)),
        "oxygen_compressor_power_kw": float(design.get("oxygen_compressor_power_kw", 0.0)),
        "h2_compressor_ideal_kwh_per_t": float(design.get("h2_compressor_ideal_kwh_per_t", 0.0)),
        "h2_compressor_real_kwh_per_t": float(design.get("h2_compressor_real_kwh_per_t", 0.0)),
        "oxygen_compressor_ideal_kwh_per_t": float(design.get("oxygen_compressor_ideal_kwh_per_t", 0.0)),
        "oxygen_compressor_real_kwh_per_t": float(design.get("oxygen_compressor_real_kwh_per_t", 0.0)),
        "annual_h2_kwh": annual_h2_kwh,
        "annual_h2_kg": annual_h2_kg,
        "average_efficiency_h2_per_el": efficiency,
        "avg_utilization": avg_utilization,
        "operating_hours": operating_hours,
        "full_load_hours_count": full_load_hours_count,
        "partial_load_hours": partial_load_hours,
        "equivalent_full_load_hours": equivalent_full_load_hours,
        "annual_baseload_available_kwh": annual_baseload_available_kwh,
        "annual_pv_available_kwh": annual_pv_available_kwh,
        "annual_wind_available_kwh": annual_wind_available_kwh,
        "annual_ppa_available_kwh": annual_ppa_available_kwh,
        "annual_baseload_used_kwh": annual_baseload_used_kwh,
        "annual_pv_used_kwh": annual_pv_used_kwh,
        "annual_wind_used_kwh": annual_wind_used_kwh,
        "annual_ppa_used_kwh": annual_ppa_used_kwh,
        "annual_section7_kwh": annual_section7_kwh,
        "annual_section13k_kwh": annual_section13k_kwh,
        "section7_hours": section7_hours,
        "section13k_hours": section13k_hours,
        "annual_battery_charge_kwh": annual_battery_charge_kwh,
        "annual_battery_discharge_kwh": annual_battery_discharge_kwh,
        "battery_capacity_kwh": battery_capacity_kwh,
        "battery_cycles_per_year": battery_cycles_per_year,
        "annual_spot_purchase_kwh": annual_spot_purchase_kwh,
        "annual_spot_sale_kwh": annual_spot_sale_kwh,
        "annual_ppa_sale_kwh": annual_ppa_sale_kwh,
        "annual_power_sale_kwh": annual_power_sale_kwh,
        "annual_curtailed_kwh": annual_curtailed_kwh,
        "annual_baseload_cost_eur": annual_baseload_cost_eur,
        "annual_pv_ppa_cost_eur": annual_pv_ppa_cost_eur,
        "annual_wind_ppa_cost_eur": annual_wind_ppa_cost_eur,
        "annual_section7_cost_eur": annual_section7_cost_eur,
        "annual_section13k_cost_eur": annual_section13k_cost_eur,
        "annual_spot_purchase_cost_eur": annual_spot_purchase_cost_eur,
        "annual_spot_sale_revenue_eur": annual_spot_sale_revenue_eur,
        "annual_procurement_cost_eur": annual_procurement_cost_eur,
        "annual_ppa_kwh": annual_ppa_available_kwh,
        "annual_spot_kwh": annual_spot_purchase_kwh,
        "annual_spot_cost_eur": annual_spot_purchase_cost_eur,
        "annual_total_procured_kwh": total_procured_kwh,
        "green_hydrogen_share": green_hydrogen_share,
    }
