from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .inputs import ScalarInputs
from .timeseries import HourlySeries


@dataclass(frozen=True)
class DispatchResult:
    """
    Core hourly outputs we need to reproduce the Excel KPIs.

    Units:
      - system_consumption_kwh: total system electricity consumption each hour (AN in Excel, kWh/h)
      - ely_consumption_kwh: electrolyzer electricity consumption each hour (AT in Excel, kWh/h)
      - utilization: AU in Excel (0..1)
      - supply_ppa_kwh: PPA supply used (kWh/h)
      - supply_spot_kwh: Spot supply used (kWh/h)
    """
    system_consumption_kwh: np.ndarray
    ely_consumption_kwh: np.ndarray
    utilization: np.ndarray
    supply_ppa_kwh: np.ndarray
    supply_spot_kwh: np.ndarray


def run_dispatch_skeleton(inputs: ScalarInputs, ts: HourlySeries) -> DispatchResult:
    """
    Minimal first-pass dispatch (NOT Excel-identical yet):

    1) Available supply from PPAs (baseload + PPA1 + PPA2).
    2) Determine provisional utilization from PPA supply.
    3) If spot enabled and price < threshold, fill remaining to 100% from spot.
    4) Apply minimum load rule: if utilization < min_load => OFF (0).
    5) Convert utilization to consumption (kWh/h) assuming 1h time step: P = system_kW * u
    6) Ely consumption = system_consumption * (ely_kW / system_kW)

    This is a safe skeleton that lets you test time-series wiring and KPI computation.
    """
    system_kW = inputs.system_kW_override if inputs.system_kW_override else inputs.ely_kW
    if system_kW <= 0:
        raise ValueError("system_kW must be > 0")

    # Available PPA supplies in kWh per hour
    baseload_kwh = inputs.baseload_kW if inputs.baseload_enabled else 0.0
    ppa1_kwh = (ts.pv1_kwh_per_kw * inputs.ppa1_kW) if inputs.ppa1_enabled else 0.0
    ppa2_kwh = (ts.wind2_kwh_per_kw * inputs.ppa2_kW) if inputs.ppa2_enabled else 0.0

    supply_ppa = baseload_kwh + ppa1_kwh + ppa2_kwh

    # Utilization from PPA only
    u = np.clip(supply_ppa / system_kW, 0.0, 1.0)

    # Spot fill
    spot_ok = inputs.spot_enabled & (ts.day_ahead_eur_per_mwh < inputs.spot_price_threshold_eur_per_mwh)
    missing_kwh = (1.0 - u) * system_kW
    supply_spot = np.where(spot_ok, missing_kwh, 0.0)

    # Total utilization after spot fill (still clipped)
    u2 = np.clip((supply_ppa + supply_spot) / system_kW, 0.0, 1.0)

    # Minimum load: if below threshold -> OFF
    u_final = np.where(u2 >= inputs.system_min_load, u2, 0.0)

    # Consumption (kWh/h)
    system_consumption = system_kW * u_final
    ely_share = inputs.ely_kW / system_kW
    ely_consumption = system_consumption * ely_share

    return DispatchResult(
        system_consumption_kwh=system_consumption,
        ely_consumption_kwh=ely_consumption,
        utilization=u_final,
        supply_ppa_kwh=supply_ppa,
        supply_spot_kwh=supply_spot,
    )