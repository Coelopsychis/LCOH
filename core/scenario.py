from __future__ import annotations

from dataclasses import asdict, fields
import json
from typing import Any, Mapping, TypeVar

import numpy as np
import pandas as pd

from .models import (
    SystemInputs,
    CapexInputs,
    OpexInputs,
    PowerInputs,
    ElectricityCostInputs,
    RevenueInputs,
    FundingInputs,
    ModelInputs,
)
from .timeseries import validate_timeseries


SCENARIO_SCHEMA_VERSION = 1
SCENARIO_TYPE = "lcoh_simulation"
TIMESERIES_COLUMNS = (
    "hour",
    "pv_kwh_per_kw",
    "wind_kwh_per_kw",
    "day_ahead_eur_per_mwh",
    "co2_eur_per_t",
    "section13k_kwh",
)

T = TypeVar("T")


def _dataclass_from_mapping(cls: type[T], values: Mapping[str, Any] | None) -> T:
    """Construct a dataclass while tolerating missing/future fields.

    Missing fields retain the dataclass defaults. Unknown fields are ignored so
    that scenario files remain reasonably robust across app versions.
    """
    values = values or {}
    allowed = {f.name for f in fields(cls)}
    kwargs = {key: value for key, value in values.items() if key in allowed}
    return cls(**kwargs)


def model_inputs_to_dict(inputs: ModelInputs) -> dict[str, Any]:
    return {
        "system": asdict(inputs.system),
        "capex": asdict(inputs.capex),
        "opex": asdict(inputs.opex),
        "power": asdict(inputs.power),
        "electricity_costs": asdict(inputs.electricity_costs),
        "revenue": asdict(inputs.revenue),
        "funding": asdict(inputs.funding),
    }


def model_inputs_from_dict(data: Mapping[str, Any]) -> ModelInputs:
    if not isinstance(data, Mapping):
        raise ValueError("Der Abschnitt 'inputs' muss ein JSON-Objekt sein.")

    return ModelInputs(
        system=_dataclass_from_mapping(SystemInputs, data.get("system")),
        capex=_dataclass_from_mapping(CapexInputs, data.get("capex")),
        opex=_dataclass_from_mapping(OpexInputs, data.get("opex")),
        power=_dataclass_from_mapping(PowerInputs, data.get("power")),
        electricity_costs=_dataclass_from_mapping(
            ElectricityCostInputs, data.get("electricity_costs")
        ),
        revenue=_dataclass_from_mapping(RevenueInputs, data.get("revenue")),
        funding=_dataclass_from_mapping(FundingInputs, data.get("funding")),
    )


def normalize_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize the five hourly input series used by the app."""
    df = df.copy().reset_index(drop=True)
    validate_timeseries(df)

    if "co2_eur_per_t" not in df.columns:
        df["co2_eur_per_t"] = 66.6
    if "section13k_kwh" not in df.columns:
        df["section13k_kwh"] = 0.0
    if "hour" not in df.columns:
        df.insert(0, "hour", np.arange(1, len(df) + 1))

    for col in TIMESERIES_COLUMNS:
        if col == "hour":
            continue
        values = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        if len(values) != 8760:
            raise ValueError(f"Zeitreihe '{col}' muss 8760 Werte enthalten.")
        if np.any(~np.isfinite(values)):
            raise ValueError(f"Zeitreihe '{col}' enthält ungültige Werte.")
        df[col] = values

    return df.loc[:, TIMESERIES_COLUMNS]


def scenario_payload(inputs: ModelInputs, timeseries_df: pd.DataFrame) -> dict[str, Any]:
    ts = normalize_timeseries(timeseries_df)
    return {
        "type": SCENARIO_TYPE,
        "schema_version": SCENARIO_SCHEMA_VERSION,
        "methodology": "Excel Rev. 8",
        "inputs": model_inputs_to_dict(inputs),
        "timeseries": {
            col: ts[col].tolist()
            for col in TIMESERIES_COLUMNS
        },
    }


def scenario_to_json_bytes(inputs: ModelInputs, timeseries_df: pd.DataFrame) -> bytes:
    payload = scenario_payload(inputs, timeseries_df)
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ).encode("utf-8")


def scenario_from_payload(payload: Mapping[str, Any]) -> tuple[ModelInputs, pd.DataFrame]:
    if not isinstance(payload, Mapping):
        raise ValueError("Die Datei enthält kein gültiges JSON-Objekt.")
    if payload.get("type") != SCENARIO_TYPE:
        raise ValueError(
            "Die Datei ist keine gespeicherte LCOH-Simulation. "
            "Bitte eine über 'Simulation speichern' erzeugte JSON-Datei verwenden."
        )

    version = payload.get("schema_version")
    if version != SCENARIO_SCHEMA_VERSION:
        raise ValueError(
            f"Nicht unterstützte Szenario-Version: {version!r}. "
            f"Erwartet wird Version {SCENARIO_SCHEMA_VERSION}."
        )

    inputs = model_inputs_from_dict(payload.get("inputs", {}))
    ts_raw = payload.get("timeseries")
    if not isinstance(ts_raw, Mapping):
        raise ValueError("Der Abschnitt 'timeseries' fehlt oder ist ungültig.")

    try:
        ts_df = pd.DataFrame({key: ts_raw[key] for key in ts_raw})
    except Exception as exc:
        raise ValueError("Die Zeitreihen konnten nicht gelesen werden.") from exc

    ts_df = normalize_timeseries(ts_df)
    return inputs, ts_df


def scenario_from_json_bytes(data: bytes | bytearray | str) -> tuple[ModelInputs, pd.DataFrame]:
    try:
        if isinstance(data, (bytes, bytearray)):
            payload = json.loads(data.decode("utf-8-sig"))
        else:
            payload = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Die Datei ist kein gültiges JSON.") from exc

    return scenario_from_payload(payload)
