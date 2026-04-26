import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const GRAFANA_BASE = (import.meta.env.VITE_GRAFANA_BASE_URL || "http://localhost:3000").replace(/\/$/, "");

const REFRESH_INTERVAL_MS = 5000;

const SCENARIOS = [
  {
    key: "power-outage",
    title: "Power Outage",
    durationSeconds: 45,
    description: "Stress both UPS paths, heat the white space, and force the alarm surface to light up.",
  },
  {
    key: "cooling-degradation",
    title: "Cooling Degradation",
    durationSeconds: 60,
    description: "Drift HVAC supply and return performance until thermal alerts appear on the plant side.",
  },
  {
    key: "load-transfer",
    title: "Load Transfer",
    durationSeconds: 45,
    description: "Shift electrical loading across the redundant power paths without a total outage.",
  },
];

const EMBEDS = [
  {
    title: "Rack Heat",
    subtitle: "Live rack temperature excursion view",
    src: `${GRAFANA_BASE}/d-solo/dc-facility-trends-live/mini-dc-facility-trends-live?orgId=1&from=now-30m&to=now&theme=dark&panelId=1&refresh=5s`,
  },
  {
    title: "Power Utilization",
    subtitle: "Rack power trendline under scenario load",
    src: `${GRAFANA_BASE}/d-solo/dc-operations-overview/mini-dc-operations-overview?orgId=1&from=now-30m&to=now&theme=dark&panelId=6&refresh=5s`,
  },
  {
    title: "Cooling Plant",
    subtitle: "HVAC supply performance in the live facility dashboard",
    src: `${GRAFANA_BASE}/d-solo/dc-facility-trends-live/mini-dc-facility-trends-live?orgId=1&from=now-30m&to=now&theme=dark&panelId=3&refresh=5s`,
  },
  {
    title: "UPS Load",
    subtitle: "Redundant UPS path loading under scenario changes",
    src: `${GRAFANA_BASE}/d-solo/dc-facility-trends-live/mini-dc-facility-trends-live?orgId=1&from=now-30m&to=now&theme=dark&panelId=6&refresh=5s`,
  },
  {
    title: "UPS Battery",
    subtitle: "Battery reserve across both UPS units",
    src: `${GRAFANA_BASE}/d-solo/dc-facility-trends-live/mini-dc-facility-trends-live?orgId=1&from=now-30m&to=now&theme=dark&panelId=7&refresh=5s`,
  },
];

const ASSET_LAYOUT = [
  {
    zone: "White Space",
    className: "white-space",
    assets: [
      {
        id: "rack-a01",
        label: "Rack A01",
        metrics: [
          ["rack_temp_c", "Inlet"],
          ["rack_kw", "Load"],
        ],
      },
      {
        id: "rack-b02",
        label: "Rack B02",
        metrics: [
          ["rack_temp_c", "Inlet"],
          ["rack_kw", "Load"],
        ],
      },
    ],
  },
  {
    zone: "Cooling Plant",
    className: "cooling-plant",
    assets: [
      {
        id: "hvac-1",
        label: "HVAC 1",
        metrics: [
          ["hvac_supply_temp_c", "Supply"],
          ["hvac_return_temp_c", "Return"],
          ["hvac_fan_speed_pct", "Fan"],
        ],
      },
      {
        id: "hvac-2",
        label: "HVAC 2",
        metrics: [
          ["hvac_supply_temp_c", "Supply"],
          ["hvac_return_temp_c", "Return"],
          ["hvac_fan_speed_pct", "Fan"],
        ],
      },
    ],
  },
  {
    zone: "Electrical Room",
    className: "electrical-room",
    assets: [
      {
        id: "ups-1",
        label: "UPS 1",
        metrics: [
          ["ups_load_pct", "Load"],
          ["ups_battery_pct", "Battery"],
        ],
      },
      {
        id: "ups-2",
        label: "UPS 2",
        metrics: [
          ["ups_load_pct", "Load"],
          ["ups_battery_pct", "Battery"],
        ],
      },
      {
        id: "pdu-1",
        label: "PDU 1",
        metrics: [["pdu_branch_load_pct", "Branch"]],
      },
      {
        id: "pdu-2",
        label: "PDU 2",
        metrics: [["pdu_branch_load_pct", "Branch"]],
      },
    ],
  },
];

const CRITICAL_PARAMETERS = [
  ["rack-a01", "rack_temp_c", "Rack A inlet"],
  ["rack-b02", "rack_temp_c", "Rack B inlet"],
  ["hvac-1", "hvac_supply_temp_c", "HVAC 1 supply"],
  ["hvac-2", "hvac_supply_temp_c", "HVAC 2 supply"],
  ["ups-1", "ups_battery_pct", "UPS 1 battery"],
  ["ups-2", "ups_battery_pct", "UPS 2 battery"],
  ["pdu-1", "pdu_branch_load_pct", "PDU 1 branch"],
  ["pdu-2", "pdu_branch_load_pct", "PDU 2 branch"],
];

const METRIC_LABELS = {
  rack_temp_c: { label: "Inlet temp", kind: "Temperature" },
  rack_kw: { label: "Rack load", kind: "Power" },
  hvac_supply_temp_c: { label: "Supply air", kind: "Temperature" },
  hvac_return_temp_c: { label: "Return air", kind: "Temperature" },
  hvac_delta_temp_c: { label: "Return - supply", kind: "Temp delta" },
  hvac_fan_speed_pct: { label: "Fan speed", kind: "Airflow" },
  ups_load_pct: { label: "UPS load", kind: "Power" },
  ups_battery_pct: { label: "Battery", kind: "Reserve" },
  pdu_branch_load_pct: { label: "Branch load", kind: "Power" },
};

const SORT_LABELS = {
  ts: "Newest",
  severity: "Severity",
  asset_id: "Asset",
  metric: "Metric",
  state: "State",
  condition: "Condition",
  duration_seconds: "Duration",
};

function getStatusTone(alert) {
  if (alert.shelved) return "shelved";
  if (alert.muted) return "muted";
  if (alert.acknowledged) return "acknowledged";
  return "open";
}

function formatRelativeUntil(value) {
  if (!value) return "none";
  const end = new Date(value);
  return end.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatPoint(point) {
  if (!point) return "--";
  return `${Number(point.value).toFixed(1)} ${point.unit}`;
}

function statusLabel(status) {
  return status || "unknown";
}

function formatDateTime(value) {
  if (!value) return "--";
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatTime(value) {
  if (!value) return "--";
  return new Date(value).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}

function timeAgo(value) {
  if (!value) return "--";
  const elapsed = Math.max(0, Date.now() - new Date(value).getTime());
  const minutes = Math.floor(elapsed / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "--";
  const total = Math.max(0, Math.floor(Number(seconds)));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function severityRank(severity) {
  return { critical: 3, warning: 2, normal: 1 }[severity] || 0;
}

function metricInfo(metric) {
  return METRIC_LABELS[metric] || { label: metric, kind: "Process" };
}

async function readJson(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // keep the status text when the body is not JSON
    }
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json();
}

function buildLatestTelemetry(rows) {
  const latest = new Map();
  for (const row of rows) {
    const key = `${row.asset_id}:${row.metric}`;
    const current = latest.get(key);
    if (!current || new Date(row.ts) > new Date(current.ts)) {
      latest.set(key, row);
    }
  }
  return latest;
}

function buildTelemetrySeries(rows) {
  const series = new Map();
  for (const row of rows) {
    const key = `${row.asset_id}:${row.metric}`;
    const values = series.get(key) || [];
    values.push(row);
    series.set(key, values);
  }
  for (const values of series.values()) {
    values.sort((left, right) => new Date(left.ts) - new Date(right.ts));
  }
  return series;
}

function Sparkline({ points = [] }) {
  const values = points.slice(-28).map((point) => Number(point.value)).filter(Number.isFinite);
  if (values.length < 2) {
    return <div className="sparkline sparkline-empty" aria-hidden="true" />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 0.1);
  const coordinates = values.map((value, index) => {
    const x = (index / (values.length - 1)) * 100;
    const y = 28 - ((value - min) / span) * 24;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg className="sparkline" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={coordinates} />
    </svg>
  );
}

function makeDeltaPoint(supply, ret) {
  if (!supply || !ret) return null;
  const value = Number(ret.value) - Number(supply.value);
  return {
    value,
    unit: supply.unit,
    status: value >= 16 ? "warning" : "normal",
  };
}

function ProcessReadout({ point, metric, compact = false, trend = [] }) {
  const info = metricInfo(metric);
  return (
    <div className={`process-readout ${compact ? "compact" : ""} status-${point?.status || "unknown"}`}>
      <div>
        <span>{info.kind}</span>
        <strong>{formatPoint(point)}</strong>
        <small>{info.label}</small>
      </div>
      {!compact ? <Sparkline points={trend} /> : null}
    </div>
  );
}

function RackIntentBars({ tempPoint, loadPoint }) {
  const tempPct = Math.min(100, Math.max(0, (Number(tempPoint?.value || 0) / 38) * 100));
  const loadPct = Math.min(100, Math.max(0, (Number(loadPoint?.value || 0) / 9) * 100));
  return (
    <div className="rack-intent-bars">
      <div>
        <span>Thermal headroom</span>
        <i style={{ "--bar-value": `${tempPct}%` }} />
      </div>
      <div>
        <span>Power capacity</span>
        <i style={{ "--bar-value": `${loadPct}%` }} />
      </div>
    </div>
  );
}

function DataCenterOverview({ alerts, telemetryRows, scenarioState }) {
  const latestTelemetry = useMemo(() => buildLatestTelemetry(telemetryRows), [telemetryRows]);
  const telemetrySeries = useMemo(() => buildTelemetrySeries(telemetryRows), [telemetryRows]);
  const getPoint = (assetId, metric) => latestTelemetry.get(`${assetId}:${metric}`);
  const getTrend = (assetId, metric) => telemetrySeries.get(`${assetId}:${metric}`) || [];
  const liveAlarms = alerts.filter((alert) => alert.active_condition && !alert.acknowledged);
  const criticalCount = liveAlarms.filter((alert) => alert.severity === "critical").length;
  const worstStatus =
    criticalCount > 0
      ? "critical"
      : liveAlarms.some((alert) => alert.severity === "warning")
        ? "warning"
        : "normal";

  return (
    <>
      <section className="scada-hero">
        <div>
          <p className="eyebrow">Live Data Center Overview</p>
          <h2>2N plant status and critical process values.</h2>
        </div>
        <div className="plant-kpis">
          <div className={`plant-state plant-${worstStatus}`}>
            <span>Plant state</span>
            <strong>{worstStatus}</strong>
          </div>
          <div>
            <span>Open live alarms</span>
            <strong>{liveAlarms.length}</strong>
          </div>
          <div>
            <span>Scenario</span>
            <strong>{scenarioState.active ? scenarioState.scenario : "normal"}</strong>
          </div>
        </div>
      </section>

      <section className="process-strip" aria-label="Critical process values">
        {CRITICAL_PARAMETERS.map(([assetId, metric, label]) => (
          <article className="process-tile" key={`${assetId}:${metric}`}>
            <span>{label}</span>
            <ProcessReadout point={getPoint(assetId, metric)} metric={metric} trend={getTrend(assetId, metric)} />
          </article>
        ))}
      </section>

      <section className="scada-board" aria-label="Data center SCADA overview">
        <div className="pid-canvas">
          <div className="pid-zone electrical-source">
            <div className="zone-header">
              <h2>Electrical Room</h2>
              <span>UPS/PDU distribution</span>
            </div>
            <div className="equipment-row four-up">
              {[
                ["ups-1", "ups_load_pct", "ups_battery_pct", "UPS"],
                ["ups-2", "ups_load_pct", "ups_battery_pct", "UPS"],
                ["pdu-1", "pdu_branch_load_pct", null, "PDU"],
                ["pdu-2", "pdu_branch_load_pct", null, "PDU"],
              ].map(([assetId, primaryMetric, secondaryMetric, assetType]) => (
                <article className="equipment-symbol power-symbol" key={assetId}>
                  <div className="symbol-topline">
                    <strong>{assetId.toUpperCase()}</strong>
                    <span>{assetType}</span>
                  </div>
                  <ProcessReadout point={getPoint(assetId, primaryMetric)} metric={primaryMetric} compact />
                  {secondaryMetric ? (
                    <ProcessReadout point={getPoint(assetId, secondaryMetric)} metric={secondaryMetric} compact />
                  ) : null}
                </article>
              ))}
            </div>
          </div>

          <div className="flow-lane power-lane">
            <span>UPS to PDU</span>
            <div className="flow-line power-a" />
            <span>PDU to racks</span>
            <div className="flow-line power-b" />
          </div>

          <div className="pid-zone white-space-zone">
            <div className="zone-header">
              <h2>White Space</h2>
              <span>Critical IT load</span>
            </div>
            <div className="rack-row">
              {["rack-a01", "rack-b02"].map((assetId) => (
                <article className="equipment-symbol rack-symbol" key={assetId}>
                  <RackIntentBars
                    tempPoint={getPoint(assetId, "rack_temp_c")}
                    loadPoint={getPoint(assetId, "rack_kw")}
                  />
                  <div className="symbol-topline">
                    <strong>{assetId.toUpperCase()}</strong>
                    <span>Rack</span>
                  </div>
                  <ProcessReadout point={getPoint(assetId, "rack_temp_c")} metric="rack_temp_c" compact />
                  <ProcessReadout point={getPoint(assetId, "rack_kw")} metric="rack_kw" compact />
                </article>
              ))}
            </div>
          </div>

          <div className="flow-lane cooling-lane">
            <span>Supply air</span>
            <div className="flow-line air-supply reverse" />
            <span>Return air</span>
            <div className="flow-line air-return reverse" />
          </div>

          <div className="pid-zone cooling-source">
            <div className="zone-header">
              <h2>Cooling Plant</h2>
              <span>CHW/Air path</span>
            </div>
            <div className="equipment-row">
              {["hvac-1", "hvac-2"].map((assetId) => {
                const supply = getPoint(assetId, "hvac_supply_temp_c");
                const ret = getPoint(assetId, "hvac_return_temp_c");
                return (
                <article className="equipment-symbol ahu-symbol" key={assetId}>
                  <div className="symbol-topline">
                    <strong>{assetId.toUpperCase()}</strong>
                    <span>Air handler</span>
                  </div>
                  <ProcessReadout point={supply} metric="hvac_supply_temp_c" compact />
                  <ProcessReadout point={ret} metric="hvac_return_temp_c" compact />
                  <ProcessReadout point={makeDeltaPoint(supply, ret)} metric="hvac_delta_temp_c" compact />
                  <ProcessReadout point={getPoint(assetId, "hvac_fan_speed_pct")} metric="hvac_fan_speed_pct" compact />
                </article>
              );
              })}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}

function AlarmHistory({ alerts, lastUpdatedAt }) {
  const [historySearch, setHistorySearch] = useState("");
  const [historySeverity, setHistorySeverity] = useState("all");
  const [historyCondition, setHistoryCondition] = useState("all");
  const [historyState, setHistoryState] = useState("all");
  const [historyWindow, setHistoryWindow] = useState("30d");
  const [sortKey, setSortKey] = useState("ts");
  const [sortDirection, setSortDirection] = useState("desc");
  const [selectedAcknowledgement, setSelectedAcknowledgement] = useState(null);
  const [nowMs, setNowMs] = useState(Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const rows = useMemo(() => {
    const search = historySearch.trim().toLowerCase();
    const windowStart =
      {
        "1h": nowMs - 60 * 60 * 1000,
        "24h": nowMs - 24 * 60 * 60 * 1000,
        "7d": nowMs - 7 * 24 * 60 * 60 * 1000,
        "30d": nowMs - 30 * 24 * 60 * 60 * 1000,
        all: 0,
      }[historyWindow] || 0;
    return [...alerts]
      .filter((alert) => {
        const tone = getStatusTone(alert);
        const condition = alert.active_condition === false ? "cleared" : "active";
        const eventTime = new Date(alert.ts).getTime();
        const matchesSearch =
          !search ||
          alert.alert_key.toLowerCase().includes(search) ||
          alert.asset_id.toLowerCase().includes(search) ||
          alert.metric.toLowerCase().includes(search) ||
          alert.message.toLowerCase().includes(search);
        return (
          matchesSearch &&
          (!windowStart || eventTime >= windowStart) &&
          (historySeverity === "all" || alert.severity === historySeverity) &&
          (historyCondition === "all" || condition === historyCondition) &&
          (historyState === "all" || tone === historyState)
        );
      })
      .sort((left, right) => {
        let leftValue;
        let rightValue;
        if (sortKey === "ts") {
          leftValue = new Date(left.ts).getTime();
          rightValue = new Date(right.ts).getTime();
        } else if (sortKey === "severity") {
          leftValue = severityRank(left.severity);
          rightValue = severityRank(right.severity);
        } else if (sortKey === "state") {
          leftValue = getStatusTone(left);
          rightValue = getStatusTone(right);
        } else if (sortKey === "condition") {
          leftValue = left.active_condition === false ? "cleared" : "active";
          rightValue = right.active_condition === false ? "cleared" : "active";
        } else if (sortKey === "duration_seconds") {
          leftValue = Number(left.duration_seconds) || 0;
          rightValue = Number(right.duration_seconds) || 0;
        } else {
          leftValue = left[sortKey] || "";
          rightValue = right[sortKey] || "";
        }
        const comparison =
          typeof leftValue === "number"
            ? leftValue - rightValue
            : String(leftValue).localeCompare(String(rightValue));
        return sortDirection === "asc" ? comparison : comparison * -1;
      });
  }, [alerts, historyCondition, historySearch, historySeverity, historyState, historyWindow, nowMs, sortDirection, sortKey]);

  function updateSort(nextKey) {
    if (nextKey === sortKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(nextKey);
    setSortDirection(nextKey === "ts" || nextKey === "severity" || nextKey === "duration_seconds" ? "desc" : "asc");
  }

  function durationFor(alert) {
    if (alert.active_condition === false) return alert.duration_seconds;
    const start = new Date(alert.start_ts || alert.ts).getTime();
    return Math.max(0, Math.floor((nowMs - start) / 1000));
  }

  return (
    <section className="history-page">
      <div className="card-header">
        <div>
          <p className="eyebrow">Alarm History</p>
          <h2>Sortable alarm event ledger.</h2>
          <p>Review recent events by asset, severity, operator state, and whether the source condition is still active.</p>
        </div>
        <div className="history-count">
          <span>Rows</span>
          <strong>{rows.length}</strong>
        </div>
        <div className="history-live-card">
          <span>Live refresh</span>
          <strong>5s</strong>
          <small>Updated {formatTime(lastUpdatedAt)}</small>
        </div>
      </div>

      <div className="history-toolbar">
        <label className="field field-wide">
          <span>Search</span>
          <input
            value={historySearch}
            onChange={(event) => setHistorySearch(event.target.value)}
            placeholder="asset, metric, key, message"
          />
        </label>
        <label className="field">
          <span>Severity</span>
          <select value={historySeverity} onChange={(event) => setHistorySeverity(event.target.value)}>
            <option value="all">All</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
          </select>
        </label>
        <label className="field">
          <span>Condition</span>
          <select value={historyCondition} onChange={(event) => setHistoryCondition(event.target.value)}>
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="cleared">Cleared</option>
          </select>
        </label>
        <label className="field">
          <span>State</span>
          <select value={historyState} onChange={(event) => setHistoryState(event.target.value)}>
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="acknowledged">Acknowledged</option>
            <option value="muted">Muted</option>
            <option value="shelved">Shelved</option>
          </select>
        </label>
        <label className="field">
          <span>Time window</span>
          <select value={historyWindow} onChange={(event) => setHistoryWindow(event.target.value)}>
            <option value="1h">Last hour</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="all">All history</option>
          </select>
        </label>
      </div>

      <div className="history-sortbar">
        {Object.entries(SORT_LABELS).map(([key, label]) => (
          <button
            className={sortKey === key ? "active" : ""}
            key={key}
            onClick={() => updateSort(key)}
          >
            {label}
            {sortKey === key ? ` ${sortDirection === "asc" ? "up" : "down"}` : ""}
          </button>
        ))}
      </div>

      <div className="history-table-wrap">
        <table className="history-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Start</th>
              <th>End</th>
              <th>Duration</th>
              <th>Asset</th>
              <th>Metric</th>
              <th>Severity</th>
              <th>State</th>
              <th>Condition</th>
              <th>Value</th>
              <th>Ack</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((alert) => {
              const tone = getStatusTone(alert);
              const conditionTone = alert.active_condition === false ? "cleared" : "active";
              return (
                <tr key={`${alert.alert_key}-${alert.ts}`}>
                  <td>{formatDateTime(alert.ts)}</td>
                  <td>{formatDateTime(alert.start_ts || alert.ts)}</td>
                  <td>{alert.active_condition === false ? formatDateTime(alert.end_ts) : "Active"}</td>
                  <td>{formatDuration(durationFor(alert))}</td>
                  <td>{alert.asset_id}</td>
                  <td>
                    <span>{metricInfo(alert.metric).label}</span>
                    <small>{alert.metric}</small>
                  </td>
                  <td><span className={`pill pill-${alert.severity}`}>{alert.severity}</span></td>
                  <td><span className={`pill pill-${tone}`}>{tone}</span></td>
                  <td><span className={`pill pill-${conditionTone}`}>{conditionTone}</span></td>
                  <td>{Number(alert.latest_value ?? alert.current_value).toFixed(1)} {alert.latest_unit || ""}</td>
                  <td>
                    {alert.acknowledgement ? (
                      <button className="details-button" onClick={() => setSelectedAcknowledgement(alert)}>
                        View note
                      </button>
                    ) : (
                      <span className="muted-text">None</span>
                    )}
                  </td>
                  <td>{alert.message}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {selectedAcknowledgement ? (
        <div className="modal-backdrop" role="presentation">
          <section className="action-modal" role="dialog" aria-modal="true" aria-labelledby="ack-modal-title">
            <div className="card-header">
              <div>
                <h2 id="ack-modal-title">Acknowledgement detail</h2>
                <p>
                  {selectedAcknowledgement.asset_id} on <strong>{selectedAcknowledgement.metric}</strong>
                </p>
              </div>
            </div>
            <dl className="ack-detail-list">
              <div>
                <dt>Operator</dt>
                <dd>{selectedAcknowledgement.acknowledgement.actor || "unknown"}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{formatDateTime(selectedAcknowledgement.acknowledgement.ts)}</dd>
              </div>
              <div>
                <dt>Note</dt>
                <dd>{selectedAcknowledgement.acknowledgement.note || "No note recorded."}</dd>
              </div>
            </dl>
            <div className="modal-actions">
              <button className="ghost-button" onClick={() => setSelectedAcknowledgement(null)}>
                Close
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [telemetryRows, setTelemetryRows] = useState([]);
  const [scenarioState, setScenarioState] = useState({ active: false, scenario: null });
  const [activeView, setActiveView] = useState("console");
  const [autoClearRectified, setAutoClearRectified] = useState(true);
  const [scenarioDurationSeconds, setScenarioDurationSeconds] = useState("60");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [stateFilter, setStateFilter] = useState("all");
  const [assetFilter, setAssetFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState("");
  const [banner, setBanner] = useState({ tone: "neutral", text: "Console ready." });
  const [pendingAction, setPendingAction] = useState(null);
  const [actionActor, setActionActor] = useState("operator");
  const [actionNote, setActionNote] = useState("");
  const [actionDuration, setActionDuration] = useState("30");
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);

  const deferredAssetFilter = useDeferredValue(assetFilter);

  async function refreshDashboard() {
    const [summaryPayload, alertsPayload, scenarioPayload, telemetryPayload] = await Promise.all([
      readJson("/summary"),
      readJson("/alerts/recent?limit=250"),
      readJson("/simulator/scenario"),
      readJson("/telemetry/recent?limit=200"),
    ]);

    startTransition(() => {
      setSummary(summaryPayload);
      setAlerts(alertsPayload.rows || []);
      setScenarioState(scenarioPayload);
      setTelemetryRows(telemetryPayload.rows || []);
      setLastUpdatedAt(new Date().toISOString());
      setLoading(false);
    });
  }

  useEffect(() => {
    refreshDashboard()
      .then(() => {
        setBanner({ tone: "success", text: "Live console connected to API and Grafana." });
      })
      .catch((error) => {
        setLoading(false);
        setBanner({ tone: "danger", text: error.message });
      });

    const timer = window.setInterval(() => {
      refreshDashboard().catch((error) => {
        setBanner({ tone: "danger", text: error.message });
      });
    }, REFRESH_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, []);

  const visibleAlerts = alerts.filter((alert) => {
    const tone = getStatusTone(alert);
    const autoCleared =
      autoClearRectified &&
      stateFilter !== "cleared" &&
      stateFilter !== "cleared-unacknowledged" &&
      alert.active_condition === false;
    const matchesSeverity =
      severityFilter === "all" || alert.severity === severityFilter;
    const matchesState =
      stateFilter === "all" ||
      tone === stateFilter ||
      (stateFilter === "cleared" && alert.active_condition === false) ||
      (stateFilter === "cleared-unacknowledged" && alert.active_condition === false && !alert.acknowledged);
    const matchesAsset =
      deferredAssetFilter.trim() === "" ||
      alert.asset_id.toLowerCase().includes(deferredAssetFilter.trim().toLowerCase()) ||
      alert.metric.toLowerCase().includes(deferredAssetFilter.trim().toLowerCase());
    return !autoCleared && matchesSeverity && matchesState && matchesAsset;
  });

  const activeAlertsByKey = new Map();
  for (const alert of alerts) {
    if (alert.active_condition !== false && !alert.acknowledged && !alert.muted && !alert.shelved) {
      activeAlertsByKey.set(alert.alert_key, alert);
    }
  }
  const activeAlerts = Array.from(activeAlertsByKey.values());

  const overviewStats = {
    critical: 0,
    warning: 0,
    acknowledged: 0,
    suppressed: 0,
    cleared: 0,
  };
  for (const alert of alerts) {
    if (alert.active_condition === false) overviewStats.cleared += 1;
    if (alert.severity === "critical" && alert.active_condition !== false) overviewStats.critical += 1;
    if (alert.severity === "warning" && alert.active_condition !== false) overviewStats.warning += 1;
    if (alert.acknowledged) overviewStats.acknowledged += 1;
    if (alert.muted || alert.shelved) overviewStats.suppressed += 1;
  }

  const assetInventory = summary?.asset_inventory || [];
  const clearedUnacknowledged = alerts.filter((alert) => alert.active_condition === false && !alert.acknowledged);
  const telemetryStatusCounts = telemetryRows.reduce(
    (counts, row) => {
      counts[row.status] = (counts[row.status] || 0) + 1;
      return counts;
    },
    { normal: 0, warning: 0, critical: 0 }
  );
  const latestTelemetryTs = telemetryRows.reduce((latest, row) => {
    if (!latest || new Date(row.ts) > new Date(latest)) return row.ts;
    return latest;
  }, null);
  const totalAssets = assetInventory.reduce((total, asset) => total + Number(asset.asset_count || 0), 0);

  async function triggerScenario(scenario) {
    const durationSeconds = Math.min(
      600,
      Math.max(5, Number(scenarioDurationSeconds) || scenario.durationSeconds)
    );
    setBusyKey(`scenario:${scenario.key}`);
    try {
      await readJson(`/simulator/scenarios/${scenario.key}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ duration_seconds: durationSeconds }),
      });
      await refreshDashboard();
      setBanner({
        tone: "success",
        text: `${scenario.title} started for ${durationSeconds} seconds.`,
      });
    } catch (error) {
      setBanner({ tone: "danger", text: error.message });
    } finally {
      setBusyKey("");
    }
  }

  function openActionModal(alert, action) {
    const defaultDuration = action === "shelve" ? "120" : "30";
    setActionActor("operator");
    setActionNote("");
    setActionDuration(defaultDuration);
    setPendingAction({ alert, action });
  }

  function openAcknowledgeAllModal() {
    if (activeAlerts.length === 0) {
      setBanner({
        tone: "neutral",
        text: "There are no active alarms that still need acknowledgment.",
      });
      return;
    }

    setActionActor("operator");
    setActionNote("");
    setActionDuration("30");
    setPendingAction({ action: "acknowledge-all", alerts: activeAlerts });
  }

  function closeActionModal() {
    if (busyKey) {
      return;
    }
    setPendingAction(null);
  }

  async function confirmAlertAction() {
    if (!pendingAction) {
      return;
    }

    if (!actionActor.trim() || !actionNote.trim()) {
      setBanner({
        tone: "danger",
        text: "Operator name and action note are required before changing an alarm state.",
      });
      return;
    }

    const { alert, action } = pendingAction;
    const payload = {
      actor: actionActor.trim(),
      note: actionNote.trim(),
    };

    if (action === "acknowledge-all") {
      setBusyKey("acknowledge-all");
      try {
        await Promise.all(
          pendingAction.alerts.map((activeAlert) =>
            readJson(`/alerts/${encodeURIComponent(activeAlert.alert_key)}/acknowledge`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            })
          )
        );
        await refreshDashboard();
        setBanner({
          tone: "success",
          text: `Acknowledged ${pendingAction.alerts.length} active alarm${pendingAction.alerts.length === 1 ? "" : "s"}.`,
        });
        setPendingAction(null);
      } catch (error) {
        setBanner({ tone: "danger", text: error.message });
      } finally {
        setBusyKey("");
      }
      return;
    }

    const alertKey = encodeURIComponent(alert.alert_key);
    const path = `/alerts/${alertKey}/${action}`;

    if (action === "mute") {
      payload.duration_minutes = Number(actionDuration) || 30;
    }
    if (action === "shelve") {
      payload.duration_minutes = Number(actionDuration) || 120;
    }

    setBusyKey(`${action}:${alert.alert_key}`);
    try {
      await readJson(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await refreshDashboard();
      setBanner({
        tone: "success",
        text: `${action} completed for ${alert.asset_id}.`,
      });
      setPendingAction(null);
    } catch (error) {
      setBanner({ tone: "danger", text: error.message });
    } finally {
      setBusyKey("");
    }
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <header className="hero">
        <div>
          <p className="eyebrow">DC Twin Operator Console</p>
          <h1>Supervisory control with a sharper surface.</h1>
          <p className="hero-copy">
            A Tesla-inspired control room for live telemetry, fast alarm action, and scenario-driven
            testing across a 2N data center model.
          </p>
        </div>
        <div className="hero-status">
          <div className="hero-brand-panel" aria-label="System topology snapshot">
            <div className="brand-panel-header">
              <span>2N Digital Twin</span>
              <strong>{activeAlerts.length === 0 ? "Stable" : `${activeAlerts.length} live`}</strong>
            </div>
            <div className="brand-lanes">
              <div className="brand-lane">
                <i>UPS A</i>
                <b />
                <i>PDU A</i>
                <b />
                <i>Rack A</i>
              </div>
              <div className="brand-lane">
                <i>UPS B</i>
                <b />
                <i>PDU B</i>
                <b />
                <i>Rack B</i>
              </div>
              <div className="brand-lane cooling">
                <i>HVAC</i>
                <b />
                <i>White Space</i>
              </div>
            </div>
          </div>
          <div className={`banner banner-${banner.tone}`}>{banner.text}</div>
          <div className="scenario-chip">
            <span>Scenario</span>
            <strong>{scenarioState.active ? scenarioState.scenario : "Normal Operations"}</strong>
          </div>
        </div>
      </header>

      <nav className="view-tabs" aria-label="Console views">
        <button
          className={activeView === "console" ? "active" : ""}
          onClick={() => setActiveView("console")}
        >
          Operator Console
        </button>
        <button
          className={activeView === "overview" ? "active" : ""}
          onClick={() => setActiveView("overview")}
        >
          Data Center Overview
        </button>
        <button
          className={activeView === "history" ? "active" : ""}
          onClick={() => setActiveView("history")}
        >
          Alarm History
        </button>
      </nav>

      {activeView === "overview" ? (
        <DataCenterOverview
          alerts={alerts}
          telemetryRows={telemetryRows}
          scenarioState={scenarioState}
        />
      ) : activeView === "history" ? (
        <AlarmHistory alerts={alerts} lastUpdatedAt={lastUpdatedAt} />
      ) : (
        <>
          <section className="summary-grid">
            <article className="summary-card summary-hot">
              <span>Live critical</span>
              <strong>{overviewStats.critical}</strong>
              <small>Condition still active</small>
            </article>
            <article className="summary-card">
              <span>Live warning</span>
              <strong>{overviewStats.warning}</strong>
              <small>Current warning conditions</small>
            </article>
            <article className="summary-card">
              <span>Acknowledged</span>
              <strong>{overviewStats.acknowledged}</strong>
              <small>Tracked by an operator</small>
            </article>
            <article className="summary-card">
              <span>Cleared</span>
              <strong>{overviewStats.cleared}</strong>
              <small>Condition returned normal</small>
            </article>
          </section>

          <section className="layout-grid">
            <div className="panel-grid">
              {EMBEDS.map((panel) => (
                <article className="embed-card" key={panel.title}>
                  <div className="card-header">
                    <div>
                      <h2>{panel.title}</h2>
                      <p>{panel.subtitle}</p>
                    </div>
                    <span className="micro-pill">Grafana</span>
                  </div>
                  <iframe
                    className="grafana-frame"
                    src={panel.src}
                    title={panel.title}
                    loading="lazy"
                  />
                </article>
              ))}
              <article className="embed-card insight-card">
                <div className="card-header">
                  <div>
                    <h2>Operator focus</h2>
                    <p>Practical next actions from the live alarm and telemetry stream.</p>
                  </div>
                  <span className="micro-pill">Live</span>
                </div>
                <div className="insight-grid">
                  <div>
                    <span>Closeout queue</span>
                    <strong>{clearedUnacknowledged.length}</strong>
                    <small>Cleared, needs note</small>
                  </div>
                  <div>
                    <span>Active alarms</span>
                    <strong>{activeAlerts.length}</strong>
                    <small>Open operator work</small>
                  </div>
                  <div>
                    <span>Suppressed</span>
                    <strong>{overviewStats.suppressed}</strong>
                    <small>Muted or shelved</small>
                  </div>
                  <div>
                    <span>Telemetry points</span>
                    <strong>{telemetryRows.length}</strong>
                    <small>Recent samples</small>
                  </div>
                </div>
                <div className="focus-list">
                  {clearedUnacknowledged.slice(0, 3).map((alert) => (
                    <div key={`${alert.alert_key}-${alert.ts}`}>
                      <span>{alert.asset_id}</span>
                      <strong>{metricInfo(alert.metric).label}</strong>
                      <small>{formatDuration(alert.duration_seconds)} event</small>
                    </div>
                  ))}
                  {clearedUnacknowledged.length === 0 ? (
                    <div>
                      <span>Queue clear</span>
                      <strong>No cleared alarms waiting on closeout</strong>
                      <small>Operators are caught up</small>
                    </div>
                  ) : null}
                </div>
              </article>
            </div>

            <aside className="side-rail">
              <section className="control-card">
                <div className="card-header">
                  <div>
                    <h2>Scenario controls</h2>
                    <p>Drive the simulator into known operating stories.</p>
                  </div>
                </div>
                <label className="field scenario-duration-field">
                  <span>Duration (seconds)</span>
                  <input
                    type="number"
                    min="5"
                    max="600"
                    step="5"
                    value={scenarioDurationSeconds}
                    onChange={(event) => setScenarioDurationSeconds(event.target.value)}
                  />
                </label>
                <div className="scenario-list">
                  {SCENARIOS.map((scenario) => (
                    <button
                      key={scenario.key}
                      className="scenario-button"
                      onClick={() => triggerScenario(scenario)}
                      disabled={busyKey === `scenario:${scenario.key}`}
                    >
                      <span>{scenario.title}</span>
                      <small>{scenario.description}</small>
                      <em>{Math.min(600, Math.max(5, Number(scenarioDurationSeconds) || scenario.durationSeconds))}s run</em>
                    </button>
                  ))}
                </div>
              </section>

              <section className="control-card">
                <div className="card-header">
                  <div>
                    <h2>Facility inventory</h2>
                    <p>Quick inventory snapshot pulled from the API summary endpoint.</p>
                  </div>
                </div>
                <div className="inventory-strip">
                  {assetInventory.map((asset) => (
                    <div className="inventory-chip" key={asset.asset_type}>
                      <strong>{asset.asset_count}</strong>
                      <span>{asset.asset_type}</span>
                    </div>
                  ))}
                </div>
                <div className="inventory-metrics">
                  <div>
                    <span>Total assets</span>
                    <strong>{totalAssets}</strong>
                  </div>
                  <div>
                    <span>Telemetry points</span>
                    <strong>{telemetryRows.length}</strong>
                  </div>
                  <div>
                    <span>Normal samples</span>
                    <strong>{telemetryStatusCounts.normal || 0}</strong>
                  </div>
                  <div>
                    <span>Warning samples</span>
                    <strong>{telemetryStatusCounts.warning || 0}</strong>
                  </div>
                  <div>
                    <span>Critical samples</span>
                    <strong>{telemetryStatusCounts.critical || 0}</strong>
                  </div>
                  <div>
                    <span>Last telemetry</span>
                    <strong>{timeAgo(latestTelemetryTs)}</strong>
                  </div>
                </div>
              </section>
            </aside>
          </section>

          <section className="alarm-section">
            <div className="card-header">
              <div>
                <h2>Alarm command surface</h2>
                <p>Filter recent alerts, then acknowledge, mute, or shelve directly from the console.</p>
              </div>
              <div className="header-actions">
                <label className="toggle-control">
                  <input
                    type="checkbox"
                    checked={autoClearRectified}
                    onChange={(event) => setAutoClearRectified(event.target.checked)}
                  />
                  <span>Auto-clear rectified</span>
                </label>
                <button className="ghost-button" onClick={openAcknowledgeAllModal} disabled={loading || activeAlerts.length === 0}>
                  Acknowledge all active
                </button>
                <button className="ghost-button" onClick={() => refreshDashboard()} disabled={loading}>
                  Refresh now
                </button>
              </div>
            </div>

            <div className="filters">
              <label className="field">
                <span>Severity</span>
                <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
                  <option value="all">All</option>
                  <option value="critical">Critical</option>
                  <option value="warning">Warning</option>
                </select>
              </label>
              <label className="field">
                <span>State</span>
                <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}>
                  <option value="all">All</option>
                  <option value="open">Open</option>
                  <option value="acknowledged">Acknowledged</option>
                  <option value="muted">Muted</option>
                  <option value="shelved">Shelved</option>
                  <option value="cleared">Cleared</option>
                  <option value="cleared-unacknowledged">Cleared, needs closeout</option>
                </select>
              </label>
              <label className="field field-wide">
                <span>Asset or metric</span>
                <input
                  value={assetFilter}
                  onChange={(event) => setAssetFilter(event.target.value)}
                  placeholder="rack-a01, hvac, ups_battery_pct"
                />
              </label>
            </div>

            {loading ? (
              <div className="empty-state">Loading the control surface...</div>
            ) : visibleAlerts.length === 0 ? (
              <div className="empty-state">No alerts match the current filters.</div>
            ) : (
              <div className="alarm-list">
                {visibleAlerts.map((alert) => {
                  const tone = getStatusTone(alert);
                  const conditionTone = alert.active_condition === false ? "cleared" : "active";
                  return (
                    <article className={`alarm-card alarm-${alert.severity}`} key={`${alert.alert_key}-${alert.ts}`}>
                      <div className="alarm-header">
                        <div>
                          <div className="alarm-tags">
                            <span className={`pill pill-${alert.severity}`}>{alert.severity}</span>
                            <span className={`pill pill-${tone}`}>{tone}</span>
                            <span className={`pill pill-${conditionTone}`}>{conditionTone}</span>
                          </div>
                          <h3>{alert.asset_id}</h3>
                          <p>{alert.message}</p>
                        </div>
                        <div className="alarm-reading">
                          <strong>{Number(alert.latest_value ?? alert.current_value).toFixed(1)}</strong>
                          <span>{alert.metric}</span>
                          <small>limit {Number(alert.threshold_value).toFixed(1)}</small>
                        </div>
                      </div>

                      <div className="alarm-meta">
                        <span>Key: {alert.alert_key}</span>
                        <span>Observed {alert.observation_count}x</span>
                        <span>Condition {alert.condition_status || "unknown"}</span>
                        <span>Muted until {formatRelativeUntil(alert.muted_until)}</span>
                        <span>Shelved until {formatRelativeUntil(alert.shelved_until)}</span>
                      </div>

                      <div className="alarm-actions">
                        <button
                          onClick={() => openActionModal(alert, "acknowledge")}
                          disabled={busyKey === `acknowledge:${alert.alert_key}`}
                        >
                          Acknowledge
                        </button>
                        <button
                          onClick={() => openActionModal(alert, alert.muted ? "unmute" : "mute")}
                          disabled={busyKey === `${alert.muted ? "unmute" : "mute"}:${alert.alert_key}`}
                        >
                          {alert.muted ? "Unmute" : "Mute 30m"}
                        </button>
                        <button
                          onClick={() => openActionModal(alert, alert.shelved ? "unshelve" : "shelve")}
                          disabled={busyKey === `${alert.shelved ? "unshelve" : "shelve"}:${alert.alert_key}`}
                        >
                          {alert.shelved ? "Unshelve" : "Shelve 2h"}
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </>
      )}

      {pendingAction ? (
        <div className="modal-backdrop" role="presentation">
          <section className="action-modal" role="dialog" aria-modal="true" aria-labelledby="action-modal-title">
            <div className="card-header">
              <div>
                <h2 id="action-modal-title">Operator confirmation required</h2>
                <p>
                  {pendingAction.action === "acknowledge-all" ? (
                    <>
                      acknowledge <strong>{pendingAction.alerts.length}</strong> active alarm
                      {pendingAction.alerts.length === 1 ? "" : "s"} with one operator note.
                    </>
                  ) : (
                    <>
                      {pendingAction.action} for <strong>{pendingAction.alert.asset_id}</strong> on{" "}
                      <strong>{pendingAction.alert.metric}</strong>.
                    </>
                  )}
                </p>
              </div>
            </div>

            <label className="field">
              <span>Operator</span>
              <input
                value={actionActor}
                onChange={(event) => setActionActor(event.target.value)}
                placeholder="Jane operator"
              />
            </label>

            <label className="field">
              <span>Action note</span>
              <input
                value={actionNote}
                onChange={(event) => setActionNote(event.target.value)}
                placeholder="Why this alarm state is being changed"
              />
            </label>

            {pendingAction.action === "mute" || pendingAction.action === "shelve" ? (
              <label className="field">
                <span>Duration (minutes)</span>
                <input
                  type="number"
                  min="1"
                  max={pendingAction.action === "mute" ? "1440" : "10080"}
                  value={actionDuration}
                  onChange={(event) => setActionDuration(event.target.value)}
                />
              </label>
            ) : null}

            <div className="modal-actions">
              <button className="ghost-button" onClick={closeActionModal} disabled={Boolean(busyKey)}>
                Cancel
              </button>
              <button onClick={confirmAlertAction} disabled={Boolean(busyKey)}>
                Confirm {pendingAction.action === "acknowledge-all" ? "acknowledge all" : pendingAction.action}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
