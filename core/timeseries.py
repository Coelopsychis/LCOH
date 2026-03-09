from __future__ import annotations

import numpy as np
import pandas as pd


def make_demo_timeseries(seed: int = 7) -> pd.DataFrame:
    """
    Synthetischer 8760h-Datensatz:
    - PV-Profil
    - Wind-Profil
    - Day-Ahead-Preis
    """
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
        }
    )


def validate_timeseries(df: pd.DataFrame) -> None:
    required = {"pv_kwh_per_kw", "wind_kwh_per_kw", "day_ahead_eur_per_mwh"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Fehlende Spalten: {sorted(missing)}")
    if len(df) != 8760:
        raise ValueError(f"Zeitreihe muss 8760 Zeilen haben, gefunden: {len(df)}")