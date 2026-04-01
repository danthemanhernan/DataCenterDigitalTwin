import json
import os
from datetime import datetime, timezone
from pathlib import Path
from random import choice
from typing import Any

from dotenv import load_dotenv

from .config_loader import (
    load_alarm_rules,
    load_baseline_choices,
    load_metric_units,
    load_point_order,
    load_scenario_profiles,
    load_scenarios,
    load_zone_by_asset,
)

load_dotenv()


SITE_NAME = os.getenv("SITE_NAME", "DC-SJC-LAB")
SIMULATOR_CONTROL_PATH = Path(
    os.getenv(
        "SIMULATOR_CONTROL_PATH",
        Path(__file__).resolve().parents[1] / "runtime" / "simulator-control.json",
    )
)

ZONE_BY_ASSET = load_zone_by_asset()
ALARM_RULES = load_alarm_rules()
SCENARIOS = load_scenarios()
POINT_ORDER = load_point_order()
METRIC_UNITS = load_metric_units()
BASELINE_CHOICES = load_baseline_choices()
SCENARIO_PROFILES = load_scenario_profiles()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_timestamp(value: datetime) -> str:
    return parse_timestamp(value).isoformat()


def parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if value in (None, ""):
        return datetime.now(timezone.utc)

    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    raise TypeError(f"Unsupported timestamp value: {value!r}")


def topic_for(asset_type: str, asset_id: str, root: str = "dc/telemetry") -> str:
    return f"{root}/{asset_type}/{asset_id}"


def parse_payload(payload: bytes) -> dict[str, Any]:
    raw = json.loads(payload.decode("utf-8"))
    raw["ts"] = parse_timestamp(raw.get("ts"))
    return raw


def read_simulator_control() -> dict[str, Any] | None:
    if not SIMULATOR_CONTROL_PATH.exists():
        return None

    raw = json.loads(SIMULATOR_CONTROL_PATH.read_text())
    raw["activated_at"] = parse_timestamp(raw.get("activated_at"))
    raw["expires_at"] = parse_timestamp(raw.get("expires_at"))
    return raw


def clear_simulator_control() -> None:
    if SIMULATOR_CONTROL_PATH.exists():
        SIMULATOR_CONTROL_PATH.unlink()


def trigger_scenario(scenario: str, duration_seconds: int = 30) -> dict[str, Any]:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unsupported scenario: {scenario}")

    activated_at = utc_now()
    expires_at = activated_at.timestamp() + max(duration_seconds, 1)
    command = {
        "scenario": scenario,
        "activated_at": serialize_timestamp(activated_at),
        "expires_at": serialize_timestamp(
            datetime.fromtimestamp(expires_at, tz=timezone.utc)
        ),
        "duration_seconds": max(duration_seconds, 1),
    }
    SIMULATOR_CONTROL_PATH.parent.mkdir(parents=True, exist_ok=True)
    SIMULATOR_CONTROL_PATH.write_text(json.dumps(command, indent=2))
    return read_simulator_control() or command


def trigger_power_outage(duration_seconds: int = 30) -> dict[str, Any]:
    return trigger_scenario("power_outage", duration_seconds=duration_seconds)


def get_active_simulator_scenario() -> dict[str, Any] | None:
    command = read_simulator_control()
    if not command:
        return None

    if command["expires_at"] <= utc_now():
        clear_simulator_control()
        return None

    return command


def determine_alarm(metric: str, value: float) -> tuple[str, str]:
    rule = ALARM_RULES.get(metric)
    if not rule:
        return "normal", ""

    warn = rule["warn"]
    crit = rule["crit"]
    inverse = rule.get("inverse", False)

    if inverse:
        if value <= crit:
            return "critical", rule["message"]
        if value <= warn:
            return "warning", rule["message"]
    else:
        if value >= crit:
            return "critical", rule["message"]
        if value >= warn:
            return "warning", rule["message"]

    return "normal", ""


def normalize_message(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    parts = topic.split("/")
    asset_type = parts[-2]
    asset_id = parts[-1]
    metric = payload["metric"]
    value = float(payload["value"])
    status, alarm_text = determine_alarm(metric, value)
    zone = ZONE_BY_ASSET.get(asset_id, "unknown")

    return {
        "ts": payload.get("ts", utc_now()),
        "site": SITE_NAME,
        "zone": zone,
        "asset_type": asset_type,
        "asset_id": asset_id,
        "metric": metric,
        "value": value,
        "unit": payload.get("unit", ""),
        "status": status,
        "alarm_text": alarm_text,
        "severity_score": {"normal": 0, "warning": 50, "critical": 100}[status],
        "quality": payload.get("quality", "good"),
    }


def scenario_progress(
    scenario: dict[str, Any] | None, ts: datetime | None = None
) -> float:
    if not scenario:
        return 0.0

    current_ts = ts or utc_now()
    activated_at = parse_timestamp(scenario["activated_at"])
    expires_at = parse_timestamp(scenario["expires_at"])
    total_seconds = max((expires_at - activated_at).total_seconds(), 1.0)
    elapsed_seconds = max((current_ts - activated_at).total_seconds(), 0.0)
    return min(elapsed_seconds / total_seconds, 1.0)


def interpolate_profile(points: list[tuple[float, float]], progress: float) -> float:
    if not points:
        raise ValueError("Scenario profile must include at least one point")

    if progress <= points[0][0]:
        return points[0][1]

    for index in range(1, len(points)):
        left_progress, left_value = points[index - 1]
        right_progress, right_value = points[index]
        if progress <= right_progress:
            span = right_progress - left_progress
            if span <= 0:
                return right_value
            ratio = (progress - left_progress) / span
            return left_value + ((right_value - left_value) * ratio)

    return points[-1][1]


def build_point(
    asset_type: str, asset_id: str, metric: str, value: float, ts: datetime
) -> dict[str, Any]:
    return {
        "asset_type": asset_type,
        "asset_id": asset_id,
        "metric": metric,
        "value": round(value, 1),
        "unit": METRIC_UNITS[metric],
        "ts": ts,
    }


def generate_simulated_points() -> list[dict[str, Any]]:
    ts = utc_now()
    return [
        build_point(
            asset_type,
            asset_id,
            metric,
            choice(BASELINE_CHOICES[(asset_type, asset_id, metric)]),
            ts,
        )
        for asset_type, asset_id, metric in POINT_ORDER
    ]


def generate_profiled_points(
    scenario_name: str, scenario: dict[str, Any] | None
) -> list[dict[str, Any]]:
    ts = utc_now()
    progress = scenario_progress(scenario, ts)
    profile = SCENARIO_PROFILES[scenario_name]
    return [
        build_point(
            asset_type,
            asset_id,
            metric,
            interpolate_profile(profile[(asset_type, asset_id, metric)], progress),
            ts,
        )
        for asset_type, asset_id, metric in POINT_ORDER
    ]


def generate_power_outage_points(
    scenario: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return generate_profiled_points("power_outage", scenario)


def generate_cooling_degradation_points(
    scenario: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return generate_profiled_points("cooling_degradation", scenario)


def generate_load_transfer_points(
    scenario: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return generate_profiled_points("load_transfer", scenario)
