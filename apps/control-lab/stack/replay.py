"""Publish a Site run export to the local broker."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from threading import Event

from paho.mqtt import client as mqtt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--seconds-per-minute", type=float, default=0.25)
    args = parser.parse_args()
    if args.seconds_per_minute < 0:
        parser.error("--seconds-per-minute must be nonnegative")
    run = json.loads(args.run.read_text())
    config = run["config"]
    run_id = hashlib.sha256(json.dumps(run, sort_keys=True).encode()).hexdigest()[:20]
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    ready = Event()
    client.on_connect = lambda c, u, f, reason, p: ready.set() if not reason.is_failure else None
    client.connect("mqtt")
    client.loop_start()
    try:
        if not ready.wait(10):
            raise RuntimeError("MQTT connection not acknowledged")
        last_minute = 0
        for point in run["points"]:
            time.sleep((point["minute"] - last_minute) * args.seconds_per_minute)
            last_minute = point["minute"]
            payload = json.dumps({**point, "run_id": run_id})
            count = 2 if config["scenario"] == "Duplicate message" and last_minute >= config["faultAt"] else 1
            for _ in range(count):
                delivery = client.publish(config["topic"], payload, qos=1)
                delivery.wait_for_publish(10)
                if not delivery.is_published():
                    raise RuntimeError(f"Publish timed out at minute {last_minute}")
        print(f"Replayed {len(run['points'])} unique events for run {run_id}")
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
