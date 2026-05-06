import argparse
import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, stdev
from typing import Any

import clickhouse_connect
from dotenv import load_dotenv

from .logic import determine_alarm


load_dotenv()


CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "dc_twin")
DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "ml" / "artifacts"

INVERSE_METRICS = {"ups_battery_pct"}
MAINTENANCE_METRICS = {
    "rack_temp_c",
    "rack_kw",
    "hvac_supply_temp_c",
    "hvac_return_temp_c",
    "hvac_fan_speed_pct",
    "ups_load_pct",
    "ups_battery_pct",
    "pdu_branch_load_pct",
}


@dataclass(frozen=True)
class TelemetryPoint:
    ts: datetime
    site: str
    zone: str
    asset_type: str
    asset_id: str
    metric: str
    value: float
    unit: str
    status: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_client() -> Any:
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )


def fetch_telemetry(hours: int, limit: int) -> list[TelemetryPoint]:
    client = get_client()
    safe_hours = max(1, min(hours, 24 * 30))
    safe_limit = max(1, min(limit, 1_000_000))
    result = client.query(
        f"""
        SELECT ts, site, zone, asset_type, asset_id, metric, value, unit, status
        FROM dc_twin.telemetry_raw
        WHERE
            ts >= now() - INTERVAL {safe_hours} HOUR
            AND metric IN %(metrics)s
        ORDER BY ts ASC
        LIMIT %(limit)s
        """,
        parameters={"metrics": tuple(sorted(MAINTENANCE_METRICS)), "limit": safe_limit},
    )
    return [row_to_point(row) for row in result.named_results()]


def row_to_point(row: dict[str, Any]) -> TelemetryPoint:
    return TelemetryPoint(
        ts=normalize_ts(row["ts"]),
        site=row.get("site", ""),
        zone=row.get("zone", ""),
        asset_type=row["asset_type"],
        asset_id=row["asset_id"],
        metric=row["metric"],
        value=float(row["value"]),
        unit=row.get("unit", ""),
        status=row.get("status") or determine_alarm(row["metric"], float(row["value"]))[0],
    )


def build_fixture_points() -> list[TelemetryPoint]:
    now = utc_now()
    specs = [
        ("hvac", "hvac-1", "hvac_supply_temp_c", 18.5, 0.12),
        ("hvac", "hvac-1", "hvac_return_temp_c", 28.5, 0.10),
        ("hvac", "hvac-1", "hvac_fan_speed_pct", 52.0, 0.25),
        ("hvac", "hvac-2", "hvac_supply_temp_c", 18.8, 0.08),
        ("hvac", "hvac-2", "hvac_return_temp_c", 29.0, 0.08),
        ("ups", "ups-a", "ups_load_pct", 48.0, 0.15),
        ("ups", "ups-a", "ups_battery_pct", 98.0, -0.02),
        ("rack", "rack-a01", "rack_temp_c", 24.0, 0.04),
        ("rack", "rack-a01", "rack_kw", 4.4, 0.01),
    ]
    points: list[TelemetryPoint] = []
    for step in range(48):
        ts = now - timedelta(minutes=2 * (47 - step))
        for asset_type, asset_id, metric, baseline, drift in specs:
            value = baseline + (step * drift)
            if asset_id == "hvac-1" and step >= 36:
                value += {"hvac_supply_temp_c": 6.0, "hvac_return_temp_c": 5.0, "hvac_fan_speed_pct": 30.0}.get(metric, 0.0)
            if asset_id == "ups-a" and metric == "ups_battery_pct" and step >= 38:
                value -= 42.0
            status, _ = determine_alarm(metric, value)
            points.append(
                TelemetryPoint(
                    ts=ts,
                    site="DC-SJC-LAB",
                    zone="fixture",
                    asset_type=asset_type,
                    asset_id=asset_id,
                    metric=metric,
                    value=round(value, 2),
                    unit="",
                    status=status,
                )
            )
    return points


def train_baseline(points: list[TelemetryPoint]) -> dict[str, dict[str, float]]:
    by_metric: dict[str, list[float]] = defaultdict(list)
    for point in points:
        if point.status == "normal":
            by_metric[point.metric].append(point.value)

    model: dict[str, dict[str, float]] = {}
    for metric, values in by_metric.items():
        if len(values) < 2:
            continue
        sigma = stdev(values)
        model[metric] = {
            "mean": mean(values),
            "stddev": sigma if sigma > 0 else 0.1,
            "samples": float(len(values)),
        }
    return model


def metric_zscore(metric: str, value: float, model: dict[str, dict[str, float]]) -> float:
    baseline = model.get(metric)
    if not baseline:
        return 0.0
    raw = (value - baseline["mean"]) / baseline["stddev"]
    return -raw if metric in INVERSE_METRICS else raw


def slope_per_hour(points: list[TelemetryPoint]) -> float:
    if len(points) < 2:
        return 0.0
    first = points[0]
    last = points[-1]
    hours = max((last.ts - first.ts).total_seconds() / 3600, 1 / 60)
    return (last.value - first.value) / hours


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def build_training_dataset(points: list[TelemetryPoint], window_minutes: int) -> list[dict[str, Any]]:
    cutoff = utc_now() - timedelta(minutes=window_minutes)
    grouped: dict[tuple[str, str, str], list[TelemetryPoint]] = defaultdict(list)
    for point in points:
        if point.ts >= cutoff:
            grouped[(point.asset_type, point.asset_id, point.metric)].append(point)

    dataset = []
    for (asset_type, asset_id, metric), rows in sorted(grouped.items()):
        values = [row.value for row in rows]
        statuses = [row.status for row in rows]
        dataset.append(
            {
                "asset_type": asset_type,
                "asset_id": asset_id,
                "metric": metric,
                "sample_count": len(rows),
                "avg_value": mean(values),
                "min_value": min(values),
                "max_value": max(values),
                "latest_value": rows[-1].value,
                "slope_per_hour": slope_per_hour(rows),
                "warning_or_critical_ratio": sum(status != "normal" for status in statuses) / len(statuses),
                "critical_ratio": sum(status == "critical" for status in statuses) / len(statuses),
            }
        )
    return dataset


def score_dataset(
    dataset: list[dict[str, Any]], model: dict[str, dict[str, float]]
) -> list[dict[str, Any]]:
    scored = []
    for row in dataset:
        metric = row["metric"]
        latest_value = row["latest_value"]
        zscore = metric_zscore(metric, latest_value, model)
        trend = -row["slope_per_hour"] if metric in INVERSE_METRICS else row["slope_per_hour"]
        trend_component = clamp(max(trend, 0) * 0.15, 0, 10)
        risk_score = (
            max(zscore, 0) * 18
            + row["warning_or_critical_ratio"] * 35
            + row["critical_ratio"] * 30
            + trend_component
        )
        if not math.isfinite(risk_score):
            risk_score = 0.0
        scored.append(
            {
                **row,
                "anomaly_zscore": round(zscore, 3),
                "trend_component": round(trend_component, 1),
                "maintenance_risk_score": round(clamp(risk_score, 0, 100), 1),
                "risk_band": risk_band(risk_score),
            }
        )
    return sorted(scored, key=lambda item: item["maintenance_risk_score"], reverse=True)


def risk_band(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")


def run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    points = build_fixture_points() if args.fixture else fetch_telemetry(args.hours, args.limit)
    if not points:
        raise SystemExit(
            "No telemetry rows found. Start the stack and simulator first, or rerun with --fixture for a local smoke test."
        )

    model = train_baseline(points)
    dataset = build_training_dataset(points, args.window_minutes)
    ranked_assets = score_dataset(dataset, model)
    report = {
        "generated_at": utc_now().isoformat(),
        "source": "fixture" if args.fixture else "clickhouse",
        "telemetry_rows": len(points),
        "window_minutes": args.window_minutes,
        "model_type": "metric_mean_std_anomaly_baseline",
        "target": "maintenance risk from abnormal telemetry level, persistence, and adverse trend",
        "top_risks": ranked_assets[: args.top_n],
    }

    artifact_dir = Path(args.artifact_dir)
    write_json(artifact_dir / "maintenance_model.json", model)
    write_json(artifact_dir / "maintenance_dataset.json", dataset)
    write_json(artifact_dir / "maintenance_report.json", report)

    print(json.dumps(report, indent=2, default=str))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a lightweight predictive-maintenance baseline from telemetry history."
    )
    parser.add_argument("--hours", type=int, default=24, help="Telemetry lookback window for ClickHouse extraction.")
    parser.add_argument("--limit", type=int, default=100_000, help="Maximum telemetry rows to extract.")
    parser.add_argument("--window-minutes", type=int, default=30, help="Recent scoring window.")
    parser.add_argument("--top-n", type=int, default=10, help="Number of ranked risks to include in the report.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="Directory for model, dataset, and report JSON artifacts.")
    parser.add_argument("--fixture", action="store_true", help="Use deterministic sample telemetry for local smoke testing.")
    return parser.parse_args()


if __name__ == "__main__":
    run_experiment(parse_args())
