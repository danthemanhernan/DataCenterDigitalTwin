from __future__ import annotations

from fastapi.testclient import TestClient

from app import api

client = TestClient(api.app)


def test_health_route_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_route_returns_prometheus_content_type():
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert response.content


def test_list_simulator_scenarios_returns_scenarios():
    response = client.get("/simulator/scenarios")

    assert response.status_code == 200
    payload = response.json()
    assert "scenarios" in payload
    assert isinstance(payload["scenarios"], dict)


def test_simulator_scenario_returns_inactive_by_default(monkeypatch):
    monkeypatch.setattr(api, "get_active_simulator_scenario", lambda: None)

    response = client.get("/simulator/scenario")

    assert response.status_code == 200
    assert response.json() == {"active": False, "scenario": None}


def test_trigger_power_outage_route_calls_trigger_scenario(monkeypatch):
    scenario = {
        "scenario": "power_outage",
        "activated_at": "2026-01-01T12:00:00+00:00",
        "expires_at": "2026-01-01T12:00:30+00:00",
        "duration_seconds": 30,
    }
    monkeypatch.setattr(api, "trigger_scenario", lambda scenario_name, duration_seconds: scenario)

    response = client.post("/simulator/scenarios/power-outage", json={"duration_seconds": 60})

    assert response.status_code == 200
    assert response.json() == {
        "active": True,
        "scenario": "power_outage",
        "activated_at": "2026-01-01T12:00:00+00:00",
        "expires_at": "2026-01-01T12:00:30+00:00",
        "duration_seconds": 30,
    }


def test_trigger_cooling_degradation_route_calls_trigger_scenario(monkeypatch):
    scenario = {
        "scenario": "cooling_degradation",
        "activated_at": "2026-01-01T12:00:00+00:00",
        "expires_at": "2026-01-01T12:00:30+00:00",
        "duration_seconds": 30,
    }
    monkeypatch.setattr(api, "trigger_scenario", lambda scenario_name, duration_seconds: scenario)

    response = client.post("/simulator/scenarios/cooling-degradation", json={"duration_seconds": 120})

    assert response.status_code == 200
    assert response.json()["scenario"] == "cooling_degradation"
    assert response.json()["duration_seconds"] == 30


def test_trigger_load_transfer_route_calls_trigger_scenario(monkeypatch):
    scenario = {
        "scenario": "load_transfer",
        "activated_at": "2026-01-01T12:00:00+00:00",
        "expires_at": "2026-01-01T12:00:30+00:00",
        "duration_seconds": 30,
    }
    monkeypatch.setattr(api, "trigger_scenario", lambda scenario_name, duration_seconds: scenario)

    response = client.post("/simulator/scenarios/load-transfer", json={"duration_seconds": 300})

    assert response.status_code == 200
    assert response.json()["scenario"] == "load_transfer"
    assert response.json()["duration_seconds"] == 30


def test_power_outage_route_rejects_invalid_duration():
    response = client.post("/simulator/scenarios/power-outage", json={"duration_seconds": 1})

    assert response.status_code == 422
    assert response.json()["detail"]
