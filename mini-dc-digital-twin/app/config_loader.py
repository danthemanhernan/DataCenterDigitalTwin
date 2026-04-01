import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parent / "config"


def config_key(asset_type: str, asset_id: str, metric: str) -> str:
    return f"{asset_type}|{asset_id}|{metric}"


@lru_cache(maxsize=None)
def load_json_config(name: str) -> Any:
    return json.loads((CONFIG_DIR / name).read_text())


@lru_cache(maxsize=1)
def load_alarm_rules() -> dict[str, dict[str, Any]]:
    return load_json_config("alarm_rules.json")


@lru_cache(maxsize=1)
def load_scenarios() -> dict[str, str]:
    return load_json_config("scenarios.json")


@lru_cache(maxsize=1)
def load_point_order() -> list[tuple[str, str, str]]:
    return [tuple(entry) for entry in load_json_config("point_order.json")]


@lru_cache(maxsize=1)
def load_metric_units() -> dict[str, str]:
    return load_json_config("metric_units.json")


@lru_cache(maxsize=1)
def load_zone_by_asset() -> dict[str, str]:
    return load_json_config("zone_by_asset.json")


@lru_cache(maxsize=1)
def load_baseline_choices() -> dict[tuple[str, str, str], list[float]]:
    raw = load_json_config("baseline_choices.json")
    return {
        tuple(key.split("|")): [float(value) for value in values]
        for key, values in raw.items()
    }


@lru_cache(maxsize=1)
def load_scenario_profiles() -> (
    dict[str, dict[tuple[str, str, str], list[tuple[float, float]]]]
):
    raw = load_json_config("scenario_profiles.json")
    return {
        scenario_name: {
            tuple(key.split("|")): [
                (float(progress), float(value)) for progress, value in points
            ]
            for key, points in profiles.items()
        }
        for scenario_name, profiles in raw.items()
    }
