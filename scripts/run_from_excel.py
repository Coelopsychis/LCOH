from __future__ import annotations

import math

from core.excel_io import load_case_from_excel, load_kwh_per_kg_factor
from core.dispatch import run_dispatch_skeleton
from core.kpis import compute_kpis


def main() -> None:
    # Change this to your local path, or call with an argument later.
    path = "Berechnungstool_Modell_Rev_6.xlsx"

    case = load_case_from_excel(path)
    kwh_per_kg = load_kwh_per_kg_factor(path)

    dispatch = run_dispatch_skeleton(case.scalars, case.ts)
    kpis = compute_kpis(case.scalars, dispatch, kwh_per_kg_h2=kwh_per_kg)

    print("\n=== Skeleton Core KPIs (Python) ===")
    print(f"AA4 (Ely kWh/a): {kpis.ely_electricity_year_kwh:,.3f}")
    print(f"F7 (H2 kWh/a):   {kpis.h2_energy_year_kwh:,.3f}")
    print(f"F8 (H2 kg/a):    {kpis.h2_mass_year_kg:,.3f}")
    print(f"F11 (avg AU):    {kpis.utilization_avg:.6f}")
    print(f"F13 (eq FLh):    {kpis.eq_full_load_hours:,.3f}")
    print(f"F14 (op h):      {kpis.operating_hours}")
    print(f"F15 (FL h):      {kpis.full_load_hours}")
    print(f"F16 (PL h):      {kpis.partial_load_hours}")

    print("\n=== Excel references (cached values) ===")
    for addr in ["F7", "F8", "F11", "F13", "F14", "F15", "F16"]:
        print(f"{addr}: {case.ref_sheet2.get(addr)}")

    print("\nNOTE: Differences are expected at this stage (skeleton dispatch only).")


if __name__ == "__main__":
    main()