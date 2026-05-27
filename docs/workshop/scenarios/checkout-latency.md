# Scenario: checkout-latency

## Instructor setup

```bash
make scenario-reset
make scenario-start NAME=checkout-latency
```

## Story for students

Customers say checkout sometimes feels slow. The rest of the shop appears mostly healthy.

## Student-visible symptoms

- Higher p95 latency on checkout traffic.
- The symptom is stronger on one backend replica.
- Slow traces include frontend to backend spans for checkout.

## Investigation path

1. Open `01 Operations Overview` and identify latency as the main symptom.
2. Open `02 Service Drilldown` and filter to `backend`.
3. Compare replicas and routes.
4. Open `03 Checkout Journey` to follow the user flow.
5. Use logs with trace IDs to open a slow trace in Tempo.

## Expected evidence

- `demo_http_request_duration_seconds` increases for `/api/checkout`.
- `backend-2` is the affected replica.
- Error rate stays near baseline.
- Traces show slow checkout backend work.

## If students get stuck

Ask: Is every route slow, or only checkout? Is every backend replica slow, or one replica?

## Reset

```bash
make scenario-reset
```
