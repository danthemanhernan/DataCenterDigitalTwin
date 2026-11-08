# DataCenterDigitalTwin local telemetry stack

1. Export **twin-run.json** from the Site’s Telemetry page and put it in `data/twin-run.json`. To generate events with the Python plant, export **twin-config.json** from Model editor and run `python3 plant.py twin-config.json data/twin-run.json`.
2. Start Docker Desktop or Docker Engine with Compose, then run `docker compose up -d --build`.
3. Wait for `curl -fsS http://localhost:8000/health` to succeed. Run `docker compose run --rm --build replay`.
4. Read accepted rows at `http://localhost:8000/telemetry`, FastAPI docs at `http://localhost:8000/docs`, and rules at `http://localhost:9090/alerts`. Open Grafana at `http://localhost:3000` with its initial local login and open the **Twin telemetry** dashboard.
5. Replay the same run twice. The run hash and event ID stay stable, so the API's `FINAL` query shows the same unique rows. The Prometheus ingest counter counts successful writes, including duplicate attempts. Browse ClickHouse with `docker compose exec clickhouse clickhouse-client --user twin --password twin-lab-local`.
6. To make a simulated MQTT outage visible in wall-clock time, export an outage run and replay with `docker compose run --rm replay python replay.py /data/twin-run.json --seconds-per-minute 2`. The alert uses receipt age, so any completed replay eventually becomes stale.
7. Stop with `docker compose down`. The named ClickHouse volume keeps the local history.

The Site computes a simplified thermal and electrical simulation. The Python plant generates the same telemetry fields from an exported configuration, and the replay process publishes the resulting packets into a local broker. Its anonymous broker and fixed ClickHouse credentials are intended for the internal Compose network. The gateway acknowledges rows after a successful insert or after exhausting a bounded retry budget, so the write-failure counter is part of the exercise. Add authentication, durable retry or quarantine, and retention before adapting this starter to a shared environment.

The telemetry payload is retained as JSON. For the dbt lab, extract typed fields with ClickHouse JSON functions, preserving the distinction between missing and zero. Use `run_id` plus `event_id` as your uniqueness key.
