from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ScalarInputs:
    """
    Minimal set of scalar inputs used by the initial dispatch skeleton.

    NOTE: In the Excel model, many more inputs exist. We start small and
    add as we implement §7 / §13k / battery / cost blocks.
    """
    commissioning_year: int
    ely_kW: float
    system_min_load: float  # 0..1 (AU threshold)
    # Optional auxiliary/system sizing; in Excel system_kW includes BoP etc.
    # For the skeleton we approximate system_kW as ely_kW unless overridden.
    system_kW_override: Optional[float] = None

    # Spot market logic (Excel: threshold in Blatt 2 C76; day-ahead in Blatt 8)
    spot_enabled: bool = True
    spot_price_threshold_eur_per_mwh: float = 0.0

    # PPAs
    ppa1_enabled: bool = True
    ppa2_enabled: bool = True
    ppa1_kW: float = 0.0
    ppa2_kW: float = 0.0
    baseload_enabled: bool = False
    baseload_kW: float = 0.0  # constant hourly supply (kWh/h == kW)

    # Efficiency handling (Excel phase-1: scalar avg efficiency incl. degradation)
    avg_efficiency: float = 0.7  # F12 in Excel


@dataclass(frozen=True)
class TimeSeriesInputs:
    """
    Hourly time series for one year (8760 values each, non-leap year).
    Units:
      - pv1_kwh_per_kw, wind2_kwh_per_kw: kWh per installed kW for that hour (i.e. capacity factor * 1h)
      - day_ahead_eur_per_mwh: market price in EUR/MWh
    """
    pv1_kwh_per_kw: "list[float]"
    wind2_kwh_per_kw: "list[float]"
    day_ahead_eur_per_mwh: "list[float]"