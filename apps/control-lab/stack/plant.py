"""Generate the browser twin's telemetry contract from a model configuration."""
import json
import math
import sys
from pathlib import Path


def clamp(value, low, high):
    return min(high, max(low, value))


def simulate(c):
    temperature = c["initial"]
    integral = 0
    previous = None
    points = []
    extensions = json.loads(c.get("schemaExtras", "{}"))
    for minute in range(c["duration"]):
        fault = c["scenario"] if minute >= c["faultAt"] else "Normal"
        load = c["peakLoad"] if minute >= 20 else c["baseLoad"]
        price = c["peakPrice"] if minute >= c["peakAt"] else c["price"]
        shed = min(c["shed"], load) if c["shedEnabled"] and price >= c["shedPrice"] else 0
        it = c["idle"] + c["gpu"] * (load - shed) / 100
        sensor = temperature + c["bias"] + c["noise"] * math.sin(minute * 2.17)
        if fault == "Sensor drift":
            sensor += 3
        if fault == "Sensor dropout":
            sensor = None
        error = 0 if sensor is None else sensor - c["setpoint"]
        derivative = 0 if sensor is None or previous is None else sensor - previous
        candidate = clamp(integral + error, -200, 200)
        lower, upper = c["minFan"], c["maxFan"]
        raw = 40 + c["kp"] * error + c["ki"] * candidate + c["kd"] * derivative
        if sensor is not None and (lower <= raw <= upper or raw > upper and error < 0 or raw < lower and error > 0):
            integral = candidate
        previous = sensor
        command = upper if sensor is None else clamp(40 + c["kp"] * error + c["ki"] * integral + c["kd"] * derivative, lower, upper)
        fan = command * 0.18 if fault == "Fan failure" else command
        flow = c["flow"] * 0.1 if fault == "Chilled-water loss" else c["flow"]
        cooling = c["capacity"] * fan / 100 * clamp(flow / 2.2, 0, 1.5) * clamp((temperature - c["water"]) / 13, 0, 1.6)
        facility = it * (1 + c["overhead"]) + 5 * (fan / 100) ** 3 + cooling / 4 + 0.6 * flow
        if minute % c["period"] == 0 and fault != "MQTT outage":
            points.append({
                "schema_version": c["schema"], "event_id": f"lab01-{minute}",
                "site_id": "lab01", "minute": minute, "inlet_c": None if sensor is None else round(sensor, 3),
                "fan_pct": round(fan, 2), "water_flow_lps": flow, "it_kw": round(it, 3),
                "facility_kw": round(facility, 3), "tariff_usd_kwh": price, "shed_pct": shed,
                "quality": "missing" if sensor is None else "good", "extensions": extensions,
            })
        temperature += (it + 0.32 * (c["ambient"] - temperature) - cooling) / (c["mass"] * 60)
    return {"config": c, "points": points}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python3 plant.py twin-config.json data/twin-run.json")
    config = json.loads(Path(sys.argv[1]).read_text())
    Path(sys.argv[2]).write_text(json.dumps(simulate(config), indent=2) + "\n")
