import os

import clickhouse_connect
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()


CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "dc_twin")

app = FastAPI(title="Mini DC Digital Twin API", version="0.1.0")


def get_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
