from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class HourlySeries:
    pv1_kwh_per_kw: np.ndarray
    wind2_kwh_per_kw: np.ndarray
    day_ahead_eur_per_mwh: np.ndarray

    def validate(self) -> None:
        n = len(self.day_ahead_eur_per_mwh)
        if n != 8760:
            raise ValueError(f"Expected 8760 hours, got {n}.")
        for name, arr in [
            ("pv1_kwh_per_kw", self.pv1_kwh_per_kw),
            ("wind2_kwh_per_kw", self.wind2_kwh_per_kw),
        ]:
            if len(arr) != n:
                raise ValueError(f"Series length mismatch: {name} has {len(arr)}, expected {n}.")
        if np.any(~np.isfinite(self.day_ahead_eur_per_mwh)):
            raise ValueError("Non-finite values in day_ahead series.")


def to_hourly_series(
    pv1_kwh_per_kw: Sequence[float],
    wind2_kwh_per_kw: Sequence[float],
    day_ahead_eur_per_mwh: Sequence[float],
) -> HourlySeries:
    hs = HourlySeries(
        pv1_kwh_per_kw=np.asarray(pv1_kwh_per_kw, dtype=float),
        wind2_kwh_per_kw=np.asarray(wind2_kwh_per_kw, dtype=float),
        day_ahead_eur_per_mwh=np.asarray(day_ahead_eur_per_mwh, dtype=float),
    )
    hs.validate()
    return hs