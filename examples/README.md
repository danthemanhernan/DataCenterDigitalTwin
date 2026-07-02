# Examples

This directory holds copyable inputs for local demos and smoke checks. Keep examples free of secrets and environment-specific hostnames unless the file name makes the intended local use explicit.

## Local Stack Environment

Use `local-stack/lab-demo.env.example` as a more annotated starting point when you want a demo `.env` for `deploy/compose/`:

```bash
cp examples/local-stack/lab-demo.env.example deploy/compose/.env
cd deploy/compose
docker compose up -d --build
```

## Simulator Scenario Payloads

Trigger built-in simulator scenarios with the JSON request bodies under `simulator-scenarios/`:

```bash
curl -X POST http://localhost:8000/simulator/scenarios/power-outage \
  -H "Content-Type: application/json" \
  --data @examples/simulator-scenarios/power-outage.json
```

Available payloads:

- `simulator-scenarios/power-outage.json`
- `simulator-scenarios/cooling-degradation.json`
- `simulator-scenarios/load-transfer.json`
