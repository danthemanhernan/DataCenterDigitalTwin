import os
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

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "dc_twin")


def create_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )


def insert_telemetry(ch_client: Any, row: dict[str, Any]) -> None:
    ch_client.insert(
        table="telemetry_raw",
        data=[
            [
                row["ts"],
                row["site"],
                row["zone"],
                row["asset_type"],
                row["asset_id"],
                row["metric"],
                row["value"],
                row["unit"],
                row["status"],
                row["alarm_text"],
                row["severity_score"],
                row["quality"],
            ]
        ],
        column_names=[
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
        ],
    )


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


def on_message(
    client: mqtt.Client, userdata: dict[str, Any], msg: mqtt.MQTTMessage
) -> None:
    payload = parse_payload(msg.payload)
    normalized = normalize_message(msg.topic, payload)
    insert_telemetry(userdata["clickhouse"], normalized)
    print(
        f"ingested {normalized['asset_id']} {normalized['metric']}={normalized['value']} status={normalized['status']}"
    )


def main() -> None:
    ch_client = create_client()
    mqtt_client = mqtt.Client(
        CallbackAPIVersion.VERSION2,
        client_id="dc-ingest",
        userdata={"clickhouse": ch_client},
    )
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    print(f"Connecting to ClickHouse http://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
    print(f"Connecting to MQTT mqtt://{MQTT_HOST}:{MQTT_PORT}")
    mqtt_client.loop_forever()


if __name__ == "__main__":
    main()
