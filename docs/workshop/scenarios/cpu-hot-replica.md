# Scenario: cpu-hot-replica

## Instructor setup

```bash
make scenario-reset
make scenario-start NAME=cpu-hot-replica
```

## Story for students

The service feels slower under normal traffic even though errors are not the first obvious symptom.

## Student-visible symptoms

- One backend replica shows high CPU utilization.
- Latency can increase while error rate stays near baseline.
- Grafana profile views show CPU-heavy application work.

## Investigation path

1. Open `01 Operations Overview` and compare latency with saturation.
2. Open `02 Service Drilldown` and filter to `backend`.
3. Find the backend replica with high CPU utilization.
4. Open `04 Logs, Traces, Profiles`.
5. Use Grafana profile exploration with the Pyroscope datasource.

## Expected evidence

- `backend-3` is the affected replica.
- CPU burn applies to matching backend `/api/` requests.
- Container CPU utilization is higher for that replica.
- Request latency can rise without matching 5xx growth.
- Profiles point to CPU burn in the backend process.

## If students get stuck

Ask: Which signal changed besides latency? What does the affected replica have in common across metrics and profiles?

## Reset

```bash
make scenario-reset
```
