# Observability Demo Student Worksheet

Your instructor will provide two URLs:

- Student UI: use this to generate user activity.
- Grafana: use this to investigate metrics, logs, traces, and profiles.

Start in Grafana with the `00 Start Here` dashboard.

## Baseline

Open the student UI and click a few traffic buttons. In Grafana, record what normal looks like.

| Question | Observation |
| --- | --- |
| Which services are receiving traffic? | |
| Which routes are active? | |
| What is the approximate p95 latency? | |
| Are errors present? | |
| Which backend replicas are serving requests? | |

## Investigation loop

Use this loop for each hidden scenario:

1. Look for a symptom in `01 Operations Overview`.
2. Decide whether the symptom is latency, traffic, errors, or saturation.
3. Open `02 Service Drilldown` and narrow by service and replica.
4. Check logs for the affected service or route.
5. Use a trace ID to inspect a trace in Tempo when a request is slow or failed.
6. Use Grafana profile views when CPU looks high.
7. Write a hypothesis and the evidence that supports it.

## Scenario notes

| Field | Notes |
| --- | --- |
| Symptom type | |
| Affected service | |
| Affected route | |
| Affected replica | |
| Best metric evidence | |
| Best log evidence | |
| Best trace evidence | |
| Profile evidence, if CPU-related | |
| Final hypothesis | |

## Optional deeper challenge

For experienced students:

- Compare route-level latency with replica-level latency.
- Find one log line that includes a useful `trace_id`.
- Explain why a high error rate and high latency require different first responses.
- Explain whether a symptom looks like application code, database wait, or infrastructure saturation.
