# Observability Demo

Local teaching lab for a three-layer application with logs, metrics, traces, profiling, dashboards, and fault injection.

## Architecture

```text
User
  |
Nginx load balancer
  |
Frontend replicas: frontend-1, frontend-2, frontend-3
  |
Backend replicas: backend-1, backend-2, backend-3
  |
CockroachDB replicas: crdb-1, crdb-2, crdb-3

Telemetry collection:
Apps / Docker / cAdvisor / CockroachDB
  |
Grafana Alloy
  |
Prometheus, Loki, Tempo, Pyroscope
  |
Grafana
```

All observability storage is local Docker volume storage. No S3, MinIO, or cloud account is required.

## Services

| Service | URL |
| --- | --- |
| Student application | http://localhost:8080 |
| Instructor fault console | http://localhost:8088 |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Loki | http://localhost:3100 |
| Tempo | http://localhost:3200 |
| Pyroscope | http://localhost:4040 |
| CockroachDB UI | http://localhost:8081 |

Grafana login is `admin` / `admin`.

## Start

`make up` auto-detects the Docker root directory so Alloy can read Docker JSON log files. If you run `docker compose` directly and use rootless Docker, set `DOCKER_ROOT_DIR` first. See `.env.example`.

```bash
make up
```

Then open:

```text
http://localhost:8080
http://localhost:3000
```

Generate student traffic:

```bash
make load-smoke
make load-steady
make load-spike
make load-consistent
```

Run consistent background traffic:

```bash
make traffic-start
make traffic-logs
make traffic-stop
```

Tune the consistent generator with per-minute rates:

```bash
make traffic-start TRAFFIC_DURATION=2h SHOP_PER_MIN=45 PRODUCTS_PER_MIN=30 CHECKOUT_PER_MIN=15
```

Default consistent traffic is deterministic constant-arrival-rate traffic: `20` home requests/min, `30` shop journeys/min, `20` products API requests/min, `10` checkout API requests/min, `10` orders API requests/min, and `6` health checks/min.
Set any `*_PER_MIN` value to `0` to disable that flow.

Stop:

```bash
make down
```

Delete all local data:

```bash
make clean
```

## Dashboards

Grafana is provisioned with student investigation dashboards and reference dashboards. Start with `00 Start Here`.

- `00 Start Here`
- `01 Operations Overview`
- `02 Service Drilldown`
- `03 Checkout Journey`
- `04 Logs, Traces, Profiles`
- Reference dashboards for RED, USE, 4 Golden Signals, and log formats.

Recommended real-life workflow:

1. Start from `Observability Demo - Operations Overview`.
2. If latency, errors, or traffic look abnormal, open `Observability Demo - Service Drilldown`.
3. Select the affected `service` and `replica`.
4. Use metrics to identify the symptom, then inspect logs in the same dashboard.
5. Expand a log line and click the derived `trace_id` field to jump to Tempo.
6. If CPU is high, open Pyroscope and select the matching app, for example `backend.backend-1`.
7. Use `Observability Demo - Checkout Journey` to teach a product-style user journey from frontend to backend to database.

## Log Formats

This lab intentionally emits three common log formats.

CLF from Nginx:

```text
127.0.0.1 - - [19/May/2026:10:15:42 +0000] "GET /api/products HTTP/1.1" 200 532
```

logfmt from normal frontend/backend request logs:

```text
level=info service=backend replica=backend-2 method=GET path=/api/products status=200 duration_ms=34 trace_id=abc123
```

JSON from backend error events:

```json
{"level":"error","service":"backend","replica":"backend-2","event":"request_error","path":"/api/products","status":503,"trace_id":"abc123"}
```

Low-cardinality Loki labels are added by Alloy from Docker labels: `service`, `replica`, and `log_format`.

## Instructor Fault Injection

Use the instructor console at http://localhost:8088 or call the helper scripts directly.
Fault controls are intentionally hidden from the student port. Scenarios can target `backend-1`, `backend-2`, `backend-3`, or all replicas, and can be scoped to a specific backend route.

```bash
./scripts/fault-latency.sh 1500 backend-2 /api/checkout
./scripts/fault-errors.sh 40 backend-1 /api/products 503
./scripts/fault-cpu.sh 10 backend-3
./scripts/fault-memory.sh 256 backend-2
./scripts/fault-db-slow.sh 3 backend-1
./scripts/fault-db-connections.sh 20 30 backend-1
./scripts/fault-reset.sh all
```

The student dashboards do not expose active fault settings or fault-control events. Students should infer the scenario from symptoms such as error ratio, latency, container CPU/memory utilization, logs, traces, and profiles.

## Teaching Flow

1. Start the stack with `make up`.
2. Open the demo app and Grafana.
3. Run `make load-steady` to create normal traffic.
4. Explain RED: request rate, error rate, and duration.
5. Explain USE: utilization, saturation, and errors for containers and database.
6. Explain the 4 Golden Signals: latency, traffic, errors, and saturation.
7. Compare CLF, logfmt, and JSON in the log dashboard.
8. Use the instructor console to inject a hidden scenario.
9. Ask students to identify the likely fault from telemetry symptoms.
10. Open a slow trace in Tempo and correlate it with logs in Loki.
11. Open Pyroscope to show where CPU time is spent during CPU-heavy scenarios.

## Notes

- Alloy replaces Promtail and acts as the single local collector/agent.
- Application traces use OpenTelemetry OTLP to Alloy.
- Application metrics are exposed on `/metrics` and scraped by Alloy.
- Frontend, backend, and database containers have cgroup CPU and memory quotas so cAdvisor can show utilization against explicit limits.
- Container logs are collected by Alloy from Docker JSON log files and sent to Loki.
- Continuous profiles are sent from the Python SDK to Pyroscope.
- CockroachDB is used so the local database layer has three replicas without PostgreSQL replication setup.
