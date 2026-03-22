import json
import os
import time

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from dotenv import load_dotenv

from .logic import generate_simulated_points, serialize_timestamp, topic_for

load_dotenv()


MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_ROOT = os.getenv("MQTT_TOPIC_ROOT", "dc/telemetry")
PUBLISH_INTERVAL_SECONDS = float(os.getenv("SIM_INTERVAL_SECONDS", "2.0"))


def main() -> None:
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="dc-simulator")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    print(f"Publishing simulated telemetry to mqtt://{MQTT_HOST}:{MQTT_PORT}")
    while True:
        for point in generate_simulated_points():
            topic = topic_for(point["asset_type"], point["asset_id"], MQTT_TOPIC_ROOT)
            payload = json.dumps(
                {
                    "metric": point["metric"],
                    "value": point["value"],
                    "unit": point["unit"],
                    "ts": serialize_timestamp(point["ts"]),
                    "quality": "good",
                }
            )
            client.publish(topic, payload=payload, qos=0)
            print(f"published {topic} -> {payload}")

        time.sleep(PUBLISH_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
