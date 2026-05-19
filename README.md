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
| Demo application | http://localhost:8080 |
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

Generate traffic:

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

Grafana is provisioned with these teaching dashboards:

- `Observability Demo - 4 Golden Signals`
- `Observability Demo - Operations Overview`
- `Observability Demo - Service Drilldown`
- `Observability Demo - Checkout Journey`
- `Observability Demo - RED Method`
- `Observability Demo - USE Method`
- `Observability Demo - Log Formats`
- `Observability Demo - Fault Lab`
- `Observability Demo - Traces and Profiles`

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

JSON from backend fault/error events:

```json
{"level":"warning","service":"backend","replica":"backend-2","event":"fault_latency_enabled","latency_ms":1500,"trace_id":"abc123"}
```

Low-cardinality Loki labels are added by Alloy from Docker labels: `service`, `replica`, and `log_format`.

## Fault Injection

Use the UI buttons at http://localhost:8080 or call the endpoints directly.
Fault endpoints are routed to `backend-1` on purpose. This creates one bad backend replica, which makes replica-level dashboards easier to explain.

```bash
curl 'http://localhost:8080/api/fault/latency?ms=1500'
curl 'http://localhost:8080/api/fault/errors?rate=40'
curl 'http://localhost:8080/api/fault/cpu?seconds=10'
curl 'http://localhost:8080/api/fault/memory?mb=256'
curl 'http://localhost:8080/api/fault/db-slow?seconds=3'
curl 'http://localhost:8080/api/fault/db-connections?count=20&seconds=30'
curl 'http://localhost:8080/api/fault/reset'
```

## Teaching Flow

1. Start the stack with `make up`.
2. Open the demo app and Grafana.
3. Run `make load-steady` to create normal traffic.
4. Explain RED: request rate, error rate, and duration.
5. Explain USE: utilization, saturation, and errors for containers and database.
6. Explain the 4 Golden Signals: latency, traffic, errors, and saturation.
7. Compare CLF, logfmt, and JSON in the log dashboard.
8. Inject latency and show it in RED and Golden Signals.
9. Inject CPU or memory pressure and show it in USE.
10. Open a slow trace in Tempo and correlate it with logs in Loki.
11. Open Pyroscope to show where CPU time is spent during CPU faults.

## Notes

- Alloy replaces Promtail and acts as the single local collector/agent.
- Application traces use OpenTelemetry OTLP to Alloy.
- Application metrics are exposed on `/metrics` and scraped by Alloy.
- The USE dashboard avoids cAdvisor container labels because rootless Docker/Lima/Colima often do not expose them. CPU and memory use application process metrics plus CockroachDB node metrics. Network IO uses app HTTP byte counters plus CockroachDB network metrics.
- Container logs are collected by Alloy from Docker JSON log files and sent to Loki.
- Continuous profiles are sent from the Python SDK to Pyroscope.
- CockroachDB is used so the local database layer has three replicas without PostgreSQL replication setup.
