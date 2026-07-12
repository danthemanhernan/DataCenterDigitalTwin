from __future__ import annotations

from uuid import UUID

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
        "scenario_id": "power_outage-test",
        "correlation_id": "00000000-0000-0000-0000-000000000001",
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
        "scenario_id": "power_outage-test",
        "correlation_id": "00000000-0000-0000-0000-000000000001",
        "activated_at": "2026-01-01T12:00:00+00:00",
        "expires_at": "2026-01-01T12:00:30+00:00",
        "duration_seconds": 30,
        "parameters": {},
    }


def test_trigger_cooling_degradation_route_calls_trigger_scenario(monkeypatch):
    scenario = {
        "scenario": "cooling_degradation",
        "scenario_id": "cooling_degradation-test",
        "correlation_id": "00000000-0000-0000-0000-000000000002",
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
        "scenario_id": "load_transfer-test",
        "correlation_id": "00000000-0000-0000-0000-000000000003",
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
        "scenario_id": "demand_response-test",
        "correlation_id": "00000000-0000-0000-0000-000000000004",
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


def test_demand_response_route_emits_domain_events(monkeypatch):
    emitted = []
    scenario = {
        "scenario": "demand_response",
        "scenario_id": "demand_response-test",
        "correlation_id": "00000000-0000-0000-0000-000000000005",
        "activated_at": "2026-01-01T12:00:00+00:00",
        "expires_at": "2026-01-01T12:02:00+00:00",
        "duration_seconds": 120,
        "parameters": {
            "price_spike_usd_mwh": 725.0,
            "shed_target_pct": 40.0,
            "recovery_target_minutes": 20,
        },
    }

    def fake_append_event(event, expected_stream_version=None):
        emitted.append((event, expected_stream_version))
        return event.with_stream_version(len(emitted))

    monkeypatch.setattr(api, "EVENT_STORE_ENABLED", True)
    monkeypatch.setattr(api, "trigger_scenario", lambda scenario_name, duration_seconds, parameters=None: scenario)
    monkeypatch.setattr(api, "append_event", fake_append_event)

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
    assert [event.event_type for event, _ in emitted] == [
        "ScenarioStarted",
        "UtilityPriceSpikeDetected",
        "DemandResponsePolicyEvaluated",
        "LoadSheddingRequested",
        "EquipmentCommandIssued",
    ]
    assert [expected for _, expected in emitted] == [0, 1, 2, 3, 4]
    assert {event.correlation_id for event, _ in emitted} == {UUID("00000000-0000-0000-0000-000000000005")}
    assert emitted[-1][0].payload["command"] == "reduce_gpu_load"


def test_recent_events_route_returns_serialized_events(monkeypatch):
    event = api.EventEnvelope(
        event_type="ScenarioStarted",
        stream_id="scenario:test",
        stream_version=1,
        source="api",
        payload={"scenario": "demand_response"},
    )
    monkeypatch.setattr(api, "list_recent_events", lambda limit: [event])

    response = client.get("/events/recent?limit=10")

    assert response.status_code == 200
    assert response.json()["rows"][0]["event_type"] == "ScenarioStarted"


def test_power_outage_route_rejects_invalid_duration():
    response = client.post("/simulator/scenarios/power-outage", json={"duration_seconds": 1})

    assert response.status_code == 422
    assert response.json()["detail"]
