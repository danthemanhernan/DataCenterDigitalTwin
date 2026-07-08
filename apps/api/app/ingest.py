import os
import time
from typing import Any

import clickhouse_connect
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from paho.mqtt.client import CallbackAPIVersion

from .logic import normalize_message, parse_payload

load_dotenv()


MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_ROOT = os.getenv("MQTT_TOPIC_ROOT", "dc/telemetry")
INGEST_BATCH_SIZE = int(os.getenv("INGEST_BATCH_SIZE", "100"))
INGEST_FLUSH_SECONDS = float(os.getenv("INGEST_FLUSH_SECONDS", "5.0"))

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "dc_twin")

TELEMETRY_COLUMNS = [
    "ts",
    "site",
    "zone",
    "asset_type",
    "asset_id",
    "metric",
    "value",
    "unit",
    "status",
    "alarm_text",
    "severity_score",
    "quality",
]


def create_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )


def telemetry_values(row: dict[str, Any]) -> list[Any]:
    return [row[column] for column in TELEMETRY_COLUMNS]


def insert_telemetry(ch_client: Any, rows: list[list[Any]]) -> None:
    if not rows:
        return

    ch_client.insert(
        table="telemetry_raw",
        data=rows,
        column_names=TELEMETRY_COLUMNS,
    )


class TelemetryBuffer:
    def __init__(self, ch_client: Any, batch_size: int, flush_seconds: float) -> None:
        self.ch_client = ch_client
        self.batch_size = max(batch_size, 1)
        self.flush_seconds = max(flush_seconds, 0.1)
        self.rows: list[list[Any]] = []
        self.last_flush = time.monotonic()

    def add(self, row: dict[str, Any]) -> int:
        self.rows.append(telemetry_values(row))
        if len(self.rows) >= self.batch_size or (time.monotonic() - self.last_flush) >= self.flush_seconds:
            return self.flush()
        return 0

    def flush(self) -> int:
        if not self.rows:
            self.last_flush = time.monotonic()
            return 0

        rows = self.rows
        self.rows = []
        insert_telemetry(self.ch_client, rows)
        self.last_flush = time.monotonic()
        return len(rows)


def on_connect(
    client: mqtt.Client,
    userdata: dict[str, Any],
    flags: dict[str, Any],
    reason_code,
    properties,
) -> None:
    topic = f"{MQTT_TOPIC_ROOT}/#"
    client.subscribe(topic)
    print(f"Subscribed to {topic}")


def on_message(client: mqtt.Client, userdata: dict[str, Any], msg: mqtt.MQTTMessage) -> None:
    payload = parse_payload(msg.payload)
    normalized = normalize_message(msg.topic, payload)
    flushed_count = userdata["telemetry_buffer"].add(normalized)
    print(
        f"ingested {normalized['asset_id']} {normalized['metric']}={normalized['value']} status={normalized['status']}"
    )
    if flushed_count:
        print(f"flushed {flushed_count} telemetry rows to ClickHouse")


def main() -> None:
    ch_client = create_client()
    telemetry_buffer = TelemetryBuffer(
        ch_client,
        batch_size=INGEST_BATCH_SIZE,
        flush_seconds=INGEST_FLUSH_SECONDS,
    )
    mqtt_client = mqtt.Client(
        CallbackAPIVersion.VERSION2,
        client_id="dc-ingest",
        userdata={"telemetry_buffer": telemetry_buffer},
    )
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    print(f"Connecting to ClickHouse http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
    print(f"Connecting to MQTT mqtt://{MQTT_HOST}:{MQTT_PORT}")
    print(f"Batching ClickHouse inserts with size={INGEST_BATCH_SIZE} flush_seconds={INGEST_FLUSH_SECONDS}")
    mqtt_client.loop_forever()


if __name__ == "__main__":
    main()
