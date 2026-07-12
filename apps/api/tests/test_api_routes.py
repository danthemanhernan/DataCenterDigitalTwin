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


def test_reset_simulator_scenario_clears_control_file(monkeypatch):
    cleared = {"called": False}

    def fake_clear_simulator_control():
        cleared["called"] = True

    monkeypatch.setattr(api, "clear_simulator_control", fake_clear_simulator_control)

    response = client.delete("/simulator/scenario")

    assert response.status_code == 200
    assert cleared["called"] is True
    assert response.json() == {"active": False, "scenario": None}


def test_trigger_power_outage_route_calls_trigger_scenario(monkeypatch):
    scenario = {
        "scenario": "power_outage",
        "activated_at": "2026-01-01T12:00:00+00:00",
        "expires_at": "2026-01-01T12:00:30+00:00",
        "duration_seconds": 30,
        "parameters": {},
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
        "parameters": {},
    }


def test_trigger_cooling_degradation_route_calls_trigger_scenario(monkeypatch):
    scenario = {
        "scenario": "cooling_degradation",
        "activated_at": "2026-01-01T12:00:00+00:00",
        "expires_at": "2026-01-01T12:00:30+00:00",
        "duration_seconds": 30,
        "parameters": {},
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
        "parameters": {},
    }
    monkeypatch.setattr(api, "trigger_scenario", lambda scenario_name, duration_seconds: scenario)

    response = client.post("/simulator/scenarios/load-transfer", json={"duration_seconds": 300})

    assert response.status_code == 200
    assert response.json()["scenario"] == "load_transfer"
    assert response.json()["duration_seconds"] == 30


def test_trigger_demand_response_route_passes_policy_parameters(monkeypatch):
    captured = {}
    scenario = {
        "scenario": "demand_response",
        "activated_at": "2026-01-01T12:00:00+00:00",
        "expires_at": "2026-01-01T12:02:00+00:00",
        "duration_seconds": 120,
        "parameters": {
            "price_spike_usd_mwh": 725.0,
            "shed_target_pct": 40.0,
            "recovery_target_minutes": 20,
        },
    }

    def fake_trigger_scenario(scenario_name, duration_seconds, parameters=None):
        captured["scenario_name"] = scenario_name
        captured["duration_seconds"] = duration_seconds
        captured["parameters"] = parameters
        return scenario

    monkeypatch.setattr(api, "trigger_scenario", fake_trigger_scenario)

    response = client.post(
        "/simulator/scenarios/demand-response",
        json={
            "duration_seconds": 120,
            "price_spike_usd_mwh": 725.0,
            "shed_target_pct": 40.0,
            "recovery_target_minutes": 20,
        },
    )

    assert response.status_code == 200
    assert captured == {
        "scenario_name": "demand_response",
        "duration_seconds": 120,
        "parameters": {
            "price_spike_usd_mwh": 725.0,
            "shed_target_pct": 40.0,
            "recovery_target_minutes": 20,
        },
    }
    assert response.json()["scenario"] == "demand_response"
    assert response.json()["parameters"]["shed_target_pct"] == 40.0


def test_power_outage_route_rejects_invalid_duration():
    response = client.post("/simulator/scenarios/power-outage", json={"duration_seconds": 1})

    assert response.status_code == 422
    assert response.json()["detail"]
