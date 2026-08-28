from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.finance import compute_financing, compute_stack_replacement
from core.models import ModelInputs


@dataclass(frozen=True)
class SensitivityParameter:
    key: str
    label: str
    description: str


EXCEL_SENSITIVITY_PARAMETERS = (
    SensitivityParameter(
        "thg_quote",
        "THG-Quote",
        "Skaliert den jährlichen THG-Quotenerlös proportional zum gewählten Änderungsfaktor.",
    ),
    SensitivityParameter(
        "interest",
        "Zinsen (FK + EK)",
        "Skaliert Fremd-, Eigenkapital- und Stack-Finanzierungszins gemeinsam.",
    ),
    SensitivityParameter(
        "opex",
        "OPEX",
        "Skaliert die gesamten jährlichen OPEX; die übrigen Größen bleiben unverändert.",
    ),
    SensitivityParameter(
        "project_lifetime",
        "Projektlaufzeit",
        "Verändert die Projektlaufzeit und berechnet Finanzierung sowie Stacktausch für diese Laufzeit neu.",
    ),
    SensitivityParameter(
        "capex",
        "CAPEX",
        "Skaliert die finanzierte Gesamtinvestition; OPEX und Stackkosten bleiben bei dieser Sensitivität unverändert.",
    ),
    SensitivityParameter(
        "full_load_hours",
        "Volllaststunden",
        "Skaliert Produktion, energieabhängige Kosten/Erlöse und Stackbeanspruchung proportional.",
    ),
    SensitivityParameter(
        "electricity_price",
        "Strompreis",
        "Skaliert die Stromkosten nach Strompreisförderung sowie die Strompreiskompensation.",
    ),
)

PARAMETER_BY_KEY = {p.key: p for p in EXCEL_SENSITIVITY_PARAMETERS}

# Central defaults used by both the Streamlit widgets and the calculation
# helpers. Keeping them here prevents UI/calculation drift.
DEFAULT_SENSITIVITY_RANGE = 0.30
DEFAULT_SENSITIVITY_RANGE_PERCENT = 30
DEFAULT_SENSITIVITY_POINTS = 13
DEFAULT_SENSITIVITY_PARAMETER = "electricity_price"


def _safe_factor(relative_change: float) -> float:
    # Negative prices/rates created solely by a sensitivity factor are not
    # meaningful for this UI. Excel normally uses only +/-30 %, so this mainly
    # protects custom ranges entered in Streamlit.
    return max(1.0 + float(relative_change), 0.0)


def _annual_cost_from_components(
    base: dict,
    *,
    financing: float | None = None,
    stack: float | None = None,
    opex: float | None = None,
    power_after_subsidy: float | None = None,
    spk: float | None = None,
    other_revenues: float | None = None,
) -> float:
    return (
        (base["financing_eur_per_year"] if financing is None else financing)
        + (base["stack_replacement_eur_per_year"] if stack is None else stack)
        + (base["total_opex_eur_per_year"] if opex is None else opex)
        + (
            base["annual_power_cost_after_subsidy_eur"]
            if power_after_subsidy is None
            else power_after_subsidy
        )
        - (base["spk_revenue_eur_per_year"] if spk is None else spk)
        - (
            base["total_other_revenues_eur_per_year"]
            if other_revenues is None
            else other_revenues
        )
    )


def compute_excel_sensitivity_lcoh(
    inputs: ModelInputs,
    base_results: dict,
    parameter_key: str,
    relative_change: float,
) -> float:
    """Return the LCOH for one point of the defined sensitivity methodology.

    The sensitivity analysis changes only the cost, revenue or operating
    component assigned to the selected parameter. This is intentionally not
    always identical to changing a raw model input and recalculating the full
    plant model; for example, CAPEX sensitivity changes financing but leaves
    CAPEX-linked OPEX and stack replacement at their base values.
    """
    if parameter_key not in PARAMETER_BY_KEY:
        raise KeyError(f"Unbekannter Sensitivitätsparameter: {parameter_key}")

    factor = _safe_factor(relative_change)
    h2 = float(base_results["annual_h2_kg"])
    if h2 <= 0:
        return np.nan

    if parameter_key == "thg_quote":
        base_thg = float(base_results["thg_revenue_eur_per_year"])
        other = float(base_results["total_other_revenues_eur_per_year"])
        annual = _annual_cost_from_components(
            base_results,
            other_revenues=other + base_thg * (factor - 1.0),
        )
        return annual / h2

    if parameter_key == "opex":
        annual = _annual_cost_from_components(
            base_results,
            opex=float(base_results["total_opex_eur_per_year"]) * factor,
        )
        return annual / h2

    if parameter_key == "capex":
        # All debt/equity annuities are linear in the financed capital for fixed
        # rates and lifetime, so scaling the financing term exactly reproduces
        # the workbook's CAPEX sensitivity.
        annual = _annual_cost_from_components(
            base_results,
            financing=float(base_results["financing_eur_per_year"]) * factor,
        )
        return annual / h2

    if parameter_key == "electricity_price":
        annual = _annual_cost_from_components(
            base_results,
            power_after_subsidy=float(base_results["annual_power_cost_after_subsidy_eur"])
            * factor,
            spk=float(base_results["spk_revenue_eur_per_year"]) * factor,
        )
        return annual / h2

    if parameter_key == "interest":
        varied = deepcopy(inputs)
        varied.capex.debt_interest_rate *= factor
        varied.capex.equity_interest_rate *= factor
        varied.capex.stack_financing_interest_rate *= factor
        financing = compute_financing(
            varied, {"total_capex_eur": float(base_results["total_capex_eur"])}
        )["financing_eur_per_year"]
        stack = compute_stack_replacement(
            varied, float(base_results["equivalent_full_load_hours"])
        )["stack_replacement_eur_per_year"]
        annual = _annual_cost_from_components(
            base_results, financing=financing, stack=stack
        )
        return annual / h2

    if parameter_key == "project_lifetime":
        varied = deepcopy(inputs)
        varied.system.project_lifetime_years = max(
            1, int(round(inputs.system.project_lifetime_years * factor))
        )
        financing = compute_financing(
            varied, {"total_capex_eur": float(base_results["total_capex_eur"])}
        )["financing_eur_per_year"]
        stack = compute_stack_replacement(
            varied, float(base_results["equivalent_full_load_hours"])
        )["stack_replacement_eur_per_year"]
        annual = _annual_cost_from_components(
            base_results, financing=financing, stack=stack
        )
        return annual / h2

    if parameter_key == "full_load_hours":
        base_flh = float(base_results["equivalent_full_load_hours"])
        if base_flh <= 0:
            return np.nan
        varied_flh = min(max(base_flh * factor, 0.0), 8760.0)
        effective_factor = varied_flh / base_flh

        stack = compute_stack_replacement(
            inputs, varied_flh
        )["stack_replacement_eur_per_year"]

        # Excel scales these energy/production-linked revenues with FLH. Fixed
        # balancing/miscellaneous revenues remain unchanged.
        linked_revenues = (
            float(base_results["thg_revenue_eur_per_year"])
            + float(base_results["power_sale_revenue_eur_per_year"])
            + float(base_results["oxygen_revenue_eur_per_year"])
            + float(base_results["waste_heat_revenue_eur_per_year"])
        )
        fixed_revenues = (
            float(base_results["balancing_energy_revenue_eur_per_year"])
            + float(base_results["other_revenue_eur_per_year"])
        )
        annual = _annual_cost_from_components(
            base_results,
            stack=stack,
            power_after_subsidy=float(base_results["annual_power_cost_after_subsidy_eur"])
            * effective_factor,
            spk=float(base_results["spk_revenue_eur_per_year"]) * effective_factor,
            other_revenues=linked_revenues * effective_factor + fixed_revenues,
        )
        varied_h2 = h2 * effective_factor
        return annual / varied_h2 if varied_h2 > 0 else np.nan

    raise AssertionError("Nicht erreichbarer Sensitivitätszweig")


def compute_tornado(
    inputs: ModelInputs,
    base_results: dict,
    relative_range: float = DEFAULT_SENSITIVITY_RANGE,
) -> pd.DataFrame:
    base_lcoh = float(base_results["lcoh_eur_per_kg"])
    rows = []
    for parameter in EXCEL_SENSITIVITY_PARAMETERS:
        minus = compute_excel_sensitivity_lcoh(
            inputs, base_results, parameter.key, -relative_range
        )
        plus = compute_excel_sensitivity_lcoh(
            inputs, base_results, parameter.key, relative_range
        )
        rows.append(
            {
                "key": parameter.key,
                "Parameter": parameter.label,
                "LCOH_minus": minus,
                "LCOH_basis": base_lcoh,
                "LCOH_plus": plus,
                "Delta_minus": minus - base_lcoh,
                "Delta_plus": plus - base_lcoh,
                "Spannweite": abs(plus - minus),
            }
        )
    return pd.DataFrame(rows).sort_values("Spannweite", ascending=True).reset_index(drop=True)


def compute_sensitivity_curve(
    inputs: ModelInputs,
    base_results: dict,
    parameter_key: str,
    relative_range: float = DEFAULT_SENSITIVITY_RANGE,
    points: int = DEFAULT_SENSITIVITY_POINTS,
) -> pd.DataFrame:
    points = max(int(points), 3)
    changes = np.linspace(-relative_range, relative_range, points)
    # Make sure the base case is present even for an even point count.
    if not np.any(np.isclose(changes, 0.0)):
        changes = np.sort(np.append(changes, 0.0))

    values = [
        compute_excel_sensitivity_lcoh(inputs, base_results, parameter_key, change)
        for change in changes
    ]
    base_lcoh = float(base_results["lcoh_eur_per_kg"])
    return pd.DataFrame(
        {
            "Änderung": changes,
            "Änderung [%]": changes * 100.0,
            "LCOH [€/kg]": values,
            "Δ LCOH [€/kg]": np.asarray(values, dtype=float) - base_lcoh,
        }
    )
