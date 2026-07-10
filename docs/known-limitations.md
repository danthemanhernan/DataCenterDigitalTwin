# Known Limitations

This project is a local digital-twin lab, not a production control system. These limitations are intentional for the current phase and should be reviewed before presenting the repository as deployable infrastructure.

## Runtime Scope

- The stack is designed for local Docker Compose operation.
- Kubernetes, Helm, cloud networking, managed secrets, and production deployment automation are later roadmap phases.
- Compose builds `mini-dc-app:latest` and `mini-dc-frontend:latest` locally instead of pulling immutable registry images.

## Data Durability

- ClickHouse and Grafana use local Docker volumes.
- Resetting volumes removes telemetry history, alert history, and Grafana runtime state.
- Database migrations are simple SQL bootstrap files, not a versioned migration framework.

## Security

- Local credentials are development defaults in `.env.example`.
- Grafana anonymous viewer access is enabled for local demo convenience.
- MQTT is exposed without TLS or authentication in the local stack.
- Secrets are not managed through a vault, cloud secret manager, or encrypted repository workflow.

## Simulation Fidelity

- Telemetry is synthetic and rule-driven.
- The simulator is useful for workflow practice and dashboard validation, but it is not calibrated against a real facility.
- The maintenance-risk model is a lightweight heuristic baseline, not a trained or validated predictive-maintenance model.

## Observability

- Prometheus scrapes the API service only.
- Grafana dashboards are provisioned for local demonstration and may need tuning for longer retention windows or larger telemetry volumes.
- Alerting writes local ClickHouse records; it does not yet send notifications through email, Slack, PagerDuty, or an incident-management system.

## Release And Deployment

- GitHub Actions currently validates builds and tests but does not deploy infrastructure.
- GitHub Container Registry publishing is documented in `docs/release-hygiene.md` but not automated.
- GitHub Releases can describe tagged versions, but they do not automatically make the local Compose stack production-ready.
