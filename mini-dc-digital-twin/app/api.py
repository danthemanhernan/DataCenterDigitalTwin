import os
import time
from typing import Any
from datetime import datetime, timedelta, timezone

import clickhouse_connect
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

from .alerting import ALERT_RULES, ensure_alerting_schema, get_alert_state, record_alert_action
from .logic import SCENARIOS, get_active_simulator_scenario, serialize_timestamp, trigger_scenario

load_dotenv()


CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "dc_twin")

app = FastAPI(title="Mini DC Digital Twin API", version="0.1.0")

REQUEST_COUNT = Counter(
    "dc_api_requests_total",
    "Total HTTP requests handled by the API",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "dc_api_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
EXCEPTIONS_TOTAL = Counter(
    "dc_api_exceptions_total",
    "Unhandled exceptions raised by the API",
    ["method", "path"],
)
APP_INFO = Gauge(
    "dc_api_app_info",
    "Static app info marker for dashboarding",
    ["app_name", "version"],
)

APP_INFO.labels(app_name=app.title, version=app.version).set(1)


class PowerOutageRequest(BaseModel):
    duration_seconds: int = Field(default=30, ge=5, le=600)


class AlertActionRequest(BaseModel):
    actor: str = Field(default="api")
    note: str = Field(default="", max_length=500)


class AlertMuteRequest(AlertActionRequest):
    duration_minutes: int = Field(default=30, ge=1, le=1440)


def serialize_scenario_state(scenario: dict[str, Any] | None) -> dict[str, Any]:
    if not scenario:
        return {"active": False, "scenario": None}

    return {
        "active": True,
        "scenario": scenario["scenario"],
        "activated_at": serialize_timestamp(scenario["activated_at"]),
        "expires_at": serialize_timestamp(scenario["expires_at"]),
        "duration_seconds": scenario["duration_seconds"],
    }


def serialize_alert_state(alert_state: dict[str, Any]) -> dict[str, Any]:
    muted_until = alert_state.get("muted_until")
    return {
        "alert_key": alert_state["alert_key"],
        "acknowledged": alert_state["acknowledged"],
        "muted": alert_state["muted"],
        "muted_until": serialize_timestamp(muted_until) if muted_until else None,
        "last_action": alert_state["last_action"],
    }


def get_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    started = time.perf_counter()
    path = request.url.path
    method = request.method

    if path == "/metrics":
        return await call_next(request)

    try:
        response = await call_next(request)
    except Exception:
        EXCEPTIONS_TOTAL.labels(method=method, path=path).inc()
        REQUEST_COUNT.labels(method=method, path=path, status_code="500").inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(time.perf_counter() - started)
        raise

    REQUEST_COUNT.labels(method=method, path=path, status_code=str(response.status_code)).inc()
    REQUEST_LATENCY.labels(method=method, path=path).observe(time.perf_counter() - started)
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/simulator/scenario")
def simulator_scenario() -> dict[str, Any]:
    return serialize_scenario_state(get_active_simulator_scenario())


@app.get("/simulator/scenarios")
def list_simulator_scenarios() -> dict[str, Any]:
    return {"scenarios": SCENARIOS}


@app.post("/simulator/scenarios/power-outage")
def trigger_power_outage_scenario(payload: PowerOutageRequest) -> dict[str, Any]:
    scenario = trigger_scenario("power_outage", duration_seconds=payload.duration_seconds)
    return serialize_scenario_state(scenario)


@app.post("/simulator/scenarios/cooling-degradation")
def trigger_cooling_degradation_scenario(payload: PowerOutageRequest) -> dict[str, Any]:
    scenario = trigger_scenario("cooling_degradation", duration_seconds=payload.duration_seconds)
    return serialize_scenario_state(scenario)


@app.post("/simulator/scenarios/load-transfer")
def trigger_load_transfer_scenario(payload: PowerOutageRequest) -> dict[str, Any]:
    scenario = trigger_scenario("load_transfer", duration_seconds=payload.duration_seconds)
    return serialize_scenario_state(scenario)


@app.get("/alarms/active")
def active_alarms(limit: int = 25):
    client = get_client()
    result = client.query(
        """
        SELECT ts, site, zone, asset_id, metric, value, unit, status, alarm_text
        FROM v_active_alarms
        ORDER BY ts DESC
        LIMIT %(limit)s
        """,
        parameters={"limit": limit},
    )
    return {"rows": result.named_results()}


@app.get("/alerts/recent")
def recent_alerts(limit: int = 50):
    client = get_client()
    ensure_alerting_schema(client)
    result = client.query(
        """
        SELECT
            ts,
            alert_key,
            rule_name,
            asset_id,
            severity,
            metric,
            current_value,
            threshold_value,
            observation_count,
            message
        FROM dc_twin.v_recent_alerts
        ORDER BY ts DESC
        LIMIT %(limit)s
        """,
        parameters={"limit": limit},
    )
    rows = []
    for row in result.named_results():
        state = get_alert_state(client, row["alert_key"])
        row["acknowledged"] = state["acknowledged"]
        row["muted"] = state["muted"]
        row["muted_until"] = serialize_timestamp(state["muted_until"]) if state["muted_until"] else None
        rows.append(row)
    return {"rows": rows}


@app.get("/alerts/rules")
def alert_rules():
    return {
        "rules": [
            {
                "name": rule.name,
                "description": rule.description,
                "window_minutes": rule.window_minutes,
            }
            for rule in ALERT_RULES
        ]
    }


@app.get("/alerts/{alert_key}/state")
def alert_state(alert_key: str):
    client = get_client()
    return serialize_alert_state(get_alert_state(client, alert_key))


@app.post("/alerts/{alert_key}/acknowledge")
def acknowledge_alert(alert_key: str, payload: AlertActionRequest):
    client = get_client()
    action = record_alert_action(
        client,
        alert_key=alert_key,
        action="acknowledge",
        actor=payload.actor,
        note=payload.note,
    )
    return {
        "action": {
            **action,
            "ts": serialize_timestamp(action["ts"]),
            "muted_until": None,
        },
        "state": serialize_alert_state(get_alert_state(client, alert_key)),
    }


@app.post("/alerts/{alert_key}/mute")
def mute_alert(alert_key: str, payload: AlertMuteRequest):
    client = get_client()
    muted_until = datetime.now(timezone.utc) + timedelta(minutes=payload.duration_minutes)
    action = record_alert_action(
        client,
        alert_key=alert_key,
        action="mute",
        actor=payload.actor,
        note=payload.note,
        muted_until=muted_until,
    )
    return {
        "action": {
            **action,
            "ts": serialize_timestamp(action["ts"]),
            "muted_until": serialize_timestamp(muted_until),
        },
        "state": serialize_alert_state(get_alert_state(client, alert_key)),
    }


@app.post("/alerts/{alert_key}/unmute")
def unmute_alert(alert_key: str, payload: AlertActionRequest):
    client = get_client()
    action = record_alert_action(
        client,
        alert_key=alert_key,
        action="unmute",
        actor=payload.actor,
        note=payload.note,
        muted_until=None,
    )
    return {
        "action": {
            **action,
            "ts": serialize_timestamp(action["ts"]),
            "muted_until": None,
        },
        "state": serialize_alert_state(get_alert_state(client, alert_key)),
    }


@app.get("/telemetry/recent")
def recent_telemetry(limit: int = 50):
    client = get_client()
    result = client.query(
        """
        SELECT ts, asset_type, asset_id, metric, value, unit, status
        FROM telemetry_raw
        ORDER BY ts DESC
        LIMIT %(limit)s
        """,
        parameters={"limit": limit},
    )
    return {"rows": result.named_results()}


@app.get("/summary")
def summary():
    client = get_client()
    alarms = client.query(
        """
        SELECT status, count() AS count
        FROM telemetry_raw
        WHERE ts >= now() - INTERVAL 15 MINUTE
        GROUP BY status
        ORDER BY count DESC
        """
    )
    assets = client.query(
        """
        SELECT asset_type, uniqExact(asset_id) AS asset_count
        FROM telemetry_raw
        GROUP BY asset_type
        ORDER BY asset_type
        """
    )
    return {
        "alarm_counts_15m": alarms.named_results(),
        "asset_inventory": assets.named_results(),
    }
