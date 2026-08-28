from __future__ import annotations

import numpy as np
import pandas as pd
import re
from pathlib import Path


def make_demo_timeseries(seed: int = 7) -> pd.DataFrame:
    """
    Lädt bevorzugt die aus Excel Rev. 8 extrahierte Referenz-Zeitreihe.
    Falls sie nicht vorhanden ist, wird wie bisher ein synthetischer 8760-h-
    Datensatz erzeugt. Dadurch bleibt die App portabel, startet im Patch aber
    mit demselben PV-/Wind-/Preisdatensatz wie das Referenz-Excel.
    """
    reference_path = Path(__file__).resolve().parent.parent / "excel_reference_timeseries.csv"
    if reference_path.exists():
        df = pd.read_csv(reference_path)
        validate_timeseries(df)
        # Optional electricity-module series. Older CSVs remain compatible.
        if "co2_eur_per_t" not in df.columns:
            df["co2_eur_per_t"] = 66.6
        if "section13k_kwh" not in df.columns:
            df["section13k_kwh"] = 0.0
        return df

    rng = np.random.default_rng(seed)
    n = 8760
    hours = np.arange(n)

    season = 0.5 + 0.5 * np.sin(2 * np.pi * (hours / n - 0.2))

    hour_of_day = hours % 24
    pv_daily = np.clip(np.sin(np.pi * (hour_of_day - 6) / 12), 0, None)
    pv_profile = pv_daily * (0.2 + 0.8 * season)

    wind_profile = np.clip(
        0.35 + 0.25 * (1 - season) + 0.15 * rng.normal(size=n),
        0,
        0.95,
    )

    price = 60 + 20 * (1 - season) + 25 * rng.normal(size=n)
    neg_mask = rng.random(n) < 0.02
    price[neg_mask] = -10 - 40 * rng.random(np.sum(neg_mask))
    price = np.clip(price, -80, 250)

    return pd.DataFrame(
        {
            "hour": np.arange(1, n + 1),
            "pv_kwh_per_kw": pv_profile,
            "wind_kwh_per_kw": wind_profile,
            "day_ahead_eur_per_mwh": price,
            "co2_eur_per_t": np.full(n, 66.6),
            "section13k_kwh": np.zeros(n),
        }
    )


def validate_timeseries(df: pd.DataFrame) -> None:
    required = {"pv_kwh_per_kw", "wind_kwh_per_kw", "day_ahead_eur_per_mwh"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Fehlende Spalten: {sorted(missing)}")
    if len(df) != 8760:
        raise ValueError(f"Zeitreihe muss 8760 Zeilen haben, gefunden: {len(df)}")


def parse_timeseries_text(text: str, expected_length: int = 8760) -> np.ndarray:
    """
    Parse a text block containing hourly values.

    Accepted separators:
    - newline
    - semicolon
    - comma
    - tab
    - spaces

    Decimal commas are supported.
    """
    if not text or not text.strip():
        raise ValueError("Keine Zeitreihenwerte eingegeben.")

    normalized = text.strip().replace("\r", "\n")

    # If users paste German decimals with semicolon/newline separators,
    # decimal commas should be converted before tokenizing by semicolon/newline.
    # This parser is robust for one value per line, semicolon lists, or whitespace.
    raw_tokens = re.split(r"[;\n\t ]+", normalized)
    raw_tokens = [tok.strip() for tok in raw_tokens if tok.strip()]

    values = []
    for tok in raw_tokens:
        tok = tok.replace(",", ".")
        try:
            values.append(float(tok))
        except ValueError as exc:
            raise ValueError(f"Wert konnte nicht gelesen werden: {tok}") from exc

    arr = np.asarray(values, dtype=float)

    if len(arr) != expected_length:
        raise ValueError(f"Es wurden {len(arr)} Werte gefunden, erwartet werden {expected_length}.")

    if np.any(~np.isfinite(arr)):
        raise ValueError("Die Zeitreihe enthält ungültige Werte.")

    return arr


def timeseries_to_text(values) -> str:
    """Convert a numeric array/series to one value per line."""
    return "\n".join(f"{float(v):.6f}" for v in values)