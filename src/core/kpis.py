from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .inputs import ScalarInputs
from .dispatch import DispatchResult


@dataclass(frozen=True)
class CoreKPIs:
    """
    Mirrors the Excel KPIs in Sheet2 F7..F16 as far as possible
    with the information available in the skeleton.

    Note:
      - LCOH (F3/F4) needs cost blocks; not implemented in the skeleton.
    """
    # “AA4” in Excel Sheet4: yearly Ely electricity consumption
    ely_electricity_year_kwh: float  # AA4-like

    # Excel F7..F16 equivalents
    h2_energy_year_kwh: float  # F7
    h2_mass_year_kg: float     # F8 (requires factor)
    utilization_avg: float     # F11 (mean AU)
    eq_full_load_hours: float  # F13 = 8760*mean(AU)
    operating_hours: int       # F14 count(AU>0)
    full_load_hours: int       # F15 count(AU==1)
    partial_load_hours: int    # F16

    # Helpful debug aggregates
    ppa_energy_year_kwh: float
    spot_energy_year_kwh: float


def compute_kpis(
    inputs: ScalarInputs,
    dispatch: DispatchResult,
    kwh_per_kg_h2: float,
) -> CoreKPIs:
    """
    kwh_per_kg_h2 corresponds to Excel '3. Nebenrechnungen'!C6 (energy per kg).
    In Excel: F8 = F7 / C6, so C6 is kWh/kg_H2.
    """
    au = dispatch.utilization
    ely_year_kwh = float(np.sum(dispatch.ely_consumption_kwh))

    # Excel style: F7 = AA4 * avg_efficiency (assuming AA4 is Ely consumption)
    h2_energy_kwh = ely_year_kwh * inputs.avg_efficiency
    h2_mass_kg = 0.0 if kwh_per_kg_h2 == 0 else (h2_energy_kwh / kwh_per_kg_h2)

    u_avg = float(np.mean(au))
    op_hours = int(np.sum(au > 0.0))
    fl_hours = int(np.sum(au == 1.0))
    pl_hours = op_hours - fl_hours

    return CoreKPIs(
        ely_electricity_year_kwh=ely_year_kwh,
        h2_energy_year_kwh=h2_energy_kwh,
        h2_mass_year_kg=h2_mass_kg,
        utilization_avg=u_avg,
        eq_full_load_hours=8760.0 * u_avg,
        operating_hours=op_hours,
        full_load_hours=fl_hours,
        partial_load_hours=pl_hours,
        ppa_energy_year_kwh=float(np.sum(dispatch.supply_ppa_kwh)),
        spot_energy_year_kwh=float(np.sum(dispatch.supply_spot_kwh)),
    )