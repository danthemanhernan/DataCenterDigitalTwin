# Data Center Control Lab

This standalone React/Vite workspace runs a simplified cooling, power, and telemetry model in the browser. Use it for parameter sweeps, fault injection, normal-versus-fault comparisons, and guided labs. The main repository's operator console is the interface for the deployed local twin.

## Run locally

With Node.js 22 and npm:

```bash
npm ci
npm test
npm run dev -- --host 127.0.0.1 --port 5174
```

Open http://localhost:5174. Run `npm run build` to produce a static deployment in `dist/`. Configuration snapshots, run history, and lab progress are saved per browser and origin. Use **Portfolio → Back up workspace** on the hosted Site, then **Import backup or config** locally to transfer them.

## Local telemetry exercises

The [reference stack](stack/README.md) can generate Python telemetry or replay a run export through its own MQTT, ClickHouse, FastAPI, Prometheus, and Grafana services. Run it separately from the monorepo Compose stack when their host ports overlap. The browser lab uses its own model and packet contract.
