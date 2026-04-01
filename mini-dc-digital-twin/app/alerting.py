import argparse
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import clickhouse_connect
from dotenv import load_dotenv


load_dotenv()


CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "dc_twin")

ALERT_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS dc_twin.alert_events
(
    ts DateTime64(3, 'UTC'),
    alert_key String,
    rule_name LowCardinality(String),
    site LowCardinality(String),
    zone LowCardinality(String),
    asset_type LowCardinality(String),
    asset_id String,
    severity LowCardinality(String),
    status LowCardinality(String),
    metric LowCardinality(String),
    message String,
    current_value Float64,
    threshold_value Float64,
    observation_count UInt16,
    window_minutes UInt8,
    source LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY (rule_name, asset_id, ts);
"""

ALERT_ACTIONS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS dc_twin.alert_actions
(
    ts DateTime64(3, 'UTC'),
    alert_key String,
    action LowCardinality(String),
    actor String,
    note String,
    muted_until Nullable(DateTime64(3, 'UTC'))
)
ENGINE = MergeTree
ORDER BY (alert_key, ts);
"""


@dataclass
class AlertRule:
    name: str
    description: str
    window_minutes: int
    query: str


ALERT_RULES = [
    AlertRule(
        name="repeated_critical_rack_temp",
        description="Repeated critical rack temperature in the last 5 minutes",
        window_minutes=5,
        query="""
        SELECT
            now64(3) AS ts,
            concat('repeated_critical_rack_temp:', asset_id) AS alert_key,
            any(site) AS site,
            any(zone) AS zone,
            any(asset_type) AS asset_type,
            asset_id,
            'critical' AS severity,
            'open' AS status,
            'rack_temp_c' AS metric,
            'Rack temperature has entered critical state repeatedly' AS message,
            max(value) AS current_value,
            38.0 AS threshold_value,
            toUInt16(count()) AS observation_count,
            toUInt8(5) AS window_minutes,
            'python-alerting' AS source
        FROM dc_twin.telemetry_raw
        WHERE
            ts >= now() - INTERVAL 5 MINUTE
            AND metric = 'rack_temp_c'
            AND status = 'critical'
        GROUP BY asset_id
        HAVING count() >= 2
        """,
    ),
    AlertRule(
        name="sustained_high_hvac_supply_temp",
        description="HVAC supply temperature drifting into warning or critical range",
        window_minutes=5,
        query="""
        SELECT
            now64(3) AS ts,
            concat('sustained_high_hvac_supply_temp:', asset_id) AS alert_key,
            any(site) AS site,
            any(zone) AS zone,
            any(asset_type) AS asset_type,
            asset_id,
            if(max(value) >= 28.0, 'critical', 'warning') AS severity,
            'open' AS status,
            'hvac_supply_temp_c' AS metric,
            'HVAC supply temperature is drifting high' AS message,
            max(value) AS current_value,
            if(max(value) >= 28.0, 28.0, 24.0) AS threshold_value,
            toUInt16(count()) AS observation_count,
            toUInt8(5) AS window_minutes,
            'python-alerting' AS source
        FROM dc_twin.telemetry_raw
        WHERE
            ts >= now() - INTERVAL 5 MINUTE
            AND metric = 'hvac_supply_temp_c'
        GROUP BY asset_id
        HAVING avg(value) >= 24.0 AND count() >= 2
        """,
    ),
    AlertRule(
        name="sustained_low_ups_battery",
        description="UPS battery has dropped into warning or critical range",
        window_minutes=10,
        query="""
        SELECT
            now64(3) AS ts,
            concat('sustained_low_ups_battery:', asset_id) AS alert_key,
            any(site) AS site,
            any(zone) AS zone,
            any(asset_type) AS asset_type,
            asset_id,
            if(min(value) <= 20.0, 'critical', 'warning') AS severity,
            'open' AS status,
            'ups_battery_pct' AS metric,
            'UPS battery has remained below healthy reserve' AS message,
            min(value) AS current_value,
            if(min(value) <= 20.0, 20.0, 30.0) AS threshold_value,
            toUInt16(count()) AS observation_count,
            toUInt8(10) AS window_minutes,
            'python-alerting' AS source
        FROM dc_twin.telemetry_raw
        WHERE
            ts >= now() - INTERVAL 10 MINUTE
            AND metric = 'ups_battery_pct'
        GROUP BY asset_id
        HAVING min(value) <= 30.0 AND count() >= 2
        """,
    ),
]


def get_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )


def ensure_alerting_schema(client: Any) -> None:
    client.command("CREATE DATABASE IF NOT EXISTS dc_twin")
    client.command(ALERT_TABLE_DDL)
    client.command(ALERT_ACTIONS_TABLE_DDL)


def alert_is_muted(client: Any, alert_key: str) -> bool:
    result = client.query(
        """
        SELECT count() AS event_count
        FROM dc_twin.alert_actions
        WHERE
            alert_key = %(alert_key)s
            AND action = 'mute'
            AND muted_until IS NOT NULL
            AND muted_until > now64(3)
            AND ts = (
                SELECT max(ts)
                FROM dc_twin.alert_actions
                WHERE alert_key = %(alert_key)s
            )
        """,
        parameters={"alert_key": alert_key},
    )
    row = result.first_row
    return bool(row and row[0] > 0)


def get_alert_state(client: Any, alert_key: str) -> dict[str, Any]:
    ensure_alerting_schema(client)
    result = client.query(
        """
        SELECT action, actor, note, muted_until, ts
        FROM dc_twin.alert_actions
        WHERE alert_key = %(alert_key)s
        ORDER BY ts DESC
        LIMIT 1
        """,
        parameters={"alert_key": alert_key},
    )
    rows = result.named_results()
    if not rows:
        return {
            "alert_key": alert_key,
            "acknowledged": False,
            "muted": False,
            "muted_until": None,
            "last_action": None,
        }

    latest = rows[0]
    muted_until = latest["muted_until"]
    muted = latest["action"] == "mute" and muted_until is not None and muted_until > datetime.now(timezone.utc)
    return {
        "alert_key": alert_key,
        "acknowledged": latest["action"] == "acknowledge",
        "muted": muted,
        "muted_until": muted_until,
        "last_action": latest,
    }


def record_alert_action(
    client: Any,
    alert_key: str,
    action: str,
    actor: str = "api",
    note: str = "",
    muted_until: Any = None,
) -> dict[str, Any]:
    ensure_alerting_schema(client)
    ts = client.query("SELECT now64(3) AS ts").named_results()[0]["ts"]
    client.insert(
        table="alert_actions",
        data=[[ts, alert_key, action, actor, note, muted_until]],
        column_names=["ts", "alert_key", "action", "actor", "note", "muted_until"],
    )
    return {
        "ts": ts,
        "alert_key": alert_key,
        "action": action,
        "actor": actor,
        "note": note,
        "muted_until": muted_until,
    }


def alert_already_open(client: Any, alert_key: str, severity: str, lookback_minutes: int) -> bool:
    result = client.query(
        """
        SELECT count() AS event_count
        FROM dc_twin.alert_events
        WHERE
            alert_key = %(alert_key)s
            AND severity = %(severity)s
            AND ts >= now() - INTERVAL %(lookback_minutes)s MINUTE
        """,
        parameters={
            "alert_key": alert_key,
            "severity": severity,
            "lookback_minutes": lookback_minutes,
        },
    )
    row = result.first_row
    return bool(row and row[0] > 0)


def insert_alert_event(client: Any, row: dict[str, Any]) -> None:
    client.insert(
        table="alert_events",
        data=[
            [
                row["ts"],
                row["alert_key"],
                row["rule_name"],
                row["site"],
                row["zone"],
                row["asset_type"],
                row["asset_id"],
                row["severity"],
                row["status"],
                row["metric"],
                row["message"],
                row["current_value"],
                row["threshold_value"],
                row["observation_count"],
                row["window_minutes"],
                row["source"],
            ]
        ],
        column_names=[
            "ts",
            "alert_key",
            "rule_name",
            "site",
            "zone",
            "asset_type",
            "asset_id",
            "severity",
            "status",
            "metric",
            "message",
            "current_value",
            "threshold_value",
            "observation_count",
            "window_minutes",
            "source",
        ],
    )


def evaluate_rules(client: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for rule in ALERT_RULES:
        result = client.query(rule.query)
        for row in result.named_results():
            candidate = dict(row)
            candidate["rule_name"] = rule.name
            if alert_is_muted(client, candidate["alert_key"]):
                continue
            if not alert_already_open(client, candidate["alert_key"], candidate["severity"], rule.window_minutes):
                candidates.append(candidate)
    return candidates


def run_alert_cycle(client: Any) -> list[dict[str, Any]]:
    ensure_alerting_schema(client)
    emitted: list[dict[str, Any]] = []
    for candidate in evaluate_rules(client):
        insert_alert_event(client, candidate)
        emitted.append(candidate)
    return emitted


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate telemetry and emit alert events.")
    parser.add_argument("--once", action="store_true", help="Run a single alert evaluation cycle and exit.")
    parser.add_argument("--interval-seconds", type=int, default=30, help="Polling interval for continuous mode.")
    args = parser.parse_args()

    client = get_client()
    print(f"Connecting to ClickHouse http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")

    if args.once:
        emitted = run_alert_cycle(client)
        print(f"Emitted {len(emitted)} alert event(s)")
        for alert in emitted:
            print(
                f"{alert['rule_name']} {alert['asset_id']} severity={alert['severity']} "
                f"value={alert['current_value']}"
            )
        return

    while True:
        emitted = run_alert_cycle(client)
        print(f"Alert cycle complete: emitted {len(emitted)} alert event(s)")
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
