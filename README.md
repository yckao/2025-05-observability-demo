# Observability Demo

Local teaching lab for an instructor-led observability workshop. The stack includes a small frontend, backend replicas, CockroachDB, Grafana, Prometheus, Loki, Tempo, Pyroscope, Grafana Alloy, k6 traffic, dashboards, and hidden instructor fault injection.

## Workshop docs

- [Instructor guide](docs/workshop/instructor-guide.md)
- [Student worksheet](docs/workshop/student-worksheet.md)
- [Scenario cards](docs/workshop/scenarios/)

## Architecture

```text
Students
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

All observability storage is local Docker volume storage. No cloud account is required for the stack itself.

## Student-facing URLs

For the main workshop path, students need only two URLs:

| Surface | Local URL | Notes |
| --- | --- | --- |
| Student application | http://localhost:8080 | Generate traffic and see failed-request trace IDs. |
| Grafana | http://localhost:3000 | Dashboards, logs, traces, and profiles. Login: `admin` / `admin`. |

Pyroscope runs internally and is queried through Grafana. Students should not need a separate Pyroscope URL.

The instructor fault console is local-only by default:

| Surface | Local URL | Notes |
| --- | --- | --- |
| Instructor fault console | http://localhost:8088 | Do not share with students. |

## Start

```bash
make up
make traffic-start
```

Then open:

```text
http://localhost:8080
http://localhost:3000
```

## Cloudflare Tunnel notes

If you expose the workshop through Cloudflare Tunnel, expose only:

- port `8080` for the student application
- port `3000` for Grafana

Set `PUBLIC_GRAFANA_URL` in `.env` so the student UI links to your public Grafana URL instead of the local default.

Example:

```dotenv
PUBLIC_GRAFANA_URL=https://grafana.example.com
```

## Common commands

```bash
make up
make down
make restart
make ps
make logs
make check
```

Traffic:

```bash
make load-smoke
make load-steady
make load-spike
make load-consistent
make traffic-start
make traffic-logs
make traffic-stop
```

Named workshop scenarios:

```bash
make scenario-list
make scenario-start NAME=checkout-latency
make scenario-status
make scenario-reset
```

Clean all local data:

```bash
make clean
```

## Default lesson flow

1. Start the stack and background traffic.
2. Share the student UI and Grafana URLs.
3. Have students record a baseline in `00 Start Here` and `01 Operations Overview`.
4. Run a hidden named scenario.
5. Students investigate with metrics, logs, traces, and Grafana profile views.
6. Reset the scenario and recap.

Use the [instructor guide](docs/workshop/instructor-guide.md) for timing, prompts, scenario order, expected evidence, and recovery steps.

## Notes

- Alloy replaces Promtail and acts as the single local collector/agent.
- Application traces use OpenTelemetry OTLP to Alloy.
- Application metrics are exposed on `/metrics` and scraped by Alloy.
- Frontend, backend, and database containers have cgroup CPU and memory quotas so cAdvisor can show utilization against explicit limits.
- Container logs are collected by Alloy from Docker JSON log files and sent to Loki.
- Continuous profiles are sent from the Python SDK to Pyroscope and explored through Grafana.
- CockroachDB is used so the local database layer has three replicas without PostgreSQL replication setup.
