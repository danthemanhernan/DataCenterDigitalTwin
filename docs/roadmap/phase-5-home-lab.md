# Phase 5 — Home Lab Deployment

## Objective

Run DataCenterDigitalTwin on a cheap always-on home lab to practice real operations, upgrades, backups, remote access, and long-running services.

## Hardware

Recommended starting options:

- [ ] Reuse an old laptop if available
- [ ] Buy a used Lenovo Tiny, Dell OptiPlex Micro, or HP Mini
- [ ] Target 16 GB RAM minimum
- [ ] Prefer 32 GB RAM if running many services
- [ ] Use SSD storage
- [ ] Add UPS later if desired

## Operating System

- [ ] Install Ubuntu Server
- [ ] Configure SSH
- [ ] Configure automatic security updates
- [ ] Configure static DHCP lease or static IP
- [ ] Configure basic firewall rules
- [ ] Document recovery steps

## Kubernetes Runtime

- [ ] Install K3s
- [ ] Configure kubectl access
- [ ] Deploy test workload
- [ ] Deploy DataCenterDigitalTwin Helm chart
- [ ] Configure persistent storage
- [ ] Configure ingress
- [ ] Configure local DNS if useful

## Always-On Services

- [ ] Host DataCenterDigitalTwin 24/7
- [ ] Run MQTT continuously
- [ ] Run ClickHouse continuously
- [ ] Run Grafana continuously
- [ ] Run Prometheus continuously
- [ ] Run simulator workloads continuously
- [ ] Add basic uptime checks

## Remote Access

- [ ] Configure Tailscale
- [ ] Optionally configure Cloudflare Tunnel
- [ ] Avoid exposing unnecessary ports directly to the internet
- [ ] Document access patterns
- [ ] Add emergency shutdown procedure

## Backups

- [ ] Back up ClickHouse data
- [ ] Back up Grafana dashboards
- [ ] Back up Helm values
- [ ] Back up Kubernetes manifests
- [ ] Test restore process
- [ ] Document backup schedule

## Operations Practice

- [ ] Practice rolling upgrades
- [ ] Practice service restarts
- [ ] Practice node reboot
- [ ] Practice disk pressure recovery
- [ ] Practice pod failure recovery
- [ ] Practice database restore
- [ ] Practice dashboard import/export

## Future Expansion

- [ ] Add second mini PC as worker node
- [ ] Add NAS storage
- [ ] Add GitOps with Argo CD
- [ ] Add hardware sensors
- [ ] Add real energy monitoring
- [ ] Add local LLM or AI assistant service

## Deliverable

An always-on K3s home lab running DataCenterDigitalTwin as a realistic operations platform with persistent telemetry, monitoring, dashboards, backups, and remote access.
