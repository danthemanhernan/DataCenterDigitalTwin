import json
import os
import time
from uuid import UUID

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from paho.mqtt.client import CallbackAPIVersion

from .domain_events import emit_domain_event
from .logic import (
    generate_cooling_degradation_points,
    generate_demand_response_points,
    generate_load_transfer_points,
    generate_power_outage_points,
    generate_simulated_points,
    get_active_simulator_scenario,
    serialize_timestamp,
    topic_for,
)

load_dotenv()


MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_ROOT = os.getenv("MQTT_TOPIC_ROOT", "dc/telemetry")
PUBLISH_INTERVAL_SECONDS = float(os.getenv("SIM_INTERVAL_SECONDS", "2.0"))
SCENARIO_ASSETS = {
    "power_outage": ("utility-grid", "utility"),
    "cooling_degradation": ("cooling-loop-a", "cooling"),
    "load_transfer": ("gpu-cluster-a", "compute"),
    "demand_response": ("gpu-cluster-a", "compute"),
}


def main() -> None:
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="dc-simulator")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    print(f"Publishing simulated telemetry to mqtt://{MQTT_HOST}:{MQTT_PORT}")
    previous_scenario_id = None
    previous_scenario = None
    while True:
        scenario = get_active_simulator_scenario()
        if scenario and scenario["scenario_id"] != previous_scenario_id:
            asset_id, asset_type = SCENARIO_ASSETS[scenario["scenario"]]
            emit_domain_event(
                event_type="EquipmentStateChanged",
                stream_id=f"asset:scenario:{scenario['scenario_id']}",
                source="simulator",
                asset_id=asset_id,
                asset_type=asset_type,
                correlation_id=UUID(scenario["correlation_id"]),
                scenario_id=scenario["scenario_id"],
                payload={"state": "active", "scenario": scenario["scenario"]},
                idempotency_key=f"{scenario['scenario_id']}:equipment-state-active",
            )
        if scenario is None and previous_scenario is not None:
            asset_id, asset_type = SCENARIO_ASSETS[previous_scenario["scenario"]]
            emit_domain_event(
                event_type="ScenarioCompleted",
                stream_id=f"scenario:{previous_scenario['scenario_id']}",
                source="simulator",
                correlation_id=UUID(previous_scenario["correlation_id"]),
                scenario_id=previous_scenario["scenario_id"],
                payload={"scenario": previous_scenario["scenario"], "reason": "natural_expiry"},
                idempotency_key=f"{previous_scenario['scenario_id']}:scenario-completed",
            )
            emit_domain_event(
                event_type="EquipmentRecovered",
                stream_id=f"asset:scenario:{previous_scenario['scenario_id']}",
                source="simulator",
                asset_id=asset_id,
                asset_type=asset_type,
                correlation_id=UUID(previous_scenario["correlation_id"]),
                scenario_id=previous_scenario["scenario_id"],
                payload={"state": "recovered", "scenario": previous_scenario["scenario"]},
                idempotency_key=f"{previous_scenario['scenario_id']}:equipment-recovered",
            )
        previous_scenario_id = scenario["scenario_id"] if scenario else None
        previous_scenario = scenario
        scenario_name = scenario["scenario"] if scenario else None
        scenario_generators = {
            "power_outage": generate_power_outage_points,
            "cooling_degradation": generate_cooling_degradation_points,
            "load_transfer": generate_load_transfer_points,
            "demand_response": generate_demand_response_points,
        }
        generator = scenario_generators.get(scenario_name)
        points = generator(scenario) if generator else generate_simulated_points()

        if scenario:
            print(f"active scenario {scenario['scenario']} until {serialize_timestamp(scenario['expires_at'])}")

        for point in points:
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
