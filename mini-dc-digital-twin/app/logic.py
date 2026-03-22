import json
import os
from datetime import datetime, timezone
from random import choice
from typing import Any

from dotenv import load_dotenv

load_dotenv()


SITE_NAME = os.getenv("SITE_NAME", "DC-SJC-LAB")

ZONE_BY_ASSET = {
    "rack-a01": "white-space-1",
    "rack-a02": "white-space-1",
    "rack-b01": "white-space-2",
    "rack-b02": "white-space-2",
    "hvac-1": "cooling-plant",
    "hvac-2": "cooling-plant",
    "ups-1": "electrical-room",
    "pdu-1": "electrical-room",
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
        {"asset_type": "rack", "asset_id": "rack-a01", "metric": "rack_temp_c", "value": choice([24.5, 26.1, 28.0, 33.4, 39.2]), "unit": "C", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-a01", "metric": "rack_kw", "value": choice([4.2, 5.1, 6.8, 7.8, 9.4]), "unit": "kW", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-b02", "metric": "rack_temp_c", "value": choice([23.8, 25.7, 29.1, 31.9, 37.4]), "unit": "C", "ts": ts},
        {"asset_type": "rack", "asset_id": "rack-b02", "metric": "rack_kw", "value": choice([3.9, 4.8, 6.0, 7.5, 8.8]), "unit": "kW", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_supply_temp_c", "value": choice([17.0, 18.5, 21.0, 25.1, 29.2]), "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-1", "metric": "hvac_return_temp_c", "value": choice([27.0, 29.0, 31.2, 35.4, 41.0]), "unit": "C", "ts": ts},
        {"asset_type": "hvac", "asset_id": "hvac-2", "metric": "hvac_fan_speed_pct", "value": choice([48.0, 61.0, 73.0, 91.0, 98.0]), "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-1", "metric": "ups_load_pct", "value": choice([42.0, 55.0, 67.0, 84.0, 95.0]), "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "ups-1", "metric": "ups_battery_pct", "value": choice([100.0, 88.0, 54.0, 28.0, 18.0]), "unit": "%", "ts": ts},
        {"asset_type": "power", "asset_id": "pdu-1", "metric": "pdu_branch_load_pct", "value": choice([35.0, 49.0, 62.0, 79.0, 93.0]), "unit": "%", "ts": ts},
    ]
