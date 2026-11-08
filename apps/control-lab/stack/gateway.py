import json
import logging
import time
from contextlib import asynccontextmanager
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import FastAPI, Query, Response
from paho.mqtt import client as mqtt
from prometheus_client import Counter, Gauge, CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, ValidationError

INGESTED = Counter("twin_ingested", "Successful ClickHouse insert attempts")
REJECTED = Counter("twin_rejected", "Invalid telemetry messages")
WRITE_FAILURES = Counter("twin_write_failures", "Failed ClickHouse insert attempts")
LAST = Gauge("twin_last_ingest_unixtime", "Wall clock time of last insert")
INLET = Gauge("twin_inlet_c", "Last valid rack inlet temperature")
FACILITY = Gauge("twin_facility_kw", "Last facility power reading")
LAST.set(time.time())
LOG = logging.getLogger("uvicorn.error")
DDL = """CREATE TABLE IF NOT EXISTS telemetry (
  run_id String, event_id String, minute UInt16,
  ingested_at DateTime64(3) DEFAULT now64(3), payload String
) ENGINE = ReplacingMergeTree(ingested_at) ORDER BY (run_id, event_id)"""


class Envelope(BaseModel):
    run_id: str
    event_id: str
    minute: int
    inlet_c: float | None
    facility_kw: float
    schema_version: int


def query(sql, body=b""):
    req = Request(
        "http://clickhouse:8123/?" + urlencode({"query": sql}),
        data=body,
        headers={"X-ClickHouse-User": "twin", "X-ClickHouse-Key": "twin-lab-local"},
    )
    with urlopen(req, timeout=3) as response:
        return response.read()


def receive(client, _, message):
    try:
        event = Envelope.model_validate_json(message.payload)
        if not 0 <= event.minute <= 240:
            raise ValueError("minute outside supported range")
    except (ValidationError, ValueError):
        REJECTED.inc()
        client.ack(message.mid, message.qos)
        return
    row = event.model_dump(include={"run_id", "event_id", "minute"})
    row["payload"] = message.payload.decode()
    data = (json.dumps(row) + "\n").encode()
    for delay in (0, 0.5, 1):
        time.sleep(delay)
        try:
            query("INSERT INTO telemetry FORMAT JSONEachRow", data)
            break
        except OSError:
            WRITE_FAILURES.inc()
    else:
        LOG.error("Dropping event after ClickHouse write retries: %s", event.event_id)
        client.ack(message.mid, message.qos)
        return
    INGESTED.inc()
    LAST.set(time.time())
    FACILITY.set(event.facility_kw)
    if event.inlet_c is not None:
        INLET.set(event.inlet_c)
    client.ack(message.mid, message.qos)


@asynccontextmanager
async def lifespan(_):
    for attempt in range(30):
        try:
            query(DDL)
            break
        except OSError:
            if attempt == 29:
                raise
            time.sleep(1)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="twin-gateway",
                         clean_session=False, manual_ack=True)
    client.on_connect = lambda c, u, f, reason, p: c.subscribe("#", qos=1) if not reason.is_failure else None
    client.on_message = receive
    client.connect_async("mqtt")
    client.loop_start()
    try:
        yield
    finally:
        client.disconnect()
        client.loop_stop()


app = FastAPI(title="DataCenterDigitalTwin gateway", lifespan=lifespan)


@app.get("/telemetry")
def telemetry(limit: int = Query(25, ge=1, le=500)):
    data = query(f"SELECT payload FROM telemetry FINAL ORDER BY ingested_at DESC, minute DESC LIMIT {limit} FORMAT JSONEachRow")
    return [json.loads(json.loads(line)["payload"]) for line in data.splitlines()]


@app.get("/health")
def health():
    query("SELECT 1")
    return {"clickhouse": "ready"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
