import os
import time

import clickhouse_connect
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

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
