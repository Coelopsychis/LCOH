from __future__ import annotations

import numpy as np
import pandas as pd

from core.models import ModelInputs
from core.timeseries import validate_timeseries
from core.constants import KWH_PER_KG_H2


def build_dispatch(inputs: ModelInputs, ts: pd.DataFrame) -> pd.DataFrame:
    """
    Einfache Basis-Dispatch-Logik:
    - PPA-Energie nutzen
    - optional Spotmarkt bis 100 % Systemauslastung auffüllen
    - Mindestlast beachten
    """
    validate_timeseries(ts)

    system_kw = inputs.system.system_power_kw
    ely_kw = inputs.system.electrolyzer_power_kw
    min_load = inputs.system.min_load_fraction
    power = inputs.power

    baseload_supply = np.full(len(ts), power.baseload_kw if power.baseload_enabled else 0.0)

    pv_supply = (
        ts["pv_kwh_per_kw"].to_numpy() * power.ppa_pv_capacity_kw
        if power.ppa_pv_enabled
        else np.zeros(len(ts))
    )

    wind_supply = (
        ts["wind_kwh_per_kw"].to_numpy() * power.ppa_wind_capacity_kw
        if power.ppa_wind_enabled
        else np.zeros(len(ts))
    )

    ppa_supply = baseload_supply + pv_supply + wind_supply

    utilization_ppa = np.clip(ppa_supply / system_kw, 0.0, 1.0)
    missing_kwh = (1.0 - utilization_ppa) * system_kw

    price = ts["day_ahead_eur_per_mwh"].to_numpy()
    spot_supply = np.where(
        (power.spot_enabled) & (price < power.spot_price_limit_eur_per_mwh),
        missing_kwh,
        0.0,
    )

    total_available = ppa_supply + spot_supply
    utilization_raw = np.clip(total_available / system_kw, 0.0, 1.0)
    utilization = np.where(utilization_raw >= min_load, utilization_raw, 0.0)

    system_consumption_kwh = utilization * system_kw
    ely_share = ely_kw / system_kw
    ely_consumption_kwh = system_consumption_kwh * ely_share

    spot_cost_eur = spot_supply * price / 1000.0

    result = ts.copy()
    result["baseload_supply_kwh"] = baseload_supply
    result["pv_supply_kwh"] = pv_supply
    result["wind_supply_kwh"] = wind_supply
    result["ppa_supply_kwh"] = ppa_supply
    result["spot_supply_kwh"] = spot_supply
    result["utilization"] = utilization
    result["system_consumption_kwh"] = system_consumption_kwh
    result["ely_consumption_kwh"] = ely_consumption_kwh
    result["spot_cost_eur"] = spot_cost_eur

    return result


def compute_operation_kpis(inputs: ModelInputs, dispatch: pd.DataFrame) -> dict:
    annual_ely_kwh = float(dispatch["ely_consumption_kwh"].sum())
    annual_h2_kwh = annual_ely_kwh * inputs.system.avg_efficiency_h2_per_el
    annual_h2_kg = annual_h2_kwh / KWH_PER_KG_H2

    utilization = dispatch["utilization"].to_numpy()
    avg_utilization = float(utilization.mean())
    operating_hours = int(np.sum(utilization > 0.0))
    full_load_hours_count = int(np.sum(utilization == 1.0))
    partial_load_hours = operating_hours - full_load_hours_count
    equivalent_full_load_hours = 8760 * avg_utilization

    return {
        "annual_ely_kwh": annual_ely_kwh,
        "annual_ely_mwh": annual_ely_kwh / 1000.0,
        "annual_h2_kwh": annual_h2_kwh,
        "annual_h2_kg": annual_h2_kg,
        "avg_utilization": avg_utilization,
        "operating_hours": operating_hours,
        "full_load_hours_count": full_load_hours_count,
        "partial_load_hours": partial_load_hours,
        "equivalent_full_load_hours": equivalent_full_load_hours,
        "annual_spot_cost_eur": float(dispatch["spot_cost_eur"].sum()),
        "annual_ppa_kwh": float(dispatch["ppa_supply_kwh"].sum()),
        "annual_spot_kwh": float(dispatch["spot_supply_kwh"].sum()),
    }