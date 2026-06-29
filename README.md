# DataCenterDigitalTwin
Test project for mocking a digital twin for a data center and using it as a playground for testing data analysis methods.

The runnable stack lives in `mini-dc-digital-twin/`. It includes the Python services, MQTT, ClickHouse, Prometheus, Grafana, and the dockerized React operator console.

```bash
cd mini-dc-digital-twin
cp .env.example .env
docker compose up -d --build
```

See `mini-dc-digital-twin/README.md` for endpoint details and local development notes.
