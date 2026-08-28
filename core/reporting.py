from __future__ import annotations

import pandas as pd


def lcoh_bridge(results: dict) -> pd.DataFrame:
    """Annual cost/revenue bridge whose sum equals annual LCOH numerator."""
    rows = [
        ("Finanzierung (FK + EK)", float(results["financing_eur_per_year"]), "Kosten"),
        ("Stackersatz", float(results["stack_replacement_eur_per_year"]), "Kosten"),
        ("OPEX", float(results["total_opex_eur_per_year"]), "Kosten"),
        ("Stromkosten brutto", float(results["annual_power_cost_gross_eur"]), "Kosten"),
        ("Strompreisförderung", -float(results["electricity_subsidy_eur_per_year"]), "Förderung"),
        ("Strompreiskompensation", -float(results["spk_revenue_eur_per_year"]), "Förderung"),
        ("Stromverkauf", -float(results["power_sale_revenue_eur_per_year"]), "Erlös"),
        ("THG-Quote", -float(results["thg_revenue_eur_per_year"]), "Erlös"),
        ("Sauerstoff", -float(results["oxygen_revenue_eur_per_year"]), "Erlös"),
        ("Abwärme", -float(results["waste_heat_revenue_eur_per_year"]), "Erlös"),
        ("Regelenergie", -float(results["balancing_energy_revenue_eur_per_year"]), "Erlös"),
        ("Sonstige Erlöse", -float(results["other_revenue_eur_per_year"]), "Erlös"),
    ]
    df = pd.DataFrame(rows, columns=["Komponente", "€/a", "Typ"])
    annual_h2 = float(results["annual_h2_kg"])
    df["€/kg H₂"] = df["€/a"] / annual_h2 if annual_h2 > 0 else float("nan")
    return df


def positive_cost_distribution(results: dict) -> pd.DataFrame:
    rows = [
        ("Finanzierung", float(results["financing_eur_per_year"])),
        ("Stackersatz", float(results["stack_replacement_eur_per_year"])),
        ("OPEX", float(results["total_opex_eur_per_year"])),
        ("Strombeschaffung", float(results["annual_procurement_cost_eur"])),
        ("Stromnebenkosten", float(results["annual_power_addons_eur"])),
    ]
    return pd.DataFrame(rows, columns=["Komponente", "€/a"])


def revenue_distribution(results: dict) -> pd.DataFrame:
    rows = [
        ("Strompreisförderung", float(results["electricity_subsidy_eur_per_year"])),
        ("Strompreiskompensation", float(results["spk_revenue_eur_per_year"])),
        ("Stromverkauf", float(results["power_sale_revenue_eur_per_year"])),
        ("THG-Quote", float(results["thg_revenue_eur_per_year"])),
        ("Sauerstoff", float(results["oxygen_revenue_eur_per_year"])),
        ("Abwärme", float(results["waste_heat_revenue_eur_per_year"])),
        ("Regelenergie", float(results["balancing_energy_revenue_eur_per_year"])),
        ("Sonstige", float(results["other_revenue_eur_per_year"])),
    ]
    df = pd.DataFrame(rows, columns=["Komponente", "€/a"])
    return df[df["€/a"] > 0].reset_index(drop=True)
