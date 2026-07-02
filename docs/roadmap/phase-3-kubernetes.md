# Phase 3 — Kubernetes Learning and Deployment

## Objective

Use DataCenterDigitalTwin as the practical application for learning Kubernetes, local cluster development, Helm, CI-based deployment testing, and basic platform engineering.

## Week 1 — Local Kubernetes Cluster

- [ ] Install kind
- [ ] Install kubectl
- [ ] Create a local kind cluster
- [ ] Deploy nginx
- [ ] Learn Pods
- [ ] Learn Deployments
- [ ] Learn Services
- [ ] Practice port-forwarding
- [ ] Practice kubectl logs
- [ ] Practice kubectl describe

## Week 2 — Containerize the Project

Deploy each service as its own Kubernetes workload:

- [ ] FastAPI service
- [ ] MQTT broker
- [ ] ClickHouse
- [ ] React operator dashboard
- [ ] Telemetry simulator
- [ ] Grafana
- [ ] Prometheus

Learn and apply:

- [ ] Deployments
- [ ] Services
- [ ] ConfigMaps
- [ ] Secrets
- [ ] PersistentVolumes
- [ ] PersistentVolumeClaims
- [ ] Readiness probes
- [ ] Liveness probes

## Week 3 — Helm

- [ ] Learn Helm chart structure
- [ ] Create Chart.yaml
- [ ] Create values.yaml
- [ ] Template Deployments
- [ ] Template Services
- [ ] Template ConfigMaps
- [ ] Template Secrets
- [ ] Practice helm install
- [ ] Practice helm upgrade
- [ ] Practice helm rollback

## Week 4 — CI to Kubernetes

Extend GitHub Actions to validate Kubernetes deployments.

Pipeline target:

1. Run Ruff
2. Run pytest
3. Build Docker images
4. Create kind cluster
5. Deploy Helm chart
6. Run smoke tests
7. Destroy cluster

Tasks:

- [ ] Add Docker image build job
- [ ] Add kind cluster setup job
- [ ] Add Helm deploy job
- [ ] Add smoke test job
- [ ] Add Kubernetes manifest validation
- [ ] Add CI badge for deployment validation

## Week 5 — Observability on Kubernetes

Deploy:

- [ ] Prometheus
- [ ] Grafana
- [ ] kube-state-metrics
- [ ] Node exporter or equivalent local metrics source

Learn:

- [ ] Pod CPU metrics
- [ ] Pod memory metrics
- [ ] Pod restarts
- [ ] Node utilization
- [ ] Service health
- [ ] Custom FastAPI metrics
- [ ] Basic alert rules

## Week 6 — Multi-Node Simulation with k3d

Replace single-node kind experiments with a multi-node k3d environment.

Cluster target:

- [ ] 1 control plane node
- [ ] 2 worker nodes

Practice:

- [ ] Node scheduling
- [ ] Resource requests
- [ ] Resource limits
- [ ] Scaling replicas
- [ ] Draining nodes
- [ ] Cordoning nodes
- [ ] Simulating node failure
- [ ] Testing service resilience

## Advanced Platform Topics

- [ ] Ingress controllers
- [ ] TLS ingress
- [ ] Horizontal Pod Autoscaler
- [ ] Network Policies
- [ ] External Secrets
- [ ] Local container registry
- [ ] Dev, stage, and prod values files
- [ ] Kustomize vs Helm comparison
- [ ] GitOps with Argo CD

## Deliverable

A Kubernetes-deployable version of DataCenterDigitalTwin that can be run locally through kind or k3d, validated in CI, and observed through Prometheus and Grafana.
