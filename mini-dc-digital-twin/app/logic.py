import json
import os
from pathlib import Path
from datetime import datetime, timezone
from random import choice
from typing import Any

from dotenv import load_dotenv

load_dotenv()


SITE_NAME = os.getenv("SITE_NAME", "DC-SJC-LAB")
SIMULATOR_CONTROL_PATH = Path(os.getenv("SIMULATOR_CONTROL_PATH", Path(__file__).resolve().parents[1] / "runtime" / "simulator-control.json"))

ZONE_BY_ASSET = {
    "rack-a01": "white-space-1",
    "rack-a02": "white-space-1",
    "rack-b01": "white-space-2",
    "rack-b02": "white-space-2",
    "hvac-1": "cooling-plant",
    "hvac-2": "cooling-plant",
    "ups-1": "electrical-room",
    "ups-2": "electrical-room",
    "pdu-1": "electrical-room",
    "pdu-2": "electrical-room",
}

ALARM_RULES = {
    "rack_temp_c": {"warn": 32.0, "crit": 38.0, "message": "Rack inlet temperature high"},
    "rack_kw": {"warn": 7.0, "crit": 9.0, "message": "Rack power draw high"},
    "hvac_supply_temp_c": {"warn": 24.0, "crit": 28.0, "message": "HVAC supply air too warm"},
    "hvac_return_temp_c": {"warn": 34.0, "crit": 40.0, "message": "HVAC return air high"},
    "hvac_fan_speed_pct": {"warn": 90.0, "crit": 97.0, "message": "HVAC fan near maximum"},
    "ups_load_pct": {"warn": 80.0, "crit": 92.0, "message": "UPS load high"},
    "ups_battery_pct": {"warn": 30.0, "crit": 20.0, "message": "UPS battery low", "inverse": True},
    "pdu_branch_load_pct": {"warn": 75.0, "crit": 90.0, "message": "PDU branch nearing limit"},
}

SCENARIOS = {
    "power_outage": "Utility loss causing UPS strain, battery discharge, and thermal rise.",
    "cooling_degradation": "One cooling train underperforming, raising room temperatures and fan demand.",
    "load_transfer": "Maintenance-style power transfer increasing load on one redundant power path.",
}


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
        "expires_at": serialize_timestamp(datetime.fromtimestamp(expires_at, tz=timezone.utc)),
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


def generate_simulated_points() -> list[dict[str, Any]]:
    ts = utc_now()
    return [
        {"asset_type": "rack", "asset_id": "rack-a01", "metric": "rack_temp_c", "value": choice([23.8, 24.6, 25.5, 26.3, 27.1]), "unit": "C", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-a01", "metric": "rack_kw", "value": choice([4.2, 4.6, 5.1, 5.5, 6.0]), "unit": "kW", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-b02", "metric": "rack_temp_c", "value": choice([23.5, 24.2, 25.0, 25.8, 26.6]), "unit": "C", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-b02", "metric": "rack_kw", "value": choice([3.9, 4.4, 4.8, 5.3, 5.8]), "unit": "kW", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_supply_temp_c", "value": choice([17.2, 18.0, 18.8, 19.6, 20.4]), "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_return_temp_c", "value": choice([27.0, 28.2, 29.4, 30.1, 31.0]), "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_fan_speed_pct", "value": choice([48.0, 54.0, 60.0, 66.0, 72.0]), "unit": "%", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_supply_temp_c", "value": choice([17.0, 17.8, 18.6, 19.4, 20.2]), "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_return_temp_c", "value": choice([26.8, 27.9, 29.0, 29.8, 30.7]), "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_fan_speed_pct", "value": choice([46.0, 52.0, 58.0, 64.0, 70.0]), "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-1", "metric": "ups_load_pct", "value": choice([42.0, 48.0, 54.0, 60.0, 66.0]), "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-1", "metric": "ups_battery_pct", "value": choice([100.0, 99.0, 98.0, 97.0, 96.0]), "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-2", "metric": "ups_load_pct", "value": choice([40.0, 46.0, 52.0, 58.0, 64.0]), "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-2", "metric": "ups_battery_pct", "value": choice([100.0, 99.0, 98.0, 97.0, 96.0]), "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "pdu-1", "metric": "pdu_branch_load_pct", "value": choice([34.0, 40.0, 46.0, 52.0, 58.0]), "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "pdu-2", "metric": "pdu_branch_load_pct", "value": choice([32.0, 38.0, 44.0, 50.0, 56.0]), "unit": "%", "ts": ts},
    ]


def generate_power_outage_points() -> list[dict[str, Any]]:
    ts = utc_now()
    return [
        {"asset_type": "rack", "asset_id": "rack-a01", "metric": "rack_temp_c", "value": 41.8, "unit": "C", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-a01", "metric": "rack_kw", "value": 9.6, "unit": "kW", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-b02", "metric": "rack_temp_c", "value": 39.7, "unit": "C", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-b02", "metric": "rack_kw", "value": 9.2, "unit": "kW", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_supply_temp_c", "value": 30.5, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_return_temp_c", "value": 43.8, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_fan_speed_pct", "value": 99.0, "unit": "%", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_supply_temp_c", "value": 29.8, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_return_temp_c", "value": 42.9, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_fan_speed_pct", "value": 98.4, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-1", "metric": "ups_load_pct", "value": 97.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-1", "metric": "ups_battery_pct", "value": 12.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-2", "metric": "ups_load_pct", "value": 95.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-2", "metric": "ups_battery_pct", "value": 15.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "pdu-1", "metric": "pdu_branch_load_pct", "value": 94.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "pdu-2", "metric": "pdu_branch_load_pct", "value": 92.0, "unit": "%", "ts": ts},
    ]


def generate_cooling_degradation_points() -> list[dict[str, Any]]:
    ts = utc_now()
    return [
        {"asset_type": "rack", "asset_id": "rack-a01", "metric": "rack_temp_c", "value": 34.6, "unit": "C", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-a01", "metric": "rack_kw", "value": 6.1, "unit": "kW", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-b02", "metric": "rack_temp_c", "value": 33.8, "unit": "C", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-b02", "metric": "rack_kw", "value": 5.9, "unit": "kW", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_supply_temp_c", "value": 26.2, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_return_temp_c", "value": 37.6, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_fan_speed_pct", "value": 93.0, "unit": "%", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_supply_temp_c", "value": 22.8, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_return_temp_c", "value": 33.2, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_fan_speed_pct", "value": 84.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-1", "metric": "ups_load_pct", "value": 61.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-1", "metric": "ups_battery_pct", "value": 98.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-2", "metric": "ups_load_pct", "value": 58.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-2", "metric": "ups_battery_pct", "value": 98.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "pdu-1", "metric": "pdu_branch_load_pct", "value": 59.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "pdu-2", "metric": "pdu_branch_load_pct", "value": 56.0, "unit": "%", "ts": ts},
    ]


def generate_load_transfer_points() -> list[dict[str, Any]]:
    ts = utc_now()
    return [
        {"asset_type": "rack", "asset_id": "rack-a01", "metric": "rack_temp_c", "value": 27.3, "unit": "C", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-a01", "metric": "rack_kw", "value": 6.4, "unit": "kW", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-b02", "metric": "rack_temp_c", "value": 26.8, "unit": "C", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-b02", "metric": "rack_kw", "value": 6.1, "unit": "kW", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_supply_temp_c", "value": 19.1, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_return_temp_c", "value": 30.2, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_fan_speed_pct", "value": 68.0, "unit": "%", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_supply_temp_c", "value": 19.4, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_return_temp_c", "value": 30.8, "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_fan_speed_pct", "value": 71.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-1", "metric": "ups_load_pct", "value": 85.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-1", "metric": "ups_battery_pct", "value": 95.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-2", "metric": "ups_load_pct", "value": 41.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-2", "metric": "ups_battery_pct", "value": 97.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "pdu-1", "metric": "pdu_branch_load_pct", "value": 82.0, "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "pdu-2", "metric": "pdu_branch_load_pct", "value": 45.0, "unit": "%", "ts": ts},
    ]
