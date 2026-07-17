from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app import alerting


class DummyResult:
    def __init__(self, rows=None, named=None):
        self.result_rows = rows or []
        self._named = named or []

    def named_results(self):
        return self._named


class FakeClient:
    def __init__(self, query_results=None, named_results=None):
        self.query_results = list(query_results or [])
        self.named_results = list(named_results or [])
        self.inserted = []
        self.commands = []
        self.queries = []

    def query(self, sql, parameters=None):
        self.queries.append((sql, parameters))
        rows = self.query_results.pop(0) if self.query_results else []
        named = self.named_results.pop(0) if self.named_results else []
        return DummyResult(rows, named)

    def insert(self, table, data, column_names):
        self.inserted.append({"table": table, "data": data, "column_names": column_names})

    def command(self, sql):
        self.commands.append(sql)


def test_normalize_utc_adds_utc_to_naive_datetime():
    naive = datetime(2026, 1, 1, 12, 0, 0)

    result = alerting.normalize_utc(naive)

    assert result.tzinfo == UTC
    assert result == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_alert_is_muted_returns_true_when_latest_action_is_future_mute(monkeypatch):
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    future = now + timedelta(minutes=5)
    client = FakeClient(query_results=[[["mute", future]]])

    monkeypatch.setattr(alerting, "utc_now", lambda: now)

    assert alerting.alert_is_muted(client, "alert-1") is True


def test_alert_is_shelved_returns_false_when_there_is_no_active_shelve(monkeypatch):
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    past = now - timedelta(minutes=5)
    client = FakeClient(query_results=[[["shelve", past]]])

    monkeypatch.setattr(alerting, "utc_now", lambda: now)

    assert alerting.alert_is_shelved(client, "alert-2") is False


def test_get_alert_state_returns_empty_status_for_missing_history():
    client = FakeClient(query_results=[[]], named_results=[[]])

    state = alerting.get_alert_state(client, "missing-alert")

    assert state["alert_key"] == "missing-alert"
    assert state["acknowledged"] is False
    assert state["muted"] is False
    assert state["shelved"] is False
    assert state["last_action"] is None
    assert client.commands


def test_get_latest_action_ts_returns_none_when_no_rows():
    client = FakeClient(query_results=[[[None]]])

    assert alerting.get_latest_action_ts(client, "alert-1", "acknowledge") is None


def test_get_alert_state_returns_acknowledged_and_active_mute_and_shelve(monkeypatch):
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    event_ts = datetime(2026, 1, 1, 11, 55, 0, tzinfo=UTC)
    ack_ts = datetime(2026, 1, 1, 11, 58, 0, tzinfo=UTC)
    mute_until = now + timedelta(minutes=10)
    shelved_until = now + timedelta(minutes=20)

    rows = [
        {
            "action": "acknowledge",
            "actor": "api",
            "note": "acknowledged",
            "muted_until": None,
            "shelved_until": None,
            "ts": ack_ts,
        },
        {
            "action": "mute",
            "actor": "api",
            "note": "temporary mute",
            "muted_until": mute_until,
            "shelved_until": None,
            "ts": ack_ts - timedelta(minutes=1),
        },
        {
            "action": "shelve",
            "actor": "api",
            "note": "temporary shelve",
            "muted_until": None,
            "shelved_until": shelved_until,
            "ts": ack_ts - timedelta(minutes=2),
        },
    ]

    client = FakeClient(query_results=[[], [[event_ts]]], named_results=[rows])
    monkeypatch.setattr(alerting, "utc_now", lambda: now)

    state = alerting.get_alert_state(client, "alert-1")

    assert state["alert_key"] == "alert-1"
    assert state["acknowledged"] is True
    assert state["muted"] is True
    assert state["muted_until"] == mute_until
    assert state["shelved"] is True
    assert state["shelved_until"] == shelved_until
    assert state["last_action"]["action"] == "acknowledge"


def test_get_latest_alert_event_ts_returns_timestamp_for_existing_event():
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    client = FakeClient(query_results=[[[ts]]])

    assert alerting.get_latest_alert_event_ts(client, "alert-1", "critical") == ts


def test_alert_already_open_returns_false_when_no_matching_event():
    client = FakeClient(query_results=[[[0]]])

    assert alerting.alert_already_open(client, "alert-1", "critical", 5) is False


def test_alert_already_open_returns_true_when_unacknowledged_event_exists(monkeypatch):
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    client = FakeClient(query_results=[[[1]]])

    monkeypatch.setattr(alerting, "get_latest_alert_event_ts", lambda c, k, s=None: ts)
    monkeypatch.setattr(alerting, "get_latest_action_ts", lambda c, k, a: None)

    assert alerting.alert_already_open(client, "alert-1", "critical", 5) is True


def test_insert_alert_event_forwards_data_to_client():
    client = FakeClient()
    row = {
        "ts": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        "alert_key": "alert-1",
        "rule_name": "test-rule",
        "site": "site-a",
        "zone": "zone-a",
        "asset_type": "rack",
        "asset_id": "rack-1",
        "severity": "critical",
        "status": "open",
        "metric": "rack_temp_c",
        "message": "high temperature",
        "current_value": 40.0,
        "threshold_value": 38.0,
        "observation_count": 2,
        "window_minutes": 5,
        "source": "python-alerting",
    }

    alerting.insert_alert_event(client, row)

    assert len(client.inserted) == 1
    inserted = client.inserted[0]
    assert inserted["table"] == "alert_events"
    assert inserted["data"][0][1] == "alert-1"
    assert inserted["data"][0][7] == "critical"


def test_emit_alert_domain_events_emits_threshold_and_raise(monkeypatch):
    emitted = []

    def fake_emit_domain_event(**kwargs):
        emitted.append(kwargs)
        return None

    monkeypatch.setattr(alerting, "emit_domain_event", fake_emit_domain_event)
    row = {
        "ts": datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        "alert_key": "alert-1",
        "rule_name": "test-rule",
        "asset_type": "rack",
        "asset_id": "rack-1",
        "severity": "critical",
        "status": "open",
        "metric": "rack_temp_c",
        "message": "high temperature",
        "current_value": 40.0,
        "threshold_value": 38.0,
        "observation_count": 2,
        "source": "python-alerting",
    }

    alerting.emit_alert_domain_events(row)

    assert [event["event_type"] for event in emitted] == ["ThresholdExceeded", "AlertRaised"]


def test_alert_rules_scope_metrics_to_canonical_asset_types():
    expected_filters = {
        "repeated_critical_rack_temp": "asset_type = 'rack'",
        "sustained_high_hvac_supply_temp": "asset_type = 'hvac'",
        "sustained_low_ups_battery": "asset_type = 'power'",
    }

    for rule in alerting.ALERT_RULES:
        assert expected_filters[rule.name] in rule.query


def test_alert_rules_do_not_select_aggregated_asset_type_alias():
    for rule in alerting.ALERT_RULES:
        assert "any(asset_type) AS asset_type" not in rule.query


def test_evaluate_rules_returns_candidate_when_not_muted_or_open(monkeypatch):
    rule = alerting.AlertRule(
        name="test-rule",
        description="test",
        window_minutes=5,
        query="SELECT 1",
    )
    monkeypatch.setattr(alerting, "ALERT_RULES", [rule])
    client = FakeClient(query_results=[[]], named_results=[[{"alert_key": "alert-1", "severity": "warning"}]])

    monkeypatch.setattr(alerting, "alert_is_muted", lambda c, k: False)
    monkeypatch.setattr(alerting, "alert_is_shelved", lambda c, k: False)
    monkeypatch.setattr(alerting, "alert_already_open", lambda client, key, severity, lookback: False)

    candidates = alerting.evaluate_rules(client)

    assert len(candidates) == 1
    assert candidates[0]["rule_name"] == "test-rule"
    assert candidates[0]["alert_key"] == "alert-1"


def test_evaluate_rules_skips_muted_candidates(monkeypatch):
    rule = alerting.AlertRule(
        name="test-rule",
        description="test",
        window_minutes=5,
        query="SELECT 1",
    )
    monkeypatch.setattr(alerting, "ALERT_RULES", [rule])
    client = FakeClient(query_results=[[]], named_results=[[{"alert_key": "alert-1", "severity": "warning"}]])

    monkeypatch.setattr(alerting, "alert_is_muted", lambda c, k: True)
    monkeypatch.setattr(alerting, "alert_is_shelved", lambda c, k: False)
    monkeypatch.setattr(alerting, "alert_already_open", lambda client, key, severity, lookback: False)

    candidates = alerting.evaluate_rules(client)

    assert candidates == []
