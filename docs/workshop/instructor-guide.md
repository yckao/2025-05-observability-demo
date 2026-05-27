# Observability Demo Instructor Guide

This guide runs a 60–90 minute instructor-led workshop with one shared stack. Students use the student app and Grafana. The instructor controls hidden scenarios locally.

## Public surfaces for students

Share only these URLs with students:

- Student UI: your public URL for port `8080`.
- Grafana: your public URL for port `3000`.

Do not share the instructor console URL or fault endpoints.

## Instructor preflight

Run these commands before class:

```bash
make check
make up
make scenario-reset
make traffic-start TRAFFIC_DURATION=2h
```

Open Grafana and confirm these dashboards load:

- `00 Start Here`
- `01 Operations Overview`
- `02 Service Drilldown`
- `03 Checkout Journey`
- `04 Logs, Traces, Profiles`

Confirm the student app can generate traffic:

```bash
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8080/api/health
```

Confirm hidden controls stay hidden from the student port:

```bash
curl -i http://localhost:8080/admin
curl -i http://localhost:8080/api/fault/status
```

Both responses should be `404`.

## Timing plan

| Time | Segment | Instructor actions | Student activity |
| --- | --- | --- | --- |
| 0–10 min | Orientation | Explain app topology and the two student URLs. | Open student UI and Grafana. |
| 10–20 min | Baseline | Keep `make traffic-start TRAFFIC_DURATION=2h` running. Show RED and USE signals. | Fill in baseline observations. |
| 20–40 min | Scenario 1 | Run `make scenario-start NAME=checkout-latency`. | Investigate latency by route and replica. |
| 40–55 min | Correlation | Open logs and traces from Grafana. | Record the strongest evidence. |
| 55–70 min | Scenario 2 | Run `make scenario-reset`, then `make scenario-start NAME=products-errors` or `make scenario-start NAME=cpu-hot-replica`. | Investigate errors or saturation. |
| 70–85 min | Optional challenge | Run `make scenario-reset`, then `make scenario-start NAME=db-slowdown`. | Advanced students compare app latency with DB symptoms. |
| 85–90 min | Recap | Run `make scenario-reset`. Summarize methods. | Share hypotheses and lessons. |

For a 60 minute class, skip the optional challenge and recap after Scenario 2.

## Scenario commands

List scenarios:

```bash
make scenario-list
```

Start a scenario:

```bash
make scenario-start NAME=checkout-latency
```

Check current fault state:

```bash
make scenario-status
```

Reset all replicas:

```bash
make scenario-reset
```

## Scenario order

Recommended main path:

1. `checkout-latency`
2. `products-errors`
3. `cpu-hot-replica`
4. `db-slowdown` as the optional deeper challenge

Scenario cards:

- [checkout-latency](scenarios/checkout-latency.md)
- [products-errors](scenarios/products-errors.md)
- [cpu-hot-replica](scenarios/cpu-hot-replica.md)
- [db-slowdown](scenarios/db-slowdown.md)

## Facilitation prompts

Use these prompts before giving hints:

- What changed first: traffic, errors, latency, or saturation?
- Is the symptom global, service-specific, route-specific, or replica-specific?
- Which dashboard panel gives the strongest evidence?
- Which log line or trace supports the metric signal?
- What would you check next if this were production?

## Recovery

Return to baseline:

```bash
make scenario-reset
make traffic-stop
make traffic-start TRAFFIC_DURATION=2h
```

If dashboards are empty, wait two scrape intervals, then generate traffic:

```bash
make load-smoke
```

If Grafana cannot show profiles, confirm the Pyroscope datasource exists in Grafana. Pyroscope is intentionally internal to Docker Compose; students should use Grafana for profiles.

If the stack is unhealthy, restart it:

```bash
make restart
make scenario-reset
make traffic-start TRAFFIC_DURATION=2h
```
